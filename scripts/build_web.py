#!/usr/bin/env python3
"""Build/sync script for dashboard static assets.

Copies web/out (or runs npm run build if needed) into
src/mergelens/server/static/ for wheel packaging and FastAPI serving.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_OUT = ROOT / "web" / "out"
STATIC_DIR = ROOT / "src" / "mergelens" / "server" / "static"


def main() -> int:
    if not WEB_OUT.is_dir() or not (WEB_OUT / "index.html").is_file():
        print(f"Error: {WEB_OUT} does not exist or lacks index.html. Build web first.", file=sys.stderr)
        return 1

    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    for item in STATIC_DIR.iterdir():
        if item.name == ".gitkeep":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    for item in WEB_OUT.iterdir():
        dest = STATIC_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    print(f"Synced {WEB_OUT} -> {STATIC_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

