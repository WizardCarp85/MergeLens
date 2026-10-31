"""`mergelens explain` — plain-English diff summary (rules first, AI optional)."""

from __future__ import annotations

import difflib
from typing import Annotated

import typer
from rich.panel import Panel

from mergelens import config
from mergelens.cli._console import advisory_footer, emit_json, err, out
from mergelens.git.ops import get_conflicted_file_data


def generate_rule_explanation(
    ours_lines: list[str], theirs_lines: list[str], base_lines: list[str]
) -> str:
    """Generate deterministic, plain-English summary of changes."""
    ours_text = "".join(ours_lines).strip()
    theirs_text = "".join(theirs_lines).strip()
    "".join(base_lines).strip()

    if ours_text == theirs_text:
        return "Both sides contain identical changes. No semantic conflict."

    explanations = []

    diff_ours = list(difflib.unified_diff(base_lines, ours_lines, fromfile="base", tofile="ours"))
    diff_theirs = list(
        difflib.unified_diff(base_lines, theirs_lines, fromfile="base", tofile="theirs")
    )

    added_ours = [
        line[1:].strip()
        for line in diff_ours
        if line.startswith("+") and not line.startswith("+++")
    ]
    added_theirs = [
        line[1:].strip()
        for line in diff_theirs
        if line.startswith("+") and not line.startswith("+++")
    ]

    if added_ours:
        explanations.append(
            f"OURS introduces {len(added_ours)} line(s): e.g. '{added_ours[0][:60]}'"
        )
    if added_theirs:
        explanations.append(
            f"THEIRS introduces {len(added_theirs)} line(s): e.g. '{added_theirs[0][:60]}'"
        )

    # Check for imports / functions / definitions
    for name, lines in [("OURS", ours_lines), ("THEIRS", theirs_lines)]:
        for line in lines:
            l_str = line.strip()
            if (
                l_str.startswith("def ")
                or l_str.startswith("function ")
                or l_str.startswith("class ")
            ):
                explanations.append(f"{name} modifies definition '{l_str[:50]}'")
                break

    if not explanations:
        explanations.append("Both sides modify the same lines with distinct values.")

    return "\n• ".join(["• " + e for e in explanations])


def main(
    path: Annotated[str, typer.Argument(help="Conflicted file to explain.")],
    hunk: Annotated[
        int | None, typer.Option("--hunk", "-n", help="Only this hunk (1-based).")
    ] = None,
    no_ai: Annotated[
        bool, typer.Option("--no-ai", help="Rules only; never contact a model.")
    ] = False,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Plain-English summary of what each side of a conflict does."""
    cfg = config.load()
    try:
        fdata = get_conflicted_file_data(cfg.root, path)
    except Exception as exc:
        err.print(f"[bad]error:[/bad] could not inspect {path}: {exc}")
        raise typer.Exit(2) from exc

    if not fdata.hunks:
        err.print(f"[bad]error:[/bad] no conflict hunks found in {path}")
        raise typer.Exit(1)

    target_hunks = fdata.hunks
    if hunk is not None:
        if 1 <= hunk <= len(fdata.hunks):
            target_hunks = [fdata.hunks[hunk - 1]]
        else:
            err.print(f"[bad]error:[/bad] hunk {hunk} out of range (1..{len(fdata.hunks)})")
            raise typer.Exit(1)

    results = []
    for h in target_hunks:
        explanation = generate_rule_explanation(h.ours_lines, h.theirs_lines, h.base_lines)
        results.append(
            {
                "hunk_id": h.hunk_id,
                "path": path,
                "start_line": h.start_line,
                "explanation": explanation,
                "ours_lines": len(h.ours_lines),
                "theirs_lines": len(h.theirs_lines),
            }
        )

    if as_json:
        emit_json(results)
        return

    for r in results:
        out.print(
            Panel(
                str(r["explanation"]),
                title=f"Conflict Explanation: {r['hunk_id']} (line {r['start_line']})",
                title_align="left",
            )
        )

    advisory_footer()
