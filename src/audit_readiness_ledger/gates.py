"""Accreditation Gatekeeper for security frameworks (ISO/IEC 27001:2022).

Separates compliance verification into two distinct axes:
1. Quantitative Maturity Score (percentage of controls addressed)
2. Deterministic Accreditation Gate (Pass / Fail based on mandatory prerequisites)

In a rigorous audit or security accreditation (e.g. NATO SCIF, ISO 27001 certification),
a high overall percentage (e.g. 95%) does not grant certification if a single
mandatory prerequisite is missing (e.g. Physical perimeter, Incident response, Cryptography).
Conversely, missing non-mandatory / desirable controls results in PASSED WITH OBSERVATIONS.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from .signatures import Coverage, Finding


class GateClass(Enum):
    """Classification of a control within an accreditation framework."""

    MANDATORY = "mandatory"      # Hard gate: failure blocks accreditation (BLOCKER)
    DESIRABLE = "desirable"      # Soft gate: failure yields an observation / action item


class AccreditationVerdict(Enum):
    """Overall outcome of the accreditation assessment."""

    FULLY_COMPLIANT = "fully_compliant"               # 100% of all applicable controls met
    PASSED_WITH_OBSERVATIONS = "passed_observations"  # 100% of mandatory met, some desirable gaps
    FAILED = "failed"                                 # >= 1 mandatory controls unmet (BLOCKER)


# Canonical ISO/IEC 27001:2022 Annex A baseline mandatory controls.
# These represent baseline non-negotiable security safeguards in enterprise/defense environments.
ISO_27001_DEFAULT_MANDATORY_CONTROLS: frozenset[str] = frozenset({
    # Governance & Foundational
    "A.5.1",   # Policies for information security
    "A.5.2",   # Information security roles and responsibilities
    "A.5.4",   # Management responsibilities
    "A.5.9",   # Inventory of information and other associated assets
    "A.5.10",  # Acceptable use of information and other associated assets
    "A.5.12",  # Classification of information
    "A.5.15",  # Access control
    "A.5.24",  # Information security incident management planning and preparation
    "A.5.25",  # Assessment and decision on information security events
    "A.5.26",  # Response to information security incidents
    "A.5.31",  # Legal, statutory, regulatory and contractual requirements

    # People Security
    "A.6.3",   # Information security awareness, education and training

    # Physical Security
    "A.7.1",   # Physical security perimeters
    "A.7.2",   # Physical entry

    # Technological Security
    "A.8.1",   # User endpoint devices
    "A.8.2",   # Privileged access rights
    "A.8.5",   # Secure authentication
    "A.8.7",   # Protection against malware
    "A.8.15",  # Logging
    "A.8.16",  # Monitoring activities
    "A.8.20",  # Network security
    "A.8.24",  # Use of cryptography
})


@dataclass(frozen=True)
class GateFinding:
    """A finding paired with its accreditation gate classification."""

    finding: Finding
    gate_class: GateClass

    @property
    def is_satisfied(self) -> bool:
        """A control is satisfied for the gate if it is addressed and not deferred."""
        return self.finding.coverage is Coverage.ADDRESSED and not self.finding.deferred

    @property
    def is_blocker(self) -> bool:
        """Returns True if this is a mandatory control that is NOT satisfied."""
        return self.gate_class is GateClass.MANDATORY and not self.is_satisfied


@dataclass(frozen=True)
class GateEvaluation:
    """The evaluated state of all accreditation gates."""

    verdict: AccreditationVerdict
    total_mandatory: int
    satisfied_mandatory: int
    total_desirable: int
    satisfied_desirable: int
    blockers: tuple[Finding, ...]
    observations: tuple[Finding, ...]
    gate_findings: tuple[GateFinding, ...]

    @property
    def mandatory_pass_rate(self) -> float:
        if self.total_mandatory == 0:
            return 100.0
        return round((self.satisfied_mandatory / self.total_mandatory) * 100.0, 1)

    @property
    def desirable_pass_rate(self) -> float:
        if self.total_desirable == 0:
            return 100.0
        return round((self.satisfied_desirable / self.total_desirable) * 100.0, 1)

    @property
    def verdict_label(self) -> str:
        if self.verdict is AccreditationVerdict.FULLY_COMPLIANT:
            return "PASSED: FULLY COMPLIANT"
        if self.verdict is AccreditationVerdict.PASSED_WITH_OBSERVATIONS:
            return "PASSED: WITH OBSERVATIONS"
        return f"FAILED: {len(self.blockers)} MANDATORY GATE BLOCKERS"


def evaluate_gates(
    findings: Sequence[Finding],
    mandatory_control_ids: frozenset[str] = ISO_27001_DEFAULT_MANDATORY_CONTROLS,
) -> GateEvaluation:
    """Evaluate accreditation findings against deterministic mandatory gates.

    Rule 1: If ANY mandatory control is not satisfied -> FAILED.
    Rule 2: If all mandatory controls are satisfied, but >=1 desirable control is not -> PASSED_WITH_OBSERVATIONS.
    Rule 3: If all controls are satisfied -> FULLY_COMPLIANT.
    """
    gate_findings: list[GateFinding] = []
    blockers: list[Finding] = []
    observations: list[Finding] = []

    satisfied_mandatory = 0
    total_mandatory = 0
    satisfied_desirable = 0
    total_desirable = 0

    for finding in findings:
        # Ignore NOT_ASSESSED from gate metrics
        if finding.coverage is Coverage.NOT_ASSESSED:
            continue

        gate_class = (
            GateClass.MANDATORY
            if finding.control_id in mandatory_control_ids
            else GateClass.DESIRABLE
        )
        gf = GateFinding(finding=finding, gate_class=gate_class)
        gate_findings.append(gf)

        if gate_class is GateClass.MANDATORY:
            total_mandatory += 1
            if gf.is_satisfied:
                satisfied_mandatory += 1
            else:
                blockers.append(finding)
        else:
            total_desirable += 1
            if gf.is_satisfied:
                satisfied_desirable += 1
            else:
                observations.append(finding)

    if blockers:
        verdict = AccreditationVerdict.FAILED
    elif observations:
        verdict = AccreditationVerdict.PASSED_WITH_OBSERVATIONS
    else:
        verdict = AccreditationVerdict.FULLY_COMPLIANT

    return GateEvaluation(
        verdict=verdict,
        total_mandatory=total_mandatory,
        satisfied_mandatory=satisfied_mandatory,
        total_desirable=total_desirable,
        satisfied_desirable=satisfied_desirable,
        blockers=tuple(blockers),
        observations=tuple(observations),
        gate_findings=tuple(gate_findings),
    )
