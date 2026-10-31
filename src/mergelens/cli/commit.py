"""`mergelens commit` — the ONLY command that runs `git commit`."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.panel import Panel

from mergelens import config
from mergelens.cli._console import err, out
from mergelens.decision.manager import (
    clear_pending_decisions,
    compose_commit_message,
    load_pending_decisions,
    record_audit_notes,
)
from mergelens.git.ops import get_merge_context
from mergelens.git.runner import run_git


def main(
    stage: Annotated[
        bool,
        typer.Option(
            "--stage",
            help="Stage the conflicted files (after confirmation) before committing.",
        ),
    ] = False,
    edit: Annotated[
        bool, typer.Option("--edit", "-e", help="Open the message in your editor.")
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Print the commit message with audit trailers without committing.",
        ),
    ] = False,
) -> None:
    """Create a standard git merge commit with trailers, then attach a git note."""
    cfg = config.load()
    try:
        ctx = get_merge_context(cfg.root)
    except Exception as exc:
        err.print(f"[bad]error:[/bad] {exc}")
        raise typer.Exit(1) from exc

    decisions = load_pending_decisions(cfg.root, ctx.merge_head_sha)

    # Compose merge commit message
    subject = f"Merge branch '{ctx.theirs_ref}' into {ctx.ours_ref}"
    body = "Resolved merge conflicts with MergeLens."
    msg = compose_commit_message(
        subject=subject,
        body=body,
        decisions=decisions,
        ours_sha=ctx.head_sha,
        theirs_sha=ctx.merge_head_sha,
    )

    if dry_run:
        out.print(
            Panel(
                msg,
                title="[bold]Dry Run: Commit Message & Trailers[/bold]",
                title_align="left",
            )
        )
        out.print(f"[hint]Pending decisions to attach: {len(decisions)}[/hint]")
        return

    # Commit execution
    commit_args = ["commit", "-m", msg]
    if edit:
        commit_args.append("--edit")

    try:
        run_git(commit_args, cwd=cfg.root, allow_commit=True, check=True)
    except Exception as exc:
        err.print(f"[bad]Commit failed:[/bad] {exc}")
        err.print("[hint]Ensure conflict resolution is staged before committing.[/hint]")
        raise typer.Exit(1) from exc

    # Get newly created commit SHA
    new_head_res = run_git(["rev-parse", "HEAD"], cwd=cfg.root)
    new_commit_sha = new_head_res.stdout.strip()

    # Attach audit records to refs/notes/mergelens
    record_audit_notes(cfg.root, new_commit_sha, decisions)

    # Clear pending decisions
    clear_pending_decisions(cfg.root, ctx.merge_head_sha)

    out.print(
        Panel(
            f"[ok]Committed merge {new_commit_sha[:10]}[/ok]\n"
            f"Attached {len(decisions)} decision record(s) to refs/notes/mergelens\n"
            f"Trailers recorded in commit message.",
            title="mergelens commit successful",
            title_align="left",
        )
    )
