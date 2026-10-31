"""`mergelens origin` — where did this commit come from?"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from mergelens import config
from mergelens.cli._console import advisory_footer, emit_json, err, out
from mergelens.git.ops import get_commit_log_info
from mergelens.git.runner import run_git
from mergelens.origin.detector import (
    find_l1_patch_id_match,
    find_l2_message_ref_match,
    get_commit_patch_id,
)


def main(
    rev: Annotated[str, typer.Argument(help="Commit-ish to trace.")],
    as_json: Annotated[bool, typer.Option("--json")] = False,
    layers: Annotated[
        str, typer.Option("--layers", help="Comma list: patchid,messages,hunks,ast.")
    ] = "patchid,messages,hunks,ast",
) -> None:
    """Run detection layers L1-L4 and print each match with its type, score and reason."""
    cfg = config.load()
    try:
        chk = run_git(["rev-parse", "--verify", rev], cwd=cfg.root)
        commit_sha = chk.stdout.strip()
    except Exception as exc:
        err.print(f"[bad]error:[/bad] invalid commit {rev}: {exc}")
        raise typer.Exit(2)

    info = get_commit_log_info(cfg.root, commit_sha)
    matches = []

    # Get recent candidate commits on main/HEAD
    candidates = []
    log_res = run_git(["log", "-n", "100", "--format=%H"], cwd=cfg.root, check=False)
    if log_res.ok:
        candidates = [c.strip() for c in log_res.stdout.splitlines() if c.strip() and c.strip() != commit_sha]

    enabled_layers = [l.strip().lower() for l in layers.split(",")]

    # Layer 2: message refs
    if "messages" in enabled_layers:
        m2 = find_l2_message_ref_match(cfg.root, commit_sha)
        if m2:
            matches.append(m2)

    # Layer 1: patch-id
    if "patchid" in enabled_layers:
        m1 = find_l1_patch_id_match(cfg.root, commit_sha, candidates)
        if m1:
            matches.append(m1)

    if as_json:
        payload = {
            "rev": rev,
            "sha": commit_sha,
            "patch_id": get_commit_patch_id(cfg.root, commit_sha),
            "matches": [m.model_dump(mode="json") for m in matches],
        }
        emit_json(payload)
        return

    out.print(Panel(
        f"[bold]{commit_sha[:10]}[/bold]: {info.get('subject', '')}\n"
        f"Author: {info.get('author_name', '')} <{info.get('author_email', '')}>\n"
        f"Date:   {info.get('date', '')}",
        title="mergelens origin trace",
        title_align="left",
    ))

    if not matches:
        out.print("[unknown]No upstream origin detected (independent change or root commit).[/unknown]")
        advisory_footer()
        return

    table = Table(title="Detected Upstream Origins", title_justify="left")
    table.add_column("Layer", style="dim")
    table.add_column("Type", style="bold")
    table.add_column("Source Commit", style="cyan")
    table.add_column("Confidence", justify="right")
    table.add_column("Reason")

    for m in matches:
        layer_num = "L1" if m.match_type.value == "patch_id" else "L2"
        table.add_row(
            layer_num,
            m.match_type.value,
            m.source_sha[:10],
            f"{int(m.confidence * 100)}%",
            m.reason,
        )

    out.print(table)
    advisory_footer()
