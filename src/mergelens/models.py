"""Shared Pydantic v2 models.

MergeContext, ConflictHunk, SideInfo, OriginMatch, EvidenceReport,
Recommendation, Decision, and AuditRecord.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


class Side(StrEnum):
    OURS = "ours"
    THEIRS = "theirs"
    BASE = "base"


class Operation(StrEnum):
    MERGE = "merge"
    CHERRY_PICK = "cherry-pick"
    REBASE = "rebase"
    NONE = "none"


class MatchType(StrEnum):
    PATCH_ID = "patch_id"
    CHERRY_PICK_X = "cherry_pick_x"
    MESSAGE_REF = "message_ref"
    HUNK_PATCH_ID = "hunk_patch_id"
    AST_SIMILAR = "ast_similar"


class Status(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    PENDING = "pending"
    UNKNOWN = "unknown"


class Relation(StrEnum):
    EQUIVALENT = "equivalent"
    SUPERSET_OURS = "superset_ours"
    SUPERSET_THEIRS = "superset_theirs"
    COMPLEMENTARY = "complementary"
    CONTRADICTORY = "contradictory"
    UNKNOWN = "unknown"


class Action(StrEnum):
    KEEP_OURS = "KEEP_OURS"
    KEEP_THEIRS = "KEEP_THEIRS"
    COMBINE = "COMBINE"
    NO_CLEAR_WINNER = "NO_CLEAR_WINNER"


T = TypeVar("T")


class Known(BaseModel, Generic[T]):
    """Honest wrapper: holds a value when verified, or unknown when unverified."""

    known: bool = True
    value: T | None = None
    reason: str | None = None

    @classmethod
    def unknown(cls, reason: str = "Unverified") -> Known[T]:
        return cls(known=False, value=None, reason=reason)

    @classmethod
    def of(cls, value: T, reason: str = "Verified") -> Known[T]:
        return cls(known=True, value=value, reason=reason)


class OriginMatch(BaseModel):
    match_type: MatchType
    source_sha: str
    target_sha: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    details: dict[str, Any] = Field(default_factory=dict)


class EvidenceItem(BaseModel):
    status: Status = Status.UNKNOWN
    source: str = "unknown"
    detail: str | None = None


class EvidenceReport(BaseModel):
    sha: str
    prod: EvidenceItem = Field(default_factory=EvidenceItem)
    uat: EvidenceItem = Field(default_factory=EvidenceItem)
    ci: EvidenceItem = Field(default_factory=EvidenceItem)
    ancestry: list[str] = Field(default_factory=list)
    notes_present: bool = False
    trailers: dict[str, str] = Field(default_factory=dict)


class SideInfo(BaseModel):
    side: Side
    sha: str | None = None
    text: str = ""
    lines: list[str] = Field(default_factory=list)
    origin: OriginMatch | None = None
    evidence: EvidenceReport | None = None


class Recommendation(BaseModel):
    action: Action
    confidence: float = Field(ge=0.0, le=1.0)
    score_ours: int = 0
    score_theirs: int = 0
    reasons: list[str] = Field(default_factory=list)


class ConflictHunk(BaseModel):
    hunk_id: str
    path: str
    start_line: int = 1
    ours: SideInfo
    theirs: SideInfo
    base: SideInfo | None = None
    recommendation: Recommendation
    relation: Relation = Relation.UNKNOWN


class MergeContext(BaseModel):
    operation: Operation
    ours: str
    theirs: str
    head: str
    merge_head: str
    conflicted_files: list[str] = Field(default_factory=list)
    is_preview: bool = False


class Decision(BaseModel):
    hunk_id: str
    path: str
    keep: str  # "ours" | "theirs" | "combine" | "custom"
    reason: str
    decided_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class AuditRecord(BaseModel):
    id: str
    commit: str
    when: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    path: str
    hunk_id: str | None = None
    keep: str
    reason: str
    author: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "Side",
    "Operation",
    "MatchType",
    "Status",
    "Relation",
    "Action",
    "Known",
    "OriginMatch",
    "EvidenceItem",
    "EvidenceReport",
    "SideInfo",
    "Recommendation",
    "ConflictHunk",
    "MergeContext",
    "Decision",
    "AuditRecord",
]
