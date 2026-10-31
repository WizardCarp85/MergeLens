"""`mergelens doctor` — environment check.

Only the checks that need no subprocess are live in steps 1-3; the git checks
switch on once `git/runner.py` exists (step 4).
"""

from __future__ import annotations

import sys
from importlib.util import find_spec
from pathlib import Path

from rich.table import Table

from mergelens import MIN_GIT_VERSION, __version__, config
from mergelens.cli._console import out

_OK, _BAD, _SKIP = "[ok]ok[/ok]", "[bad]fail[/bad]", "[unknown]pending[/unknown]"


def _static_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "server" / "static"


def main() -> None:
    cfg = config.load()
    table = Table(title=f"mergelens {__version__} — doctor", title_justify="left")
    table.add_column("check")
    table.add_column("result")
    table.add_column("detail", overflow="fold")

    py_ok = sys.version_info >= (3, 11)
    table.add_row("python >= 3.11", _OK if py_ok else _BAD, sys.version.split()[0])

    repo_ok = (cfg.root / ".git").exists()
    table.add_row("git repository", _OK if repo_ok else _BAD, str(cfg.root))

    table.add_row(
        "config file",
        _OK if cfg.source_path else "[warn]defaults[/warn]",
        str(cfg.source_path or "no .mergelens.toml — using built-in defaults"),
    )

    ui_ok = find_spec("fastapi") is not None and find_spec("uvicorn") is not None
    table.add_row(
        "dashboard deps",
        _OK if ui_ok else "[warn]missing[/warn]",
        "fastapi + uvicorn" if ui_ok else "install with: pipx inject mergelens 'mergelens[ui]'",
    )

    static = _static_dir()
    built = static.is_dir() and any(p.name == "index.html" for p in static.iterdir())
    table.add_row(
        "dashboard assets",
        _OK if built else "[warn]not built[/warn]",
        str(static) if built else "run: python scripts/build_web.py",
    )

    from mergelens.git.runner import get_git_version, has_notes_rewrite_ref

    want = ".".join(map(str, MIN_GIT_VERSION))
    try:
        git_ver = get_git_version(cfg.root)
        got = ".".join(map(str, git_ver))
        table.add_row(f"git >= {want}", _OK, got)
    except Exception as exc:
        table.add_row(f"git >= {want}", _BAD, str(exc))

    notes_ok = has_notes_rewrite_ref(cfg.root)
    table.add_row(
        "notes.rewriteRef",
        _OK if notes_ok else "[warn]missing[/warn]",
        "configured for refs/notes/mergelens"
        if notes_ok
        else "run: mergelens init",
    )

    out.print(table)
