"""`mergelens ui` — local dashboard."""

from __future__ import annotations

import secrets
import socket
import webbrowser
from typing import Annotated

import typer
import uvicorn
from rich.panel import Panel

from mergelens.cli._console import err, out
from mergelens.server.app import create_app


def _find_free_port() -> int:
    """Find an available port on 127.0.0.1."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def main(
    port: Annotated[int, typer.Option("--port", "-p", help="0 = pick a free port.")] = 0,
    open_browser: Annotated[bool, typer.Option("--browser/--no-browser")] = True,
) -> None:
    """Serves the static dashboard export plus a read-mostly JSON API
    on 127.0.0.1, guarded by a one-time bearer token.
    """
    bind_port = port if port > 0 else _find_free_port()
    token = secrets.token_urlsafe(24)

    dashboard_url = f"http://127.0.0.1:{bind_port}/#token={token}"

    out.print(Panel(
        f"[bold green]MergeLens Dashboard running at:[/bold green]\n"
        f"[cyan]{dashboard_url}[/cyan]\n\n"
        f"Guarded by local token in URL hash. Press Ctrl+C to stop.",
        title="mergelens ui",
        title_align="left",
    ))

    if open_browser:
        try:
            webbrowser.open(dashboard_url)
        except Exception:
            pass

    app = create_app(token=token)
    try:
        uvicorn.run(app, host="127.0.0.1", port=bind_port, log_level="warning")
    except KeyboardInterrupt:
        out.print("\n[ok]MergeLens dashboard stopped.[/ok]")
