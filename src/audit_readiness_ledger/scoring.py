"""Quantitative scoring and structured gap analysis for Audit-Readiness-Ledger.

Calculates maturity metrics across framework domains while preserving audit traceability
and feeding the deterministic gatekeeper.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .gates import GateClass, GateEvaluation, evaluate_gates
from .lexicon_loader import Framework
from .signatures import Coverage, Finding


@dataclass(frozen=True)
class ThemeScore:
    """Quantitative completion metric for one framework theme/domain."""

    theme: str
    total: int
    addressed: int
    unclear: int
    not_addressed: int
    not_assessed: int

    @property
    def score_percentage(self) -> float:
        """Percentage of addressed controls over assessed controls."""
        assessed = self.total - self.not_assessed
        if assessed == 0:
            return 0.0
        # Weighted: Addressed = 100%, Unclear = 50%
        points = self.addressed + (0.5 * self.unclear)
        return round((points / assessed) * 100.0, 1)

    @property
    def strict_percentage(self) -> float:
        """Strict percentage: only fully addressed controls count."""
        assessed = self.total - self.not_assessed
        if assessed == 0:
            return 0.0
        return round((self.addressed / assessed) * 100.0, 1)


@dataclass(frozen=True)
class ScoredFinding:
    """Detailed finding with control metadata, gate classification, and severity."""

    control_id: str
    title: str
    theme: str
    clause: str
    coverage: Coverage
    gate_class: GateClass
    is_satisfied: bool
    is_blocker: bool
    documents: tuple[str, ...]
    explanation: str


@dataclass(frozen=True)
class AssuranceAssessment:
    """Complete quantitative and deterministic assurance result."""

    framework_name: str
    total_controls: int
    total_assessed: int
    overall_score: float
    overall_strict_score: float
    gate_evaluation: GateEvaluation
    theme_scores: dict[str, ThemeScore]
    scored_findings: tuple[ScoredFinding, ...]

    @property
    def blockers_count(self) -> int:
        return len(self.gate_evaluation.blockers)

    @property
    def observations_count(self) -> int:
        return len(self.gate_evaluation.observations)


def score_assessment(
    findings: Sequence[Finding],
    framework: Framework,
    mandatory_control_ids: frozenset[str] | None = None,
) -> AssuranceAssessment:
    """Compute theme-level metrics, overall maturity scores, and gate verdicts."""
    gate_kwargs = {}
    if mandatory_control_ids is not None:
        gate_kwargs["mandatory_control_ids"] = mandatory_control_ids

    gate_eval = evaluate_gates(findings, **gate_kwargs)
    gate_class_map = {gf.finding.control_id: gf.gate_class for gf in gate_eval.gate_findings}

    # Map controls by ID from framework
    controls_map = {c.id: c for c in framework.controls}

    # Theme aggregations
    theme_counts: dict[str, dict[str, int]] = {}
    scored_list: list[ScoredFinding] = []

    total_assessed = 0
    total_addressed = 0
    total_unclear = 0

    for finding in findings:
        ctrl = controls_map.get(finding.control_id)
        theme = ctrl.grouping if ctrl else "Other"
        title = ctrl.title if ctrl else finding.control_id
        clause = finding.control_id.rsplit(".", 1)[0] if "." in finding.control_id else ""

        if theme not in theme_counts:
            theme_counts[theme] = {
                "total": 0,
                "addressed": 0,
                "unclear": 0,
                "not_addressed": 0,
                "not_assessed": 0,
            }

        theme_counts[theme]["total"] += 1

        if finding.coverage is Coverage.ADDRESSED:
            theme_counts[theme]["addressed"] += 1
            total_addressed += 1
            total_assessed += 1
        elif finding.coverage is Coverage.UNCLEAR:
            theme_counts[theme]["unclear"] += 1
            total_unclear += 1
            total_assessed += 1
        elif finding.coverage is Coverage.NOT_ADDRESSED:
            theme_counts[theme]["not_addressed"] += 1
            total_assessed += 1
        elif finding.coverage is Coverage.NOT_ASSESSED:
            theme_counts[theme]["not_assessed"] += 1

        g_class = gate_class_map.get(finding.control_id, GateClass.DESIRABLE)
        is_sat = finding.coverage is Coverage.ADDRESSED and not finding.deferred
        is_blk = g_class is GateClass.MANDATORY and not is_sat

        scored_list.append(
            ScoredFinding(
                control_id=finding.control_id,
                title=title,
                theme=theme,
                clause=clause,
                coverage=finding.coverage,
                gate_class=g_class,
                is_satisfied=is_sat,
                is_blocker=is_blk,
                documents=finding.documents,
                explanation=finding.explanation,
            )
        )

    # Build ThemeScores
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

    overall_score = (
        round(((total_addressed + 0.5 * total_unclear) / total_assessed) * 100.0, 1)
        if total_assessed > 0
        else 0.0
    )
    overall_strict_score = (
        round((total_addressed / total_assessed) * 100.0, 1) if total_assessed > 0 else 0.0
    )

    return AssuranceAssessment(
        framework_name=framework.name,
        total_controls=len(framework.controls),
        total_assessed=total_assessed,
        overall_score=overall_score,
        overall_strict_score=overall_strict_score,
        gate_evaluation=gate_eval,
        theme_scores=theme_scores,
        scored_findings=tuple(scored_list),
    )
