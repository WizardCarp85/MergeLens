"""`mergelens init` — opt-in repo configuration."""

from __future__ import annotations

from typing import Annotated

import typer

from mergelens import NOTES_REF, config
from mergelens.cli._console import out
from mergelens.git.runner import run_git


def main(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="List the git config changes without applying them."),
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip the per-change prompt.")] = False,
    rerere: Annotated[
        bool, typer.Option("--rerere/--no-rerere", help="Also enable git rerere.")
    ] = True,
) -> None:
    """Configure:

    * notes.rewriteRef=refs/notes/mergelens (notes survive rebase/amend)
    * notes.rewrite.rebase / notes.rewrite.amend = true
    * rerere.enabled = true (optional)
    """
    cfg = config.load()
    changes = [
        ("notes.rewriteRef", NOTES_REF),
        ("notes.rewrite.rebase", "true"),
        ("notes.rewrite.amend", "true"),
    ]
    if rerere:
        changes.append(("rerere.enabled", "true"))

    if dry_run:
        out.print("[bold]Changes that would be applied to .git/config:[/bold]")
        for k, v in changes:
            out.print(f"  git config {k} '{v}'")
        return

    for k, v in changes:
        if not yes:
            confirm = typer.confirm(f"Set git config {k} = '{v}'?", default=True)
            if not confirm:
                continue
        run_git(["config", k, v], cwd=cfg.root, allow_write=True, check=True)
        out.print(f"[ok]Configured {k} = {v}[/ok]")

    out.print("[bold green]mergelens repo initialization complete.[/bold green]")
