"""FastAPI backend sidecar for the MergeLens dashboard."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from mergelens import config
from mergelens.cli.status import build_status_hunks
from mergelens.decision.manager import load_audit_records, save_decision
from mergelens.evidence.collector import collect_evidence, get_timeline
from mergelens.git.ops import get_merge_context
from mergelens.models import Decision

security = HTTPBearer(auto_error=False)


def create_app(token: str | None = None, static_dir: Path | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    expected_token = token or os.environ.get("MERGELENS_TOKEN") or secrets.token_urlsafe(24)
    app = FastAPI(title="MergeLens API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
        if not credentials or credentials.credentials != expected_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing bearer token.",
            )
        return credentials.credentials

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "service": "mergelens", "status": "running"}

    @app.get("/api/context")
    async def get_context(credentials: str = Depends(verify_token)) -> dict[str, Any]:
        cfg = config.load()
        try:
            ctx, hunks = build_status_hunks(cfg)
            return ctx.model_dump(mode="json")
        except Exception as exc:
            # Fallback if no active merge: return empty context
            return {
                "operation": "none",
                "ours": "HEAD",
                "theirs": "—",
                "head": "",
                "merge_head": "",
                "conflicted_files": [],
                "detail": str(exc),
            }

    @app.get("/api/hunks")
    async def get_hunks(credentials: str = Depends(verify_token)) -> list[dict[str, Any]]:
        cfg = config.load()
        try:
            _, hunks = build_status_hunks(cfg)
            return [h.model_dump(mode="json") for h in hunks]
        except Exception:
            return []

    @app.get("/api/hunks/{hunk_id:path}")
    async def get_hunk(hunk_id: str, credentials: str = Depends(verify_token)) -> dict[str, Any]:
        cfg = config.load()
        try:
            _, hunks = build_status_hunks(cfg)
            for h in hunks:
                if h.hunk_id == hunk_id:
                    return h.model_dump(mode="json")
        except Exception:
            pass
        raise HTTPException(status_code=404, detail=f"Hunk {hunk_id} not found.")

    @app.get("/api/evidence/{sha}")
    async def get_evidence_endpoint(
        sha: str, credentials: str = Depends(verify_token)
    ) -> dict[str, Any]:
        cfg = config.load()
        report = collect_evidence(cfg.root, sha, cfg)
        return report.model_dump(mode="json")

    @app.get("/api/timeline/{sha}")
    async def get_timeline_endpoint(
        sha: str, credentials: str = Depends(verify_token)
    ) -> list[dict[str, Any]]:
        cfg = config.load()
        return get_timeline(cfg.root, sha)

    @app.get("/api/audit")
    async def get_audit_endpoint(credentials: str = Depends(verify_token)) -> list[dict[str, Any]]:
        cfg = config.load()
        records = load_audit_records(cfg.root)
        return [r.model_dump(mode="json") for r in records]

    @app.post("/api/decisions")
    async def post_decision(
        decision: Decision, credentials: str = Depends(verify_token)
    ) -> dict[str, Any]:
        cfg = config.load()
        try:
            ctx = get_merge_context(cfg.root)
            merge_head = ctx.merge_head_sha
        except Exception:
            merge_head = "MERGE_HEAD"
        save_decision(cfg.root, merge_head, decision)
        return {"ok": True, "saved": decision.model_dump(mode="json")}

    # Static file serving
    resolved_static = static_dir or (Path(__file__).resolve().parent / "static")
    if resolved_static.is_dir():
        # Serve Next.js static export
        @app.get("/{full_path:path}")
        async def serve_static(full_path: str) -> FileResponse:
            clean = full_path.strip("/")
            # API requests that reached here are 404
            if clean.startswith("api/"):
                raise HTTPException(status_code=404, detail="API route not found")

            # Try candidate files
            candidates = [
                resolved_static / clean,
                resolved_static / f"{clean}.html",
                resolved_static / clean / "index.html",
            ]
            for c in candidates:
                if c.is_file():
                    return FileResponse(c)

            index_file = resolved_static / "index.html"
            if index_file.is_file():
                return FileResponse(index_file)

            raise HTTPException(status_code=404, detail="File not found")

    return app
