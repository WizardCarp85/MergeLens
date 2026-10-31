"""Testing provenance collector implementing the 5-layer waterfall:

notes -> trailers -> origin-linked -> ancestry -> Unknown
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Sequence

from mergelens import NOTES_REF
from mergelens.config import Config
from mergelens.git.ops import get_commit_log_info, is_ancestor
from mergelens.git.runner import run_git
from mergelens.models import EvidenceItem, EvidenceReport, OriginMatch, Status

TRAILER_RE = re.compile(r"^([A-Za-z0-9\-]+):\s*(.*)$")


def parse_trailers(message: str) -> dict[str, str]:
    """Extract standard Git commit trailers from message body."""
    trailers = {}
    for line in message.splitlines():
        line = line.strip()
        m = TRAILER_RE.match(line)
        if m:
            key = m.group(1).lower()
            val = m.group(2).strip()
            trailers[key] = val
    return trailers


def read_notes_evidence(root: Path, commit_sha: str) -> dict[str, str] | None:
    """Read testing metadata from refs/notes/mergelens."""
    res = run_git(["notes", f"--ref={NOTES_REF}", "show", commit_sha], cwd=root, check=False)
    if not res.ok:
        return None
    try:
        # Notes can be single JSON or JSON lines
        for line in reversed(res.stdout.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                data = json.loads(line)
                if isinstance(data, dict):
                    return data
    except Exception:
        pass
    return None


def collect_evidence(
    root: Path,
    commit_sha: str,
    cfg: Config,
    origin: OriginMatch | None = None,
) -> EvidenceReport:
    """Evaluate testing evidence through the 5-layer waterfall."""
    if not commit_sha:
        return EvidenceReport(sha="")

    report = EvidenceReport(sha=commit_sha)

    # Layer 1: Git Notes
    note_data = read_notes_evidence(root, commit_sha)
    if note_data:
        report.notes_present = True
        for key, target in [("prod", "prod"), ("uat", "uat"), ("ci", "ci")]:
            if key in note_data:
                val = str(note_data[key]).lower()
                status = Status.PASS if val in {"pass", "passed", "true", "yes", "success"} else Status.FAIL if val in {"fail", "failed", "false", "no"} else Status.UNKNOWN
                setattr(report, target, EvidenceItem(status=status, source="notes", detail=note_data.get(f"{key}_detail")))

    # Layer 2: Commit Trailers
    info = get_commit_log_info(root, commit_sha)
    msg = f"{info.get('subject', '')}\n{info.get('body', '')}"
    trailers = parse_trailers(msg)
    report.trailers = trailers

    if report.prod.status == Status.UNKNOWN:
        if "prod" in trailers or "production" in trailers:
            val = trailers.get("prod", trailers.get("production", "")).lower()
            status = Status.PASS if val in {"pass", "true", "deployed", "verified"} else Status.FAIL if val in {"fail", "false"} else Status.UNKNOWN
            report.prod = EvidenceItem(status=status, source="trailers", detail=f"Prod trailer: {val}")

    if report.uat.status == Status.UNKNOWN:
        if "uat" in trailers:
            val = trailers["uat"].lower()
            status = Status.PASS if val in {"pass", "passed", "verified"} else Status.FAIL if val in {"fail", "failed"} else Status.UNKNOWN
            report.uat = EvidenceItem(status=status, source="trailers", detail=f"UAT trailer: {val}")

    if report.ci.status == Status.UNKNOWN:
        if "ci" in trailers or "tested-by" in trailers:
            val = trailers.get("ci", trailers.get("tested-by", "")).lower()
            status = Status.PASS if val not in {"fail", "failed", "broken"} else Status.FAIL
            report.ci = EvidenceItem(status=status, source="trailers", detail=f"CI trailer: {val}")

    # Layer 3: Origin-linked evidence
    if origin and origin.source_sha and (report.prod.status == Status.UNKNOWN or report.uat.status == Status.UNKNOWN):
        upstream_evidence = collect_evidence(root, origin.source_sha, cfg, origin=None)
        if report.prod.status == Status.UNKNOWN and upstream_evidence.prod.status != Status.UNKNOWN:
            report.prod = EvidenceItem(
                status=upstream_evidence.prod.status,
                source=f"origin-linked ({origin.source_sha[:8]})",
                detail=f"Inherited from upstream {origin.reason}",
            )
        if report.uat.status == Status.UNKNOWN and upstream_evidence.uat.status != Status.UNKNOWN:
            report.uat = EvidenceItem(
                status=upstream_evidence.uat.status,
                source=f"origin-linked ({origin.source_sha[:8]})",
                detail=f"Inherited from upstream {origin.reason}",
            )
        if report.ci.status == Status.UNKNOWN and upstream_evidence.ci.status != Status.UNKNOWN:
            report.ci = EvidenceItem(
                status=upstream_evidence.ci.status,
                source=f"origin-linked ({origin.source_sha[:8]})",
                detail=f"Inherited from upstream {origin.reason}",
            )

    # Layer 4: Branch Ancestry
    ancestry_matches = []
    # Test production branch
    for prod_ref in [cfg.branches.production, "production", "origin/production", "release"]:
        chk = run_git(["rev-parse", "--verify", prod_ref], cwd=root, check=False)
        if chk.ok and is_ancestor(root, commit_sha, prod_ref):
            ancestry_matches.append(prod_ref)
            if report.prod.status == Status.UNKNOWN:
                report.prod = EvidenceItem(status=Status.PASS, source=f"ancestry ({prod_ref})", detail=f"Contained in branch {prod_ref}")
            break

    # Test UAT branch
    for uat_ref in [cfg.branches.uat, "uat", "origin/uat", "staging"]:
        chk = run_git(["rev-parse", "--verify", uat_ref], cwd=root, check=False)
        if chk.ok and is_ancestor(root, commit_sha, uat_ref):
            ancestry_matches.append(uat_ref)
            if report.uat.status == Status.UNKNOWN:
                report.uat = EvidenceItem(status=Status.PASS, source=f"ancestry ({uat_ref})", detail=f"Contained in branch {uat_ref}")
            break

    # Test mainline branch
    for main_ref in [cfg.branches.mainline, "main", "master", "origin/main", "origin/master"]:
        chk = run_git(["rev-parse", "--verify", main_ref], cwd=root, check=False)
        if chk.ok and is_ancestor(root, commit_sha, main_ref):
            ancestry_matches.append(main_ref)
            if report.ci.status == Status.UNKNOWN:
                report.ci = EvidenceItem(status=Status.PASS, source=f"ancestry ({main_ref})", detail=f"Contained in branch {main_ref}")
            break

    report.ancestry = ancestry_matches

    # Layer 5: Honestly preserved as Status.UNKNOWN if not found
    return report


def get_timeline(root: Path, commit_sha: str) -> list[dict[str, str]]:
    """Retrieve chronological timeline events for a commit."""
    events = []
    info = get_commit_log_info(root, commit_sha)
    if info.get("date"):
        events.append({
            "when": info.get("date", ""),
            "event": "Commit authored",
            "detail": f"{info.get('subject', '')} by {info.get('author_name', '')}",
        })

    # Check notes
    note_data = read_notes_evidence(root, commit_sha)
    if note_data:
        events.append({
            "when": note_data.get("when", note_data.get("decided_at", "")),
            "event": "Audit note recorded",
            "detail": f"Decision: keep={note_data.get('keep')}, reason={note_data.get('reason')}",
        })

    return events

