"""Git access layer.

Hard invariant: Only ``mergelens.git.runner`` may invoke a subprocess.
No command ever writes to the user's working tree.
Only ``mergelens commit`` may run ``git commit``.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from mergelens import MIN_GIT_VERSION, NOTES_REF
from mergelens.errors import GitTooOld, MergeLensError, NotAGitRepo, WriteGuardError

# Commands that only inspect state and never modify the index, refs, or working tree.
READ_COMMANDS = {
    "--version",
    "version",
    "rev-parse",
    "status",
    "ls-files",
    "cat-file",
    "diff",
    "diff-tree",
    "log",
    "patch-id",
    "merge-base",
    "merge-tree",
    "show",
    "branch",
}

# Commands that modify refs or config without altering working tree files.
WRITE_COMMANDS = {
    "init",
    "commit",
    "notes",
    "config",
    "push",
    "fetch",
    "add",
}

# Subcommands strictly forbidden because they can modify the working tree.
FORBIDDEN_COMMANDS = {
    "checkout",
    "restore",
    "reset",
    "rebase",
    "merge",
    "cherry-pick",
    "clean",
    "rm",
    "mv",
    "stash",
}


@dataclass(frozen=True)
class GitResult:
    stdout: str
    stderr: str
    returncode: int

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _parse_subcommand(args: Sequence[str]) -> str:
    for arg in args:
        if arg.startswith("-") and arg not in {"--version"}:
            continue
        return arg
    return ""


def run_git(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    input_data: str | bytes | None = None,
    check: bool = True,
    allow_write: bool = False,
    allow_commit: bool = False,
    allow_fixture: bool = False,
) -> GitResult:
    """Execute git with strict allowlist and write protection."""
    subcmd = _parse_subcommand(args)

    if not allow_fixture:
        if subcmd in FORBIDDEN_COMMANDS:
            raise WriteGuardError(
                f"Git subcommand '{subcmd}' is forbidden because it can modify the working tree.",
                hint="mergelens never mutates the working tree.",
            )

        if subcmd == "commit":
            if not allow_commit:
                raise WriteGuardError(
                    "git commit is forbidden except when authorized via mergelens commit.",
                    hint="Only `mergelens commit` is permitted to invoke git commit.",
                )
        elif subcmd in WRITE_COMMANDS:
            # Special case: read-only config inspection is allowed without allow_write
            is_config_read = subcmd == "config" and any(
                a in args for a in ["--get", "--get-all", "-l", "--list"]
            )
            is_notes_read = subcmd == "notes" and (
                "show" in args or "list" in args or len(args) == 1
            )
            if not (is_config_read or is_notes_read) and not allow_write:
                raise WriteGuardError(
                    f"Git subcommand '{subcmd}' requires explicit write permission.",
                    hint="Pass allow_write=True to authorize this mutation.",
                )
        elif subcmd not in READ_COMMANDS and subcmd != "":
            raise WriteGuardError(
                f"Git subcommand '{subcmd}' is not in the mergelens allowlist.",
                hint=f"Allowed read commands: {', '.join(sorted(READ_COMMANDS))}",
            )

    cmd = ["git", *args]
    stdin_input = input_data.encode("utf-8") if isinstance(input_data, str) else input_data

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            input=stdin_input,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as err:
        raise MergeLensError("Git executable not found in PATH.") from err

    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")

    if check and proc.returncode != 0:
        if "not a git repository" in stderr.lower():
            raise NotAGitRepo(
                "Not inside a git repository.",
                hint="Run mergelens from inside a Git working tree.",
            )
        raise MergeLensError(
            f"git {' '.join(args)} failed with exit code {proc.returncode}: {stderr.strip()}"
        )

    return GitResult(stdout=stdout, stderr=stderr, returncode=proc.returncode)


def get_git_version(cwd: Path | None = None) -> tuple[int, int, int]:
    """Return parsed (major, minor, patch) git version, enforcing MIN_GIT_VERSION."""
    res = run_git(["--version"], cwd=cwd, check=True)
    # Output format: git version 2.39.3 (Apple Git-146) or git version 2.40.0
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", res.stdout)
    if not m:
        return (0, 0, 0)
    major = int(m.group(1))
    minor = int(m.group(2))
    patch = int(m.group(3) or 0)
    ver = (major, minor, patch)
    if ver < MIN_GIT_VERSION:
        min_ver_str = ".".join(map(str, MIN_GIT_VERSION))
        raise GitTooOld(
            f"Detected Git {ver[0]}.{ver[1]}.{ver[2]}, but mergelens requires >= {min_ver_str}",
            hint="Please upgrade git.",
        )
    return ver


def has_notes_rewrite_ref(cwd: Path | None = None) -> bool:
    """Check whether notes.rewriteRef is configured to track refs/notes/mergelens."""
    res = run_git(["config", "--get-all", "notes.rewriteRef"], cwd=cwd, check=False)
    if not res.ok:
        return False
    configured = {line.strip() for line in res.stdout.splitlines()}
    return NOTES_REF in configured or "refs/notes/*" in configured
