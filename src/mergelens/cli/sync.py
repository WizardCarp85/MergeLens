"""`mergelens sync` — push/pull refs/notes/mergelens."""

from __future__ import annotations

from typing import Annotated

import typer

from mergelens import NOTES_REF, config
from mergelens.cli._console import err, out
from mergelens.git.runner import run_git


def main(
    action: Annotated[str, typer.Argument(help="push | pull")],
    remote: Annotated[str, typer.Option("--remote", help="Remote name.")] = "origin",
) -> None:
    """pull uses `git notes merge -s cat_sort_uniq`, which is safe because notes
    are append-only JSON Lines."""
    if action not in {"push", "pull"}:
        raise typer.BadParameter("action must be 'push' or 'pull'")

    cfg = config.load()

    if action == "push":
        out.print(f"Pushing {NOTES_REF} to {remote}...")
        try:
            res = run_git(["push", remote, f"{NOTES_REF}:{NOTES_REF}"], cwd=cfg.root, allow_write=True, check=True)
            out.print(f"[ok]Successfully pushed {NOTES_REF} to {remote}.[/ok]")
        except Exception as exc:
            err.print(f"[bad]Push failed:[/bad] {exc}")
            raise typer.Exit(1)
    elif action == "pull":
        out.print(f"Fetching {NOTES_REF} from {remote}...")
        try:
            # Fetch remote notes to temporary ref
            temp_ref = f"{NOTES_REF}_upstream"
            run_git(["fetch", remote, f"{NOTES_REF}:{temp_ref}"], cwd=cfg.root, allow_write=True, check=False)
            # Merge notes append-only using cat_sort_uniq
            merge_res = run_git(
                ["notes", f"--ref={NOTES_REF}", "merge", "-s", "cat_sort_uniq", temp_ref],
                cwd=cfg.root,
                allow_write=True,
                check=False,
            )
            out.print(f"[ok]Successfully merged notes from {remote}.[/ok]")
        except Exception as exc:
            err.print(f"[bad]Pull failed:[/bad] {exc}")
            raise typer.Exit(1)
