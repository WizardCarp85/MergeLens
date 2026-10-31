"""Typed errors. Exit codes: 0 ok, 1 user action needed, 2 tool/environment error."""

from __future__ import annotations


class MergeLensError(Exception):
    """Base error. ``exit_code`` is what the CLI returns."""

    exit_code: int = 2
    hint: str | None = None

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if hint is not None:
            self.hint = hint


class UserActionNeeded(MergeLensError):
    """The tool is fine; the human has to do something (e.g. ``git add``)."""

    exit_code = 1


class NotAGitRepo(MergeLensError):
    hint = "Run mergelens from inside a Git working tree."


class GitTooOld(MergeLensError):
    hint = "mergelens needs git >= 2.38 (for `merge-tree --write-tree`)."


class NoMergeInProgress(UserActionNeeded):
    hint = "Start a merge first, or use `mergelens status --preview <branch>`."


class WriteGuardError(MergeLensError):
    """A git command tried to mutate state without going through a write path."""


class NotImplementedYet(MergeLensError):
    """Placeholder for scaffolding landing in a later step."""

    exit_code = 2
