"""Unit tests for the Audit Workbench and Remediation Lifecycle."""

from __future__ import annotations

import json
import pytest

from audit_readiness_ledger.gates import AccreditationVerdict
from audit_readiness_ledger.workbench import (
    AuditEntry,
    AuditSession,
    AuditState,
    RemediationStatus,
    initialize_blank_session,
)


def test_initialize_blank_session():
    """Verify that a new blank session properly loads all 93 ISO 27001 controls."""
    session = initialize_blank_session()
    assert len(session.entries) == 93
    assert session.unassessed_count == 93
    assert "A.5.1" in session.entries
    assert session.entries["A.5.1"].is_mandatory is True
    assert session.entries["A.5.1"].state is AuditState.UNASSESSED


def test_json_session_roundtrip():
    """Verify complete lossless JSON serialization and deserialization."""
    session = initialize_blank_session()
    session.organization_name = "Acme Financial Services"
    session.auditor_name = "Jane Doe, Lead Auditor"
    session.lessons_learned = "Asset inventory requires automated tooling."

    session.entries["A.7.2"].state = AuditState.NOT_IMPLEMENTED
    session.entries["A.7.2"].root_cause = "Badge reader was decommissioned during office renovation."
    session.entries["A.7.2"].corrective_action = "Install biometric access control lock on server room."
    session.entries["A.7.2"].remediation_owner = "Facilities Manager"
    session.entries["A.7.2"].target_date = "2026-10-15"
    session.entries["A.7.2"].remediation_status = RemediationStatus.IN_PROGRESS

    json_str = session.to_json()
    reloaded = AuditSession.from_json(json_str)

    assert reloaded.organization_name == "Acme Financial Services"
    assert reloaded.auditor_name == "Jane Doe, Lead Auditor"
    assert reloaded.lessons_learned == "Asset inventory requires automated tooling."
    assert reloaded.entries["A.7.2"].state is AuditState.NOT_IMPLEMENTED
    assert reloaded.entries["A.7.2"].remediation_status is RemediationStatus.IN_PROGRESS
    assert reloaded.entries["A.7.2"].remediation_owner == "Facilities Manager"


def test_re_audit_verification_closes_blocker():
    """Verify the re-audit cycle: a verified remediation turns a FAILED verdict into PASSED."""
    session = initialize_blank_session()

    # Mark all controls as FULLY_IMPLEMENTED
    for entry in session.entries.values():
        entry.state = AuditState.FULLY_IMPLEMENTED

    # Introduce 1 mandatory blocker: Physical Entry (A.7.2)
    session.entries["A.7.2"].state = AuditState.NOT_IMPLEMENTED
    session.entries["A.7.2"].remediation_status = RemediationStatus.OPEN

    # First evaluation: must be strictly FAILED
    assessment1, gate_eval1 = session.evaluate_assurance()
    assert gate_eval1.verdict is AccreditationVerdict.FAILED
    assert len(gate_eval1.blockers) == 1
    assert gate_eval1.blockers[0].control_id == "A.7.2"

    # Now, the organization remediates the control and auditor re-audits it:
    session.entries["A.7.2"].remediation_status = RemediationStatus.VERIFIED_CLOSED
    session.entries["A.7.2"].verified_date = "2026-10-16"
    session.entries["A.7.2"].verification_notes = "Physical inspection confirmed new card reader active with tamper alarm."

    # Second evaluation (Re-Audit): blocker is resolved!
    assessment2, gate_eval2 = session.evaluate_assurance()
    assert gate_eval2.verdict is AccreditationVerdict.FULLY_COMPLIANT
    assert len(gate_eval2.blockers) == 0
    assert assessment2.overall_score == 100.0


def test_excluded_control_does_not_penalize_score():
    """Verify that a legitimate Statement of Applicability (SoA) exclusion does not lower the score."""
    session = initialize_blank_session()

    # Mark 92 controls as fully implemented
    for entry in session.entries.values():
        entry.state = AuditState.FULLY_IMPLEMENTED

    # Control A.8.28 (Secure coding) is excluded because organization doesn't develop software
    session.entries["A.8.28"].state = AuditState.NOT_APPLICABLE
    session.entries["A.8.28"].evidence_notes = "Outsourced COTS only; no in-house development."

    assessment, gate_eval = session.evaluate_assurance()

    # Total applicable is 92 out of 93, all 92 are implemented -> 100.0% score
    assert assessment.total_assessed == 92
    assert assessment.overall_score == 100.0
    assert gate_eval.verdict is AccreditationVerdict.FULLY_COMPLIANT
