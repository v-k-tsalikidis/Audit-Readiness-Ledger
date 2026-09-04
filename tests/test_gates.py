"""Tests for deterministic accreditation gates and assurance scoring."""

from __future__ import annotations

from audit_readiness_ledger.gates import (
    AccreditationVerdict,
    evaluate_gates,
)
from audit_readiness_ledger.lexicon_loader import Control, Framework
from audit_readiness_ledger.scoring import score_assessment
from audit_readiness_ledger.signatures import Coverage, Finding, TermHit


def dummy_finding(control_id: str, coverage: Coverage, deferred: bool = False) -> Finding:
    hits = (
        (TermHit(term="test", document="doc.md", line=1, excerpt="..."),)
        if coverage is Coverage.ADDRESSED
        else ()
    )
    docs = ("doc.md",) if coverage is Coverage.ADDRESSED else ()
    return Finding(
        control_id=control_id,
        coverage=coverage,
        documents=docs,
        hits=hits,
        groups_matched=2 if coverage is Coverage.ADDRESSED else 0,
        groups_required=2,
        deferred=deferred,
    )


def test_mandatory_blocker_fails_even_with_high_overall_compliance():
    """Verify that a single missing mandatory control forces a FAILED verdict."""
    mandatory_set = frozenset({"A.5.1", "A.7.2", "A.8.24"})

    # Suppose 99 controls are addressed, but A.7.2 (Physical entry - mandatory) is missing!
    findings = [
        dummy_finding("A.5.1", Coverage.ADDRESSED),
        dummy_finding("A.8.24", Coverage.ADDRESSED),
        dummy_finding("A.7.2", Coverage.NOT_ADDRESSED),  # MANDATORY BLOCKER
    ]
    # Add 97 desirable controls, all addressed
    for i in range(1, 98):
        findings.append(dummy_finding(f"A.99.{i}", Coverage.ADDRESSED))

    eval_result = evaluate_gates(findings, mandatory_control_ids=mandatory_set)

    # 99 out of 100 controls are addressed (99% compliance!), but verdict is FAILED
    assert eval_result.verdict is AccreditationVerdict.FAILED
    assert len(eval_result.blockers) == 1
    assert eval_result.blockers[0].control_id == "A.7.2"
    assert "FAILED: 1 MANDATORY GATE BLOCKERS" in eval_result.verdict_label


def test_missing_desirable_controls_pass_with_observations():
    """Verify that missing desirable controls produce PASSED WITH OBSERVATIONS."""
    mandatory_set = frozenset({"A.5.1", "A.8.24"})

    findings = [
        dummy_finding("A.5.1", Coverage.ADDRESSED),
        dummy_finding("A.8.24", Coverage.ADDRESSED),
        dummy_finding("A.5.8", Coverage.NOT_ADDRESSED),  # Desirable control missing
        dummy_finding("A.8.12", Coverage.NOT_ADDRESSED),  # Desirable control missing
    ]

    eval_result = evaluate_gates(findings, mandatory_control_ids=mandatory_set)

    # All mandatory are addressed, so it passes, but with observations
    assert eval_result.verdict is AccreditationVerdict.PASSED_WITH_OBSERVATIONS
    assert len(eval_result.blockers) == 0
    assert len(eval_result.observations) == 2
    assert eval_result.mandatory_pass_rate == 100.0
    assert eval_result.desirable_pass_rate == 0.0


def test_fully_compliant_verdict():
    """Verify that 100% satisfaction produces FULLY_COMPLIANT."""
    mandatory_set = frozenset({"A.5.1"})

    findings = [
        dummy_finding("A.5.1", Coverage.ADDRESSED),
        dummy_finding("A.5.2", Coverage.ADDRESSED),
    ]

    eval_result = evaluate_gates(findings, mandatory_control_ids=mandatory_set)

    assert eval_result.verdict is AccreditationVerdict.FULLY_COMPLIANT
    assert len(eval_result.blockers) == 0
    assert len(eval_result.observations) == 0


def test_scoring_engine_aggregation():
    """Test theme aggregation and overall score computation."""
    controls = (
        Control(id="A.5.1", title="Policies", grouping="Organizational controls"),
        Control(id="A.5.2", title="Roles", grouping="Organizational controls"),
        Control(id="A.8.1", title="Endpoints", grouping="Technological controls"),
    )
    framework = Framework(name="Test ISO 27001", controls=controls, licence="Apache-2.0")

    findings = [
        dummy_finding("A.5.1", Coverage.ADDRESSED),
        dummy_finding("A.5.2", Coverage.UNCLEAR),
        dummy_finding("A.8.1", Coverage.NOT_ADDRESSED),
    ]

    # 1 addressed (1.0), 1 unclear (0.5), 1 not addressed (0.0) -> 1.5 / 3 = 50.0%
    assessment = score_assessment(findings, framework, mandatory_control_ids=frozenset({"A.5.1"}))

    assert assessment.overall_score == 50.0
    assert assessment.overall_strict_score == 33.3  # 1/3
    assert assessment.theme_scores["Organizational controls"].addressed == 1
    assert assessment.theme_scores["Organizational controls"].unclear == 1
    assert assessment.theme_scores["Technological controls"].not_addressed == 1
    assert assessment.gate_evaluation.verdict is AccreditationVerdict.PASSED_WITH_OBSERVATIONS
