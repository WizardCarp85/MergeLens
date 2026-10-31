"""Tests for Origin detection, Evidence collection, and Scoring engine."""

from mergelens.config import ScoringConfig
from mergelens.evidence.collector import parse_trailers
from mergelens.models import (
    Action,
    EvidenceItem,
    EvidenceReport,
    MatchType,
    OriginMatch,
    Relation,
    Status,
)
from mergelens.origin.detector import (
    CHERRY_PICK_X_RE,
    DJANGO_BACKPORT_RE,
    find_l4_ast_similarity_match,
)
from mergelens.scoring.engine import compute_side_score, evaluate_recommendation


def test_cherry_pick_x_regex():
    msg = """Fix bug in parser\n\n(cherry picked from commit 7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b)"""
    m = CHERRY_PICK_X_RE.search(msg)
    assert m is not None
    assert m.group(1) == "7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b"


def test_django_backport_regex():
    msg = """Backport of 4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d from main.\n\nTicket #32401."""
    m = DJANGO_BACKPORT_RE.search(msg)
    assert m is not None
    assert m.group(1) == "4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d"


def test_ast_similarity():
    code_a = """
    def calculate_tax(amount: float) -> float:
        rate = 0.15
        return amount * rate
    """
    code_b = """
    def calculate_tax(amount: float) -> float:
        # standard rate calculation
        tax_rate = 0.15
        return amount * tax_rate
    """
    match = find_l4_ast_similarity_match(code_a, code_b, "abc1234", "def5678")
    assert match is not None
    assert match.match_type == MatchType.AST_SIMILAR
    assert match.confidence >= 0.70


def test_trailer_parsing():
    msg = """Feature commit\n\nTested-by: QA Team\nProd: verified\nUAT: pass\nCI: pass\n"""
    trailers = parse_trailers(msg)
    assert trailers["tested-by"] == "QA Team"
    assert trailers["prod"] == "verified"
    assert trailers["uat"] == "pass"


def test_scoring_production_winner():
    cfg = ScoringConfig()

    evidence_theirs = EvidenceReport(
        sha="theirs_sha",
        prod=EvidenceItem(status=Status.PASS, source="ancestry (origin/production)"),
        uat=EvidenceItem(status=Status.PASS, source="trailers"),
        ci=EvidenceItem(status=Status.PASS, source="trailers"),
    )
    origin_theirs = OriginMatch(
        match_type=MatchType.CHERRY_PICK_X,
        source_sha="upstream_sha",
        target_sha="theirs_sha",
        confidence=0.98,
        reason="cherry-pick -x",
    )

    evidence_ours = EvidenceReport(
        sha="ours_sha",
        prod=EvidenceItem(status=Status.UNKNOWN, source="unverified"),
        uat=EvidenceItem(status=Status.UNKNOWN, source="unverified"),
        ci=EvidenceItem(status=Status.PASS, source="trailers"),
    )

    score_theirs, reasons_theirs = compute_side_score(evidence_theirs, origin_theirs, cfg)
    score_ours, reasons_ours = compute_side_score(evidence_ours, None, cfg)

    # Theirs: 45 (prod) + 25 (uat) + 15 (ci) + 5 (provenance) + 10 (mainline) = 100
    assert score_theirs == 100
    # Ours: 15 (ci) = 15
    assert score_ours == 15

    rec = evaluate_recommendation(
        score_ours=score_ours,
        score_theirs=score_theirs,
        reasons_ours=reasons_ours,
        reasons_theirs=reasons_theirs,
        cfg=cfg,
    )

    assert rec.action == Action.KEEP_THEIRS
    assert rec.score_theirs == 100
    assert rec.score_ours == 15
    assert "THEIRS is the clear winner" in rec.reasons[0]

