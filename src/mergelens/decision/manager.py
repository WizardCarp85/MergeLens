"""Pending decision manager and commit message composition."""

from __future__ import annotations

import json
from pathlib import Path

from mergelens import NOTES_REF, config
from mergelens.git.runner import run_git
from mergelens.models import AuditRecord, Decision


def get_pending_file(root: Path, merge_head: str) -> Path:
    """Return path to pending decisions JSON in scratch area."""
    cfg = config.load(root)
    pending_dir = cfg.pending_dir
    pending_dir.mkdir(parents=True, exist_ok=True)
    clean_sha = merge_head.strip().replace("/", "_")
    return pending_dir / f"{clean_sha}.json"


def load_pending_decisions(root: Path, merge_head: str) -> list[Decision]:
    """Read pending decisions from scratch area."""
    p = get_pending_file(root, merge_head)
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [Decision.model_validate(item) for item in data]
    except Exception:
        pass
    return []


def save_decision(root: Path, merge_head: str, decision: Decision) -> None:
    """Save or update a pending decision in scratch area."""
    decisions = load_pending_decisions(root, merge_head)
    # Replace decision for same hunk_id if already exists
    filtered = [d for d in decisions if d.hunk_id != decision.hunk_id]
    filtered.append(decision)
    p = get_pending_file(root, merge_head)
    p.write_text(
        json.dumps([d.model_dump() for d in filtered], indent=2),
        encoding="utf-8",
    )


def clear_pending_decisions(root: Path, merge_head: str) -> None:
    """Clear pending decisions for this merge."""
    p = get_pending_file(root, merge_head)
    if p.is_file():
        p.unlink()


def compose_commit_message(
    subject: str,
    body: str,
    decisions: list[Decision],
    ours_sha: str,
    theirs_sha: str,
) -> str:
    """Compose standard Git commit message with Mergelens resolution trailers."""
    lines = [subject.strip(), ""]
    if body.strip():
        lines.append(body.strip())
        lines.append("")

    lines.append("---")
    lines.append("Mergelens-Provenance: verified")
    lines.append(f"Mergelens-Ours: {ours_sha[:12]}")
    lines.append(f"Mergelens-Theirs: {theirs_sha[:12]}")

    for d in decisions:
        lines.append(f"Mergelens-Decision: {d.path}#{d.hunk_id} keep={d.keep} reason=\"{d.reason}\"")

    return "\n".join(lines).strip() + "\n"


def record_audit_notes(root: Path, commit_sha: str, decisions: list[Decision]) -> None:
    """Record audit records in refs/notes/mergelens."""
    for d in decisions:
        audit = AuditRecord(
            id=f"{commit_sha[:8]}-{d.hunk_id}",
            commit=commit_sha,
            path=d.path,
            hunk_id=d.hunk_id,
            keep=d.keep,
            reason=d.reason,
        )
        line = json.dumps(audit.model_dump())
        # Append note using git notes append or add
        res = run_git(
            ["notes", f"--ref={NOTES_REF}", "append", "-m", line, commit_sha],
            cwd=root,
            check=False,
            allow_write=True,
        )
        if not res.ok:
            # Try add if append failed
            run_git(
                ["notes", f"--ref={NOTES_REF}", "add", "-f", "-m", line, commit_sha],
                cwd=root,
                check=False,
                allow_write=True,
            )


def load_audit_records(root: Path) -> list[AuditRecord]:
    """Read all audit records from refs/notes/mergelens."""
    res = run_git(["notes", f"--ref={NOTES_REF}", "list"], cwd=root, check=False)
    if not res.ok or not res.stdout.strip():
        return []

    records = []
    # Each line is "<note_blob_sha> <commit_sha>"
    for line in res.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            note_blob, commit_sha = parts[0], parts[1]
            content_res = run_git(["cat-file", "-p", note_blob], cwd=root, check=False)
            if content_res.ok:
                for chunk in content_res.stdout.splitlines():
                    chunk = chunk.strip()
                    if chunk.startswith("{") and chunk.endswith("}"):
                        try:
                            records.append(AuditRecord.model_validate(json.loads(chunk)))
                        except Exception:
                            pass
    return records
