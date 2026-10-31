"""Deterministic scoring engine for merge conflict decisions.

Calculates score for OURS and THEIRS from testing provenance and origin,
and produces a recommended Action plus explanatory reasons.
"""

from __future__ import annotations

from mergelens.config import ScoringConfig
from mergelens.models import (
    Action,
    EvidenceReport,
    MatchType,
    OriginMatch,
    Recommendation,
    Relation,
    Status,
)


def compute_side_score(
    evidence: EvidenceReport | None,
    origin: OriginMatch | None,
    cfg: ScoringConfig,
) -> tuple[int, list[str]]:
    """Compute score for one side based on its testing evidence and origin."""
    score = 0
    reasons: list[str] = []

    if not evidence:
        return score, reasons

    # Production testing
    if evidence.prod.status == Status.PASS:
        score += cfg.prod
        reasons.append(f"+{cfg.prod} Running/tested in production ({evidence.prod.source})")

    # UAT testing
    if evidence.uat.status == Status.PASS:
        score += cfg.uat_pass
        reasons.append(f"+{cfg.uat_pass} Passed UAT testing ({evidence.uat.source})")
    elif evidence.uat.status == Status.FAIL:
        score += cfg.uat_fail
        reasons.append(f"{cfg.uat_fail} Failed UAT testing ({evidence.uat.source})")

    # CI testing
    if evidence.ci.status == Status.PASS:
        score += cfg.ci_pass
        reasons.append(f"+{cfg.ci_pass} Passed CI tests ({evidence.ci.source})")
    elif evidence.ci.status == Status.FAIL:
        score += cfg.ci_fail
        reasons.append(f"{cfg.ci_fail} Failed CI tests ({evidence.ci.source})")

    # Origin provenance
    if origin:
        score += cfg.provenance
        reasons.append(f"+{cfg.provenance} Provenance verified: {origin.reason}")
        if origin.match_type in {MatchType.PATCH_ID, MatchType.CHERRY_PICK_X}:
            score += cfg.mainline_patch
            reasons.append(
                f"+{cfg.mainline_patch} Origin matches upstream commit {origin.source_sha[:8]}"
            )

    return score, reasons


def evaluate_recommendation(
    score_ours: int,
    score_theirs: int,
    reasons_ours: list[str],
    reasons_theirs: list[str],
    relation: Relation = Relation.UNKNOWN,
    cfg: ScoringConfig = ScoringConfig(),
) -> Recommendation:
    """Determine action based on delta between sides and relation."""
    delta = score_theirs - score_ours
    reasons = []
    confidence = 0.5

    for r in reasons_ours:
        reasons.append(f"Ours: {r}")
    for r in reasons_theirs:
        reasons.append(f"Theirs: {r}")

    if delta >= cfg.clear_winner_delta:
        action = Action.KEEP_THEIRS
        confidence = min(0.95, 0.65 + (delta / 100.0))
        reasons.insert(
            0, f"THEIRS is the clear winner (+{delta} points ahead: superior testing provenance)."
        )
    elif delta <= -cfg.clear_winner_delta:
        action = Action.KEEP_OURS
        confidence = min(0.95, 0.65 + (abs(delta) / 100.0))
        reasons.insert(
            0,
            f"OURS is the clear winner (+{abs(delta)} points ahead: superior testing provenance).",
        )
    else:
        if relation == Relation.EQUIVALENT:
            action = Action.KEEP_OURS
            confidence = 0.90
            reasons.insert(
                0, "Both sides are semantically equivalent. Retaining OURS avoids churn."
            )
        elif relation in {Relation.COMPLEMENTARY, Relation.SUPERSET_OURS, Relation.SUPERSET_THEIRS}:
            action = Action.COMBINE
            confidence = 0.75
            reasons.insert(
                0, "Both sides contain distinct valid changes. Recommendation: combine both."
            )
        else:
            action = Action.NO_CLEAR_WINNER
            confidence = 0.50
            reasons.insert(
                0, "No clear winner based on testing provenance. Manual inspection required."
            )

    return Recommendation(
        action=action,
        confidence=round(confidence, 2),
        score_ours=score_ours,
        score_theirs=score_theirs,
        reasons=reasons,
    )
