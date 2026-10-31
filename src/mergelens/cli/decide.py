"""`mergelens decide` — record a choice. Writes only to
`.git/mergelens/pending/<MERGE_HEAD>.json`. Never touches the worktree or refs.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.table import Table

from mergelens import config
from mergelens.cli._console import advisory_footer, err, out
from mergelens.decision.manager import (
    clear_pending_decisions,
    load_pending_decisions,
    save_decision,
)
from mergelens.git.ops import detect_operation
from mergelens.models import Decision


def main(
    path: Annotated[str | None, typer.Argument(help="File the decision applies to.")] = None,
    hunk: Annotated[int | None, typer.Option("--hunk", "-n", help="Hunk number (1-based).")] = None,
    keep: Annotated[
        str | None,
        typer.Option("--keep", help="ours | theirs | combine | custom"),
    ] = None,
    reason: Annotated[str | None, typer.Option("--reason", "-m", help="Why. Required.")] = None,
    show: Annotated[bool, typer.Option("--show", help="List pending decisions and exit.")] = False,
    clear: Annotated[bool, typer.Option("--clear", help="Discard pending decisions.")] = False,
) -> None:
    """Record your choice and reason. Saved as pending; writes nothing to git yet."""
    cfg = config.load()
    op, theirs_sha = detect_operation(cfg.root / ".git")

    if not theirs_sha:
        theirs_sha = "MERGE_HEAD"

    if clear:
        clear_pending_decisions(cfg.root, theirs_sha)
        out.print(f"[ok]Cleared pending decisions for {theirs_sha[:10]}.[/ok]")
        return

    if show or (path is None and keep is None and reason is None):
        decisions = load_pending_decisions(cfg.root, theirs_sha)
        if not decisions:
            out.print("[unknown]No pending decisions recorded for active merge.[/unknown]")
            advisory_footer()
            return
        table = Table(title=f"Pending Decisions ({theirs_sha[:10]})", title_justify="left")
        table.add_column("Hunk ID", style="dim")
        table.add_column("Path", style="bold")
        table.add_column("Choice", style="cyan")
        table.add_column("Reason")
        for d in decisions:
            table.add_row(d.hunk_id, d.path, d.keep, d.reason)
        out.print(table)
        advisory_footer()
        return

    if not path:
        err.print("[bad]error:[/bad] missing path argument. Specify file to record decision for.")
        raise typer.Exit(1)

    if not keep or keep not in {"ours", "theirs", "combine", "custom"}:
        err.print("[bad]error:[/bad] --keep must be one of: ours, theirs, combine, custom")
        raise typer.Exit(1)

    if not reason:
        err.print("[bad]error:[/bad] --reason / -m is required when recording a decision.")
        raise typer.Exit(1)

    hunk_id = f"{path}#{hunk or 1}"
    dec = Decision(
        hunk_id=hunk_id,
        path=path,
        keep=keep,
        reason=reason,
    )
    save_decision(cfg.root, theirs_sha, dec)
    out.print(f"[ok]Recorded pending decision for {hunk_id}: keep {keep}[/ok]")
    advisory_footer()
