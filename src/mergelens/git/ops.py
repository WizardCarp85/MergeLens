"""High-level Git inspection and query operations built atop runner.py."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mergelens.errors import NoMergeInProgress
from mergelens.git.runner import run_git
from mergelens.models import Operation, Side


@dataclass(frozen=True)
class ConflictHunkData:
    hunk_id: str
    path: str
    ours_lines: list[str]
    theirs_lines: list[str]
    base_lines: list[str]
    start_line: int = 1


@dataclass(frozen=True)
class ConflictedFileData:
    path: str
    stage1_sha: str | None  # base
    stage2_sha: str | None  # ours
    stage3_sha: str | None  # theirs
    hunks: list[ConflictHunkData]


@dataclass(frozen=True)
class ActiveMergeContext:
    operation: Operation
    ours_ref: str
    theirs_ref: str
    head_sha: str
    merge_head_sha: str
    conflicted_files: list[str]
    is_preview: bool = False


def detect_operation(git_dir: Path) -> tuple[Operation, str | None]:
    """Detect in-progress Git operation and the corresponding theirs ref."""
    if (git_dir / "MERGE_HEAD").is_file():
        theirs = (git_dir / "MERGE_HEAD").read_text(encoding="utf-8").strip().splitlines()[0]
        return Operation.MERGE, theirs
    if (git_dir / "CHERRY_PICK_HEAD").is_file():
        theirs = (git_dir / "CHERRY_PICK_HEAD").read_text(encoding="utf-8").strip().splitlines()[0]
        return Operation.CHERRY_PICK, theirs
    if (git_dir / "rebase-merge").is_dir() or (git_dir / "rebase-apply").is_dir():
        # Look for stopped-sha or head-name
        rebase_dir = (
            git_dir / "rebase-merge"
            if (git_dir / "rebase-merge").is_dir()
            else git_dir / "rebase-apply"
        )
        stopped = rebase_dir / "stopped-sha"
        theirs = stopped.read_text(encoding="utf-8").strip() if stopped.is_file() else "REBASE_HEAD"
        return Operation.REBASE, theirs
    return Operation.NONE, None


def get_merge_context(root: Path, preview_branch: str | None = None) -> ActiveMergeContext:
    """Get active merge context or simulate preview against a target branch."""
    git_dir = root / ".git"

    if preview_branch:
        # Virtual preview using git merge-tree --write-tree
        head_res = run_git(["rev-parse", "HEAD"], cwd=root)
        head_sha = head_res.stdout.strip()
        theirs_res = run_git(["rev-parse", preview_branch], cwd=root)
        theirs_sha = theirs_res.stdout.strip()

        # Run merge-tree to preview conflicts
        # git merge-tree --write-tree HEAD <preview_branch>
        mt_res = run_git(
            ["merge-tree", "--write-tree", "--name-only", "HEAD", preview_branch],
            cwd=root,
            check=False,
        )
        conflicted = []
        if mt_res.returncode != 0:
            for line in mt_res.stdout.splitlines():
                line = line.strip()
                if line and not line.startswith("CONFLICT") and len(line) != 40:
                    conflicted.append(line)
        return ActiveMergeContext(
            operation=Operation.MERGE,
            ours_ref="HEAD",
            theirs_ref=preview_branch,
            head_sha=head_sha,
            merge_head_sha=theirs_sha,
            conflicted_files=sorted(set(conflicted)),
            is_preview=True,
        )

    op, theirs_sha = detect_operation(git_dir)
    if op == Operation.NONE or not theirs_sha:
        raise NoMergeInProgress(
            "No merge, cherry-pick, or rebase conflict in progress.",
            hint="Start a merge first, or use `mergelens status --preview <branch>`.",
        )

    head_res = run_git(["rev-parse", "HEAD"], cwd=root)
    head_sha = head_res.stdout.strip()

    # Get conflicted files from `git diff --name-only --diff-filter=U`
    diff_res = run_git(["diff", "--name-only", "--diff-filter=U"], cwd=root, check=False)
    conflicted = [line.strip() for line in diff_res.stdout.splitlines() if line.strip()]

    # Also check git ls-files -u
    if not conflicted:
        ls_res = run_git(["ls-files", "-u"], cwd=root, check=False)
        paths = set()
        for line in ls_res.stdout.splitlines():
            parts = line.split(maxsplit=3)
            if len(parts) == 4:
                paths.add(parts[3])
        conflicted = sorted(paths)

    return ActiveMergeContext(
        operation=op,
        ours_ref="HEAD",
        theirs_ref=theirs_sha,
        head_sha=head_sha,
        merge_head_sha=theirs_sha,
        conflicted_files=conflicted,
        is_preview=False,
    )


def read_blob(root: Path, blob_sha: str) -> str:
    """Read a blob from Git's object database."""
    res = run_git(["cat-file", "-p", blob_sha], cwd=root)
    return res.stdout


def parse_conflict_markers(content: str, path: str) -> list[ConflictHunkData]:
    """Parse conflict markers in file text (supporting 2-way and 3-way diffs)."""
    lines = content.splitlines(keepends=True)
    hunks: list[ConflictHunkData] = []
    in_conflict = False
    current_side: Side | None = None
    ours: list[str] = []
    theirs: list[str] = []
    base: list[str] = []
    hunk_index = 1
    start_line = 1

    for idx, line in enumerate(lines, 1):
        if line.startswith("<<<<<<<"):
            in_conflict = True
            current_side = Side.OURS
            ours, theirs, base = [], [], []
            start_line = idx
        elif in_conflict and line.startswith("|||||||"):
            current_side = Side.BASE
        elif in_conflict and line.startswith("======="):
            current_side = Side.THEIRS
        elif in_conflict and line.startswith(">>>>>>>"):
            in_conflict = False
            hunks.append(
                ConflictHunkData(
                    hunk_id=f"{path}#{hunk_index}",
                    path=path,
                    ours_lines=ours,
                    theirs_lines=theirs,
                    base_lines=base,
                    start_line=start_line,
                )
            )
            hunk_index += 1
            current_side = None
        elif in_conflict:
            if current_side == Side.OURS:
                ours.append(line)
            elif current_side == Side.BASE:
                base.append(line)
            elif current_side == Side.THEIRS:
                theirs.append(line)

    return hunks


def get_conflicted_file_data(root: Path, path: str) -> ConflictedFileData:
    """Inspect stages 1, 2, and 3 for a path and parse conflict hunks."""
    ls_res = run_git(["ls-files", "-u", "--", path], cwd=root, check=False)
    s1, s2, s3 = None, None, None
    for line in ls_res.stdout.splitlines():
        parts = line.split(maxsplit=3)
        if len(parts) == 4:
            mode, sha, stage, p = parts
            if stage == "1":
                s1 = sha
            elif stage == "2":
                s2 = sha
            elif stage == "3":
                s3 = sha

    file_path = root / path
    hunks: list[ConflictHunkData] = []
    if file_path.is_file():
        text = file_path.read_text(encoding="utf-8", errors="replace")
        hunks = parse_conflict_markers(text, path)

    # Fallback if no markers found in file (or empty hunks) but stages exist
    if not hunks and (s2 or s3):
        ours_text = read_blob(root, s2).splitlines(keepends=True) if s2 else []
        theirs_text = read_blob(root, s3).splitlines(keepends=True) if s3 else []
        base_text = read_blob(root, s1).splitlines(keepends=True) if s1 else []
        hunks.append(
            ConflictHunkData(
                hunk_id=f"{path}#1",
                path=path,
                ours_lines=ours_text,
                theirs_lines=theirs_text,
                base_lines=base_text,
                start_line=1,
            )
        )

    return ConflictedFileData(
        path=path,
        stage1_sha=s1,
        stage2_sha=s2,
        stage3_sha=s3,
        hunks=hunks,
    )


def is_ancestor(root: Path, commit_sha: str, target_branch: str) -> bool:
    """Check if commit_sha is an ancestor of target_branch."""
    res = run_git(["merge-base", "--is-ancestor", commit_sha, target_branch], cwd=root, check=False)
    return res.ok


def get_commit_log_info(root: Path, rev: str) -> dict[str, str]:
    """Retrieve metadata for a commit (subject, body, author, date)."""
    fmt = "%H%n%an%n%ae%n%aI%n%s%n%b"
    res = run_git(["log", "-1", f"--format={fmt}", rev], cwd=root, check=False)
    if not res.ok:
        return {}
    parts = res.stdout.split("\n", 5)
    return {
        "sha": parts[0] if len(parts) > 0 else rev,
        "author_name": parts[1] if len(parts) > 1 else "",
        "author_email": parts[2] if len(parts) > 2 else "",
        "date": parts[3] if len(parts) > 3 else "",
        "subject": parts[4] if len(parts) > 4 else "",
        "body": parts[5] if len(parts) > 5 else "",
    }
