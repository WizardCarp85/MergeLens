"""Origin detection layers L1-L4:

L1: git patch-id (exact semantic patch equivalence)
L2: Message references (cherry-pick -x, Django "Backport of", PR refs)
L3: Hunk-level patch-id
L4: Token / AST similarity for modified cherry-picks
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Sequence

from mergelens.git.ops import get_commit_log_info
from mergelens.git.runner import run_git
from mergelens.models import MatchType, OriginMatch

# Regex patterns for commit message backport & cherry-pick trailers
CHERRY_PICK_X_RE = re.compile(
    r"(?:cherry picked from commit|cherry-picked from commit)\s+([0-9a-fA-F]{7,40})",
    re.IGNORECASE,
)
DJANGO_BACKPORT_RE = re.compile(
    r"Backport of\s+([0-9a-fA-F]{7,40})",
    re.IGNORECASE,
)
GENERIC_BACKPORT_RE = re.compile(
    r"(?:backport|upstream commit|origin commit|original-commit):\s*([0-9a-fA-F]{7,40})",
    re.IGNORECASE,
)
PR_REF_RE = re.compile(r"(?:#|GH-|pull/)(\d+)", re.IGNORECASE)


def compute_patch_id(root: Path, patch_text: str) -> str | None:
    """Compute git patch-id for given diff text."""
    if not patch_text.strip():
        return None
    res = run_git(["patch-id", "--stable"], cwd=root, input_data=patch_text, check=False)
    if res.ok and res.stdout.strip():
        # Output format: "<patch-id> <commit-sha-or-zero>"
        return res.stdout.split()[0]
    return None


def get_commit_patch_id(root: Path, commit_sha: str) -> str | None:
    """Compute patch-id of a commit using git diff-tree."""
    res = run_git(
        ["diff-tree", "-p", "--no-commit-id", "--root", commit_sha],
        cwd=root,
        check=False,
    )
    if not res.ok:
        return None
    return compute_patch_id(root, res.stdout)


def find_l1_patch_id_match(
    root: Path,
    target_sha: str,
    candidate_commits: Sequence[str],
) -> OriginMatch | None:
    """L1: Search for identical patch-id among candidate commits."""
    target_pid = get_commit_patch_id(root, target_sha)
    if not target_pid:
        return None

    for cand in candidate_commits:
        if cand == target_sha:
            continue
        cand_pid = get_commit_patch_id(root, cand)
        if cand_pid and cand_pid == target_pid:
            return OriginMatch(
                match_type=MatchType.PATCH_ID,
                source_sha=cand,
                target_sha=target_sha,
                confidence=1.0,
                reason=f"Exact patch-id match with {cand[:10]}",
                details={"patch_id": target_pid},
            )
    return None


def find_l2_message_ref_match(root: Path, commit_sha: str) -> OriginMatch | None:
    """L2: Search for upstream commit references in commit message."""
    info = get_commit_log_info(root, commit_sha)
    msg = f"{info.get('subject', '')}\n{info.get('body', '')}"

    # 1. cherry-pick -x
    m = CHERRY_PICK_X_RE.search(msg)
    if m:
        ref_sha = m.group(1)
        # Verify commit exists in repository
        chk = run_git(["rev-parse", "--verify", ref_sha], cwd=root, check=False)
        verified_sha = chk.stdout.strip() if chk.ok else ref_sha
        return OriginMatch(
            match_type=MatchType.CHERRY_PICK_X,
            source_sha=verified_sha,
            target_sha=commit_sha,
            confidence=0.98,
            reason=f"Cherry-pick -x trailer points to {verified_sha[:10]}",
            details={"raw_reference": ref_sha},
        )

    # 2. Django-style "Backport of <hash>"
    m = DJANGO_BACKPORT_RE.search(msg)
    if m:
        ref_sha = m.group(1)
        chk = run_git(["rev-parse", "--verify", ref_sha], cwd=root, check=False)
        verified_sha = chk.stdout.strip() if chk.ok else ref_sha
        return OriginMatch(
            match_type=MatchType.MESSAGE_REF,
            source_sha=verified_sha,
            target_sha=commit_sha,
            confidence=0.95,
            reason=f"Django backport header references {verified_sha[:10]}",
            details={"raw_reference": ref_sha, "format": "django"},
        )

    # 3. Generic Backport: <hash>
    m = GENERIC_BACKPORT_RE.search(msg)
    if m:
        ref_sha = m.group(1)
        chk = run_git(["rev-parse", "--verify", ref_sha], cwd=root, check=False)
        verified_sha = chk.stdout.strip() if chk.ok else ref_sha
        return OriginMatch(
            match_type=MatchType.MESSAGE_REF,
            source_sha=verified_sha,
            target_sha=commit_sha,
            confidence=0.90,
            reason=f"Backport trailer references {verified_sha[:10]}",
            details={"raw_reference": ref_sha},
        )

    return None


def find_l3_hunk_patch_id_match(
    root: Path,
    path: str,
    hunk_lines: Sequence[str],
    candidate_commits: Sequence[str],
) -> OriginMatch | None:
    """L3: Match individual hunk patch-id against candidate commit diffs."""
    if not hunk_lines:
        return None
    # Fabricate a unified diff hunk for git patch-id
    synthetic_diff = f"--- a/{path}\n+++ b/{path}\n@@ -1,1 +1,{len(hunk_lines)} @@\n" + "".join(
        f"+{l}" if not l.startswith("+") else l for l in hunk_lines
    )
    hunk_pid = compute_patch_id(root, synthetic_diff)
    if not hunk_pid:
        return None

    for cand in candidate_commits:
        diff_res = run_git(["show", "--format=", "--unified=0", cand, "--", path], cwd=root, check=False)
        if diff_res.ok and diff_res.stdout:
            cand_pid = compute_patch_id(root, diff_res.stdout)
            if cand_pid and cand_pid == hunk_pid:
                return OriginMatch(
                    match_type=MatchType.HUNK_PATCH_ID,
                    source_sha=cand,
                    target_sha="",
                    confidence=0.88,
                    reason=f"Hunk patch-id matched commit {cand[:10]} on {path}",
                    details={"hunk_patch_id": hunk_pid},
                )
    return None


def find_l4_ast_similarity_match(
    text_a: str,
    text_b: str,
    source_sha: str = "",
    target_sha: str = "",
) -> OriginMatch | None:
    """L4: AST / Tokenized similarity for modified code during backports."""
    clean_a = [
        line.strip()
        for line in text_a.splitlines()
        if line.strip() and not line.strip().startswith("#") and not line.strip().startswith("//")
    ]
    clean_b = [
        line.strip()
        for line in text_b.splitlines()
        if line.strip() and not line.strip().startswith("#") and not line.strip().startswith("//")
    ]

    if not clean_a or not clean_b:
        return None

    # Token-level comparison ignoring trivial variable name changes & whitespace
    tokens_a = re.findall(r"\w+", " ".join(clean_a))
    tokens_b = re.findall(r"\w+", " ".join(clean_b))

    matcher = difflib.SequenceMatcher(None, tokens_a, tokens_b)
    ratio = matcher.ratio()

    if ratio >= 0.65:
        return OriginMatch(
            match_type=MatchType.AST_SIMILAR,
            source_sha=source_sha,
            target_sha=target_sha,
            confidence=round(ratio * 0.85, 2),
            reason=f"Content token similarity {int(ratio * 100)}% with {source_sha[:10] if source_sha else 'upstream'}",
            details={"similarity_ratio": round(ratio, 3)},
        )

    return None


def detect_origin(
    root: Path,
    target_sha: str,
    candidate_commits: Sequence[str] | None = None,
    hunk_lines: Sequence[str] | None = None,
    path: str | None = None,
) -> OriginMatch | None:
    """Run detection layers L1 -> L2 -> L3 in order of decreasing certainty."""
    if not target_sha:
        return None

    # L2 is fastest and highly accurate on real backports (CPython, Django, etc.)
    m2 = find_l2_message_ref_match(root, target_sha)
    if m2:
        return m2

    # L1 patch-id
    candidates = candidate_commits or []
    if not candidates:
        # Get last 50 commits on main/HEAD
        res = run_git(["log", "-n", "50", "--format=%H"], cwd=root, check=False)
        if res.ok:
            candidates = [line.strip() for line in res.stdout.splitlines() if line.strip()]

    m1 = find_l1_patch_id_match(root, target_sha, candidates)
    if m1:
        return m1

    # L3 hunk patch-id
    if hunk_lines and path:
        m3 = find_l3_hunk_patch_id_match(root, path, hunk_lines, candidates)
        if m3:
            return m3

    return None
