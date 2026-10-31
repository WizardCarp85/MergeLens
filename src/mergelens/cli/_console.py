"""Shared output helpers. Every command renders through here so that `--json`
and human output never diverge."""

from __future__ import annotations

import json
import sys
from typing import Any, NoReturn

import typer
from rich.console import Console
from rich.theme import Theme

from mergelens.errors import MergeLensError

THEME = Theme(
    {
        "ours": "bold cyan",
        "theirs": "bold magenta",
        "base": "dim",
        "ok": "bold green",
        "warn": "bold yellow",
        "bad": "bold red",
        "unknown": "dim white",
        "hint": "italic dim",
    }
)

# stdout = data, stderr = chatter. Keeps `--json` pipeable.
out = Console(theme=THEME, highlight=False)
err = Console(theme=THEME, stderr=True, highlight=False)


def emit_json(payload: Any) -> None:
    """Dump a model or dict as JSON on stdout."""
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    sys.stdout.write(json.dumps(payload, indent=2, default=str) + "\n")


def advisory_footer() -> None:
    err.print("[hint]mergelens is advisory — no files were modified.[/hint]")


def fail(exc: MergeLensError) -> NoReturn:
    err.print(f"[bad]error:[/bad] {exc.message}")
    if exc.hint:
        err.print(f"[hint]{exc.hint}[/hint]")
    raise typer.Exit(exc.exit_code)


def todo(step: str) -> NoReturn:
    """Honest placeholder for scaffolding that lands in a later step."""
    err.print(f"[warn]not implemented yet[/warn] — arrives in {step}")
    raise typer.Exit(2)
