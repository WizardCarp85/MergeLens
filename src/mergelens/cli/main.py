"""mergelens entry point. Registers commands; contains no logic."""

from __future__ import annotations

from typing import Annotated

import typer

from mergelens import __version__
from mergelens.cli import (
    commit,
    decide,
    doctor,
    explain,
    init,
    origin,
    status,
    sync,
    ui,
)
from mergelens.cli._console import err

app = typer.Typer(
    name="mergelens",
    help=(
        "Git-native merge conflict advisor.\n\n"
        "Reads your repo, explains where each side came from and how well it was "
        "tested, and recommends an action. It never edits your files — you resolve, "
        "then run `mergelens commit`."
    ),
    no_args_is_help=True,
    add_completion=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _version_cb(value: bool) -> None:
    if value:
        typer.echo(f"mergelens {__version__}")
        raise typer.Exit(0)


@app.callback()
def root(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            callback=_version_cb,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = False,
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress chatter on stderr.")
    ] = False,
) -> None:
    if quiet:
        err.quiet = True


app.command(
    "init",
    help="One-time repo setup (notes rewrite config, rerere). Asks before every change.",
)(init.main)
app.command(
    "doctor",
    help="Check environment: git version, notes config, dashboard assets, AI provider.",
)(doctor.main)
app.command(
    "status",
    help="Show conflicts with origin, testing evidence and a recommendation.",
)(status.main)
app.command(
    "explain",
    help="Plain-English summary of what each side of a conflict does.",
)(explain.main)
app.command(
    "origin",
    help="Show where a commit came from (patch-id, cherry-pick -x, message refs, AST).",
)(origin.main)
app.command(
    "decide",
    help="Record your choice and reason. Saved as pending; writes nothing to git yet.",
)(decide.main)
app.command(
    "commit",
    help="Create a standard git merge commit with trailers, then attach a git note.",
)(commit.main)
app.command("sync", help="Push/pull refs/notes/mergelens.")(sync.main)
app.command("ui", help="Open the local dashboard (127.0.0.1, token-protected).")(ui.main)


if __name__ == "__main__":
    app()
