"""Tests enforcing hard architectural invariants."""

import ast
from pathlib import Path

import pytest

from mergelens.errors import WriteGuardError
from mergelens.git.runner import run_git

SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "mergelens"


def test_only_runner_calls_subprocess():
    """Hard Invariant: Only mergelens.git.runner may invoke subprocess."""
    runner_path = SRC_ROOT / "git" / "runner.py"

    for py_file in SRC_ROOT.rglob("*.py"):
        if py_file.resolve() == runner_path.resolve():
            continue

        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    assert name.name != "subprocess", f"{py_file} directly imports subprocess!"
            elif isinstance(node, ast.ImportFrom):
                assert node.module != "subprocess", f"{py_file} directly imports from subprocess!"


def test_write_guard_blocks_mutations():
    """Hard Invariant: Forbidden working tree mutations must be blocked."""
    for forbidden in ["checkout", "restore", "reset", "rebase", "clean"]:
        with pytest.raises(WriteGuardError):
            run_git([forbidden, "some_arg"])


def test_git_commit_requires_explicit_authorization():
    """Hard Invariant: Only mergelens commit may run git commit."""
    with pytest.raises(WriteGuardError):
        run_git(["commit", "-m", "unauthorized commit"], allow_commit=False)
