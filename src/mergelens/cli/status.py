"""`mergelens status` — main read command.

Detects in-progress merge, reads conflict stages, analyzes origin and
testing evidence for OURS vs THEIRS, and shows recommendations.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from mergelens import config
from mergelens.cli._console import advisory_footer, emit_json, err, out
from mergelens.evidence.collector import collect_evidence
from mergelens.git.ops import get_conflicted_file_data, get_merge_context
from mergelens.models import ConflictHunk, MergeContext, Side, SideInfo
from mergelens.origin.detector import detect_origin
from mergelens.scoring.engine import compute_side_score, evaluate_recommendation


def build_status_hunks(
    cfg: config.Config, preview: str | None = None
) -> tuple[MergeContext, list[ConflictHunk]]:
    """Build complete MergeContext and analyzed ConflictHunks."""
    ctx = get_merge_context(cfg.root, preview_branch=preview)
    hunks: list[ConflictHunk] = []

    # Pre-collect candidate commits for origin matching
    candidates: list[str] = []

    for path in ctx.conflicted_files:
        fdata = get_conflicted_file_data(cfg.root, path)
        for hdata in fdata.hunks:
            # Analyze THEIRS
            origin_theirs = detect_origin(
                cfg.root,
                ctx.merge_head_sha,
                candidates,
                hdata.theirs_lines,
                path,
            )
            evidence_theirs = collect_evidence(cfg.root, ctx.merge_head_sha, cfg, origin_theirs)
            score_theirs, reasons_theirs = compute_side_score(
                evidence_theirs, origin_theirs, cfg.scoring
            )

            # Analyze OURS
            origin_ours = detect_origin(
                cfg.root,
                ctx.head_sha,
                candidates,
                hdata.ours_lines,
                path,
            )
            evidence_ours = collect_evidence(cfg.root, ctx.head_sha, cfg, origin_ours)
            score_ours, reasons_ours = compute_side_score(evidence_ours, origin_ours, cfg.scoring)

            rec = evaluate_recommendation(
                score_ours=score_ours,
                score_theirs=score_theirs,
                reasons_ours=reasons_ours,
                reasons_theirs=reasons_theirs,
                cfg=cfg.scoring,
            )

            hunk = ConflictHunk(
                hunk_id=hdata.hunk_id,
                path=path,
                start_line=hdata.start_line,
                ours=SideInfo(
                    side=Side.OURS,
                    sha=ctx.head_sha,
                    text="".join(hdata.ours_lines),
                    lines=hdata.ours_lines,
                    origin=origin_ours,
                    evidence=evidence_ours,
                ),
                theirs=SideInfo(
                    side=Side.THEIRS,
                    sha=ctx.merge_head_sha,
                    text="".join(hdata.theirs_lines),
                    lines=hdata.theirs_lines,
                    origin=origin_theirs,
                    evidence=evidence_theirs,
                ),
                base=SideInfo(
                    side=Side.BASE,
                    sha=fdata.stage1_sha,
                    text="".join(hdata.base_lines),
                    lines=hdata.base_lines,
                )
                if fdata.stage1_sha or hdata.base_lines
                else None,
                recommendation=rec,
            )
            hunks.append(hunk)

    mctx = MergeContext(
        operation=ctx.operation,
        ours=ctx.ours_ref,
        theirs=ctx.theirs_ref,
        head=ctx.head_sha,
        merge_head=ctx.merge_head_sha,
        conflicted_files=ctx.conflicted_files,
        is_preview=ctx.is_preview,
    )
    return mctx, hunks


def main(
    as_json: Annotated[bool, typer.Option("--json", help="Machine-readable output.")] = False,
    preview: Annotated[
        str | None,
        typer.Option(
            "--preview",
            metavar="BRANCH",
            help="Predict conflicts against BRANCH without starting a merge.",
        ),
    ] = None,
    path: Annotated[list[str] | None, typer.Argument(help="Limit to these paths.")] = None,
) -> None:
    """Detect in-progress merge, read conflict stages, and show
    OURS vs THEIRS with origin, testing evidence and a recommendation.
    """
    cfg = config.load()
    try:
        ctx, hunks = build_status_hunks(cfg, preview=preview)
    except Exception as exc:
        err.print(f"[bad]error:[/bad] {exc}")
        raise typer.Exit(2) from exc

    if path:
        paths_set = set(path)
        hunks = [h for h in hunks if h.path in paths_set]

    if as_json:
        payload = {
            "context": ctx.model_dump(mode="json"),
            "hunks": [h.model_dump(mode="json") for h in hunks],
        }
        emit_json(payload)
        return

    # Render human summary
    mode_str = (
        f"PREVIEW vs {ctx.theirs}" if ctx.is_preview else f"{ctx.operation.upper()} in progress"
    )
    out.print(
        Panel(
            f"[bold]{mode_str}[/bold]\n"
            f"[ours]OURS (HEAD):[/ours] {ctx.head[:10]} ({ctx.ours})\n"
            f"[theirs]THEIRS (MERGE_HEAD):[/theirs] {ctx.merge_head[:10]} ({ctx.theirs})\n"
            f"Conflicted files: [bold]{len(ctx.conflicted_files)}[/bold]",
            title="mergelens conflict status",
            title_align="left",
        )
    )

    if not hunks:
        out.print("[ok]No conflicts found.[/ok]")
        advisory_footer()
        return

    table = Table(title="Conflict Hunks & Recommendations", title_justify="left")
    table.add_column("Hunk ID", style="dim")
    table.add_column("Path", style="bold")
    table.add_column("OURS Testing", style="cyan")
    table.add_column("THEIRS Testing", style="magenta")
    table.add_column("Score", justify="right")
    table.add_column("Recommendation")

    for h in hunks:
        ours_ev = []
        if h.ours.evidence:
            if h.ours.evidence.prod.status.value == "pass":
                ours_ev.append("prod:PASS")
            if h.ours.evidence.uat.status.value == "pass":
                ours_ev.append("uat:PASS")
            if h.ours.evidence.ci.status.value == "pass":
                ours_ev.append("ci:PASS")
        ours_str = ", ".join(ours_ev) if ours_ev else "unverified"

        theirs_ev = []
        if h.theirs.evidence:
            if h.theirs.evidence.prod.status.value == "pass":
                theirs_ev.append("prod:PASS")
            if h.theirs.evidence.uat.status.value == "pass":
                theirs_ev.append("uat:PASS")
            if h.theirs.evidence.ci.status.value == "pass":
                theirs_ev.append("ci:PASS")
        if h.theirs.origin:
            theirs_ev.append(f"origin:{h.theirs.origin.source_sha[:7]}")
        theirs_str = ", ".join(theirs_ev) if theirs_ev else "unverified"

        action = h.recommendation.action
        act_style = "bold green" if "KEEP" in action else "bold yellow"

        table.add_row(
            h.hunk_id,
            h.path,
            ours_str,
            theirs_str,
            f"{h.recommendation.score_ours} vs {h.recommendation.score_theirs}",
            f"[{act_style}]{action}[/{act_style}]",
        )

    out.print(table)
    advisory_footer()
