"""Audit Workbench & Remediation Lifecycle Engine.

Provides an interactive data model for on-site auditing, Statement of Applicability (SoA)
management, session persistence (JSON/CSV), and the complete Corrective Action Plan (CAP)
remediation lifecycle.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date
from enum import Enum
from typing import Any

from .gates import (
    ISO_27001_DEFAULT_MANDATORY_CONTROLS,
    AccreditationVerdict,
    GateClass,
    GateEvaluation,
    GateFinding,
)
from .lexicon_loader import Framework, load_framework
from .scoring import AssuranceAssessment, ScoredFinding, ThemeScore
from .signatures import Coverage, Finding, TermHit


class AuditState(Enum):
    """Explicit 5-state audit assessment taxonomy.

    Eliminates ambiguity between unreviewed omissions and intentional exclusions.
    """

    UNASSESSED = "unassessed"                      # Pending review / not yet audited
    FULLY_IMPLEMENTED = "fully_implemented"        # 100% compliant and verified
    PARTIALLY_IMPLEMENTED = "partially_implemented"# In progress / compensating control
    NOT_IMPLEMENTED = "not_implemented"            # Clear non-conformity (Blocker if mandatory)
    NOT_APPLICABLE = "not_applicable"              # Formally excluded via Statement of Applicability


class RemediationStatus(Enum):
    """Remediation and re-audit verification lifecycle."""

    NOT_APPLICABLE = "not_applicable"   # Control is satisfied or excluded
    OPEN = "open"                       # Non-conformity identified, no plan yet
    IN_PROGRESS = "in_progress"         # Corrective action assigned and underway
    PENDING_RE_AUDIT = "pending_re_audit"# Remediation reported complete, awaiting re-test
    VERIFIED_CLOSED = "verified_closed" # Auditor verified remediation; control re-tested compliant


@dataclass
class AuditEntry:
    """Audit evaluation, observation, and remediation record for a single control."""

    control_id: str
    title: str
    theme: str
    clause: str
    is_mandatory: bool = True
    state: AuditState = AuditState.UNASSESSED
    evidence_notes: str = ""
    root_cause: str = ""
    corrective_action: str = ""
    remediation_owner: str = ""
    target_date: str = ""
    remediation_status: RemediationStatus = RemediationStatus.NOT_APPLICABLE
    verification_notes: str = ""
    verified_date: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "control_id": self.control_id,
            "title": self.title,
            "theme": self.theme,
            "clause": self.clause,
            "is_mandatory": self.is_mandatory,
            "state": self.state.value,
            "evidence_notes": self.evidence_notes,
            "root_cause": self.root_cause,
            "corrective_action": self.corrective_action,
            "remediation_owner": self.remediation_owner,
            "target_date": self.target_date,
            "remediation_status": self.remediation_status.value,
            "verification_notes": self.verification_notes,
            "verified_date": self.verified_date,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditEntry:
        return cls(
            control_id=data["control_id"],
            title=data.get("title", ""),
            theme=data.get("theme", ""),
            clause=data.get("clause", ""),
            is_mandatory=data.get("is_mandatory", True),
            state=AuditState(data.get("state", AuditState.UNASSESSED.value)),
            evidence_notes=data.get("evidence_notes", ""),
            root_cause=data.get("root_cause", ""),
            corrective_action=data.get("corrective_action", ""),
            remediation_owner=data.get("remediation_owner", ""),
            target_date=data.get("target_date", ""),
            remediation_status=RemediationStatus(
                data.get("remediation_status", RemediationStatus.NOT_APPLICABLE.value)
            ),
            verification_notes=data.get("verification_notes", ""),
            verified_date=data.get("verified_date", ""),
        )


@dataclass
class AuditSession:
    """Complete portable audit assessment session with session-level metadata."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    organization_name: str = "Target Organization"
    auditor_name: str = "Lead Auditor"
    audit_date: str = field(default_factory=lambda: date.today().isoformat())
    framework_name: str = "ISO/IEC 27001:2022 Annex A"
    entries: dict[str, AuditEntry] = field(default_factory=dict)
    lessons_learned: str = ""

    @property
    def unassessed_count(self) -> int:
        return sum(1 for e in self.entries.values() if e.state is AuditState.UNASSESSED)

    @property
    def implemented_count(self) -> int:
        return sum(1 for e in self.entries.values() if e.state is AuditState.FULLY_IMPLEMENTED)

    @property
    def partial_count(self) -> int:
        return sum(1 for e in self.entries.values() if e.state is AuditState.PARTIALLY_IMPLEMENTED)

    @property
    def not_implemented_count(self) -> int:
        return sum(1 for e in self.entries.values() if e.state is AuditState.NOT_IMPLEMENTED)

    @property
    def excluded_count(self) -> int:
        return sum(1 for e in self.entries.values() if e.state is AuditState.NOT_APPLICABLE)

    @property
    def open_remediations_count(self) -> int:
        return sum(
            1
            for e in self.entries.values()
            if e.remediation_status in {RemediationStatus.OPEN, RemediationStatus.IN_PROGRESS, RemediationStatus.PENDING_RE_AUDIT}
        )

    @property
    def verified_closed_remediations_count(self) -> int:
        return sum(
            1
            for e in self.entries.values()
            if e.remediation_status is RemediationStatus.VERIFIED_CLOSED
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "organization_name": self.organization_name,
            "auditor_name": self.auditor_name,
            "audit_date": self.audit_date,
            "framework_name": self.framework_name,
            "lessons_learned": self.lessons_learned,
            "entries": {cid: entry.to_dict() for cid, entry in self.entries.items()},
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditSession:
        entries = {
            cid: AuditEntry.from_dict(edata)
            for cid, edata in data.get("entries", {}).items()
        }
        return cls(
            session_id=data.get("session_id", str(uuid.uuid4())[:8]),
            organization_name=data.get("organization_name", "Target Organization"),
            auditor_name=data.get("auditor_name", "Lead Auditor"),
            audit_date=data.get("audit_date", date.today().isoformat()),
            framework_name=data.get("framework_name", "ISO/IEC 27001:2022 Annex A"),
            entries=entries,
            lessons_learned=data.get("lessons_learned", ""),
        )

    @classmethod
    def from_json(cls, json_str: str) -> AuditSession:
        data = json.loads(json_str)
        return cls.from_dict(data)

    def to_csv(self) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Control ID",
            "Title",
            "Theme",
            "Mandatory Gate",
            "Audit State",
            "Evidence / Exclusion Justification",
            "Root Cause",
            "Corrective Action",
            "Owner",
            "Target Date",
            "Remediation Status",
            "Verified Date",
            "Verification Notes",
        ])
        for cid, e in sorted(self.entries.items()):
            writer.writerow([
                e.control_id,
                e.title,
                e.theme,
                "YES" if e.is_mandatory else "NO",
                e.state.value.upper(),
                e.evidence_notes,
                e.root_cause,
                e.corrective_action,
                e.remediation_owner,
                e.target_date,
                e.remediation_status.value.upper(),
                e.verified_date,
                e.verification_notes,
            ])
        return output.getvalue()

    def evaluate_assurance(self) -> tuple[AssuranceAssessment, GateEvaluation]:
        """Convert workbench entries into deterministic gate evaluation and scoring."""
        findings: list[Finding] = []
        gate_findings: list[GateFinding] = []
        blockers: list[Finding] = []
        observations: list[Finding] = []

        total_mandatory = 0
        satisfied_mandatory = 0
        total_desirable = 0
        satisfied_desirable = 0

        theme_counts: dict[str, dict[str, int]] = {}
        scored_findings: list[ScoredFinding] = []

        total_applicable = 0
        total_points = 0.0
        strict_points = 0.0

        for cid, entry in self.entries.items():
            theme = entry.theme or "Other"
            if theme not in theme_counts:
                theme_counts[theme] = {
                    "total": 0,
                    "addressed": 0,
                    "unclear": 0,
                    "not_addressed": 0,
                    "not_assessed": 0,
                }
            theme_counts[theme]["total"] += 1

            # Excluded controls (Not Applicable) do not penalize the score if justified
            if entry.state is AuditState.NOT_APPLICABLE:
                theme_counts[theme]["not_assessed"] += 1
                coverage = Coverage.NOT_ASSESSED
                # Map to Finding
                f = Finding(
                    control_id=cid,
                    coverage=coverage,
                    documents=(),
                    hits=(),
                    groups_matched=0,
                    groups_required=0,
                )
                findings.append(f)
                continue

            total_applicable += 1
            gate_class = GateClass.MANDATORY if entry.is_mandatory else GateClass.DESIRABLE

            # If re-audit verified closed, treat as fully implemented
            effective_state = entry.state
            if entry.remediation_status is RemediationStatus.VERIFIED_CLOSED:
                effective_state = AuditState.FULLY_IMPLEMENTED

            is_satisfied = effective_state is AuditState.FULLY_IMPLEMENTED

            if effective_state is AuditState.FULLY_IMPLEMENTED:
                coverage = Coverage.ADDRESSED
                theme_counts[theme]["addressed"] += 1
                total_points += 1.0
                strict_points += 1.0
            elif effective_state is AuditState.PARTIALLY_IMPLEMENTED:
                coverage = Coverage.UNCLEAR
                theme_counts[theme]["unclear"] += 1
                total_points += 0.5
            else:
                coverage = Coverage.NOT_ADDRESSED
                theme_counts[theme]["not_addressed"] += 1

            hits: tuple[TermHit, ...] = ()
            if entry.evidence_notes:
                hits = (TermHit(term="Auditor Note", document="Workbench", line=1, excerpt=entry.evidence_notes),)

            f = Finding(
                control_id=cid,
                coverage=coverage,
                documents=("Workbench",) if entry.evidence_notes else (),
                hits=hits,
                groups_matched=2 if is_satisfied else (1 if effective_state is AuditState.PARTIALLY_IMPLEMENTED else 0),
                groups_required=2,
            )
            findings.append(f)

            gf = GateFinding(finding=f, gate_class=gate_class)
            gate_findings.append(gf)

            if gate_class is GateClass.MANDATORY:
                total_mandatory += 1
                if is_satisfied:
                    satisfied_mandatory += 1
                else:
                    blockers.append(f)
            else:
                total_desirable += 1
                if is_satisfied:
                    satisfied_desirable += 1
                else:
                    observations.append(f)

            scored_findings.append(
                ScoredFinding(
                    control_id=cid,
                    title=entry.title,
                    theme=theme,
                    clause=entry.clause,
                    coverage=coverage,
                    gate_class=gate_class,
                    is_satisfied=is_satisfied,
                    is_blocker=(gate_class is GateClass.MANDATORY and not is_satisfied),
                    documents=("Workbench",) if entry.evidence_notes else (),
                    explanation=entry.evidence_notes or ("Excluded via SoA" if entry.state is AuditState.NOT_APPLICABLE else f"Status: {entry.state.value}"),
                )
            )

        if blockers:
            verdict = AccreditationVerdict.FAILED
        elif observations:
            verdict = AccreditationVerdict.PASSED_WITH_OBSERVATIONS
        else:
            verdict = AccreditationVerdict.FULLY_COMPLIANT

        gate_eval = GateEvaluation(
            verdict=verdict,
            total_mandatory=total_mandatory,
            satisfied_mandatory=satisfied_mandatory,
            total_desirable=total_desirable,
            satisfied_desirable=satisfied_desirable,
            blockers=tuple(blockers),
            observations=tuple(observations),
            gate_findings=tuple(gate_findings),
        )

        theme_scores: dict[str, ThemeScore] = {}
        for theme_name, counts in theme_counts.items():
            theme_scores[theme_name] = ThemeScore(
                theme=theme_name,
                total=counts["total"],
                addressed=counts["addressed"],
                unclear=counts["unclear"],
                not_addressed=counts["not_addressed"],
                not_assessed=counts["not_assessed"],
            )

        overall_score = round((total_points / total_applicable) * 100.0, 1) if total_applicable > 0 else 0.0
        overall_strict_score = round((strict_points / total_applicable) * 100.0, 1) if total_applicable > 0 else 0.0

        assessment = AssuranceAssessment(
            framework_name=self.framework_name,
            total_controls=len(self.entries),
            total_assessed=total_applicable,
            overall_score=overall_score,
            overall_strict_score=overall_strict_score,
            gate_evaluation=gate_eval,
            theme_scores=theme_scores,
            scored_findings=tuple(scored_findings),
        )

        return assessment, gate_eval


def initialize_blank_session(
    framework_slug: str = "iso-27001-2022",
    mandatory_control_ids: frozenset[str] = ISO_27001_DEFAULT_MANDATORY_CONTROLS,
) -> AuditSession:
    """Create a new blank session populated with all controls from the framework catalogue."""
    framework = load_framework(framework_slug)
    entries: dict[str, AuditEntry] = {}
    for ctrl in framework.controls:
        clause = ctrl.id.rsplit(".", 1)[0] if "." in ctrl.id else ""
        is_mand = ctrl.id in mandatory_control_ids
        entries[ctrl.id] = AuditEntry(
            control_id=ctrl.id,
            title=ctrl.title,
            theme=ctrl.grouping,
            clause=clause,
            is_mandatory=is_mand,
            state=AuditState.UNASSESSED,
        )

    return AuditSession(
        framework_name=framework.name,
        entries=entries,
    )
