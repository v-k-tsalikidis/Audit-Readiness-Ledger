"""Turn findings into something a person can act on.

The shape of this report is the argument of the project, so it is worth
saying what it deliberately does not contain.

There is no score and no percentage. A number like "78% compliant" cannot
be checked, cannot be defended to an auditor, and reads as an achievement
when it is really an average of guesses. What replaces it is a list: these
controls are not addressed by any document you gave me, and here is where I
looked.

Counts do appear, because a count is a list length and a reader can verify
it by counting the list. That is a different thing from a rating.

Every section that could mislead by omission states its own limits. The
report says how many controls were examined out of the framework total, how
many documents were read, and which files could not be opened. A reader who
knows 59 of 93 controls were examined can weigh the result. A reader who
assumes all 93 were cannot.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from .documents import Skipped
from .hygiene import HygieneFinding, Status
from .lexicon_loader import Control, Framework
from .signatures import Coverage, Finding


@dataclass(frozen=True)
class Analysis:
    """Everything one run produced."""

    framework: Framework
    findings: tuple[Finding, ...]
    hygiene: tuple[HygieneFinding, ...]
    cross_references: tuple[HygieneFinding, ...]
    documents_read: tuple[str, ...]
    units: dict[str, str]
    skipped: tuple[Skipped, ...]
    source: str
    run_date: date

    @property
    def by_coverage(self) -> dict[Coverage, list[Finding]]:
        grouped: dict[Coverage, list[Finding]] = {c: [] for c in Coverage}
        for finding in self.findings:
            grouped[finding.coverage].append(finding)
        return grouped

    @property
    def examined(self) -> int:
        return sum(1 for f in self.findings if f.coverage is not Coverage.NOT_ASSESSED)

    def title_of(self, control_id: str) -> str:
        for control in self.framework.controls:
            if control.id == control_id:
                return control.title
        return ""

    def control_of(self, control_id: str) -> Control | None:
        for control in self.framework.controls:
            if control.id == control_id:
                return control
        return None


def _cite(analysis: Analysis, document: str, line: int | None) -> str:
    """A citation a reader can follow, in the unit that document actually has."""
    if line is None:
        return document
    unit = analysis.units.get(document, "line")
    return f"{document} {unit} {line}"


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return singular if count == 1 else (plural or singular + "s")


def render_markdown(analysis: Analysis) -> str:
    out: list[str] = []
    grouped = analysis.by_coverage
    total = len(analysis.framework.controls)

    out.append(f"# Audit readiness: {analysis.source}")
    out.append("")
    out.append(
        f"{analysis.framework.name}. Run on {analysis.run_date.isoformat()} against "
        f"{len(analysis.documents_read)} "
        f"{_plural(len(analysis.documents_read), 'document')}."
    )
    out.append("")
    unexamined = total - analysis.examined
    if unexamined:
        out.append(
            f"{analysis.examined} of {total} controls were examined. The other "
            f"{unexamined} have no signature in this tool's lexicon, so nothing "
            f"was looked for and nothing can be concluded about them."
        )
    else:
        out.append(
            f"All {total} controls were examined. Every control in the framework "
            f"has a signature, so none of them was passed over in silence."
        )

    # The headline: what to go and do something about.
    missing = grouped[Coverage.NOT_ADDRESSED]
    out.append("")
    out.append("## Controls no document addresses")
    out.append("")
    if not missing:
        out.append("None. Every control that was examined is mentioned somewhere in the set.")
    else:
        out.append(
            f"{len(missing)} of the {analysis.examined} controls examined are not "
            f"mentioned in any document supplied. These are the usual source of "
            f"audit findings."
        )
        out.append("")
        out.append("| Control | Subject |")
        out.append("| --- | --- |")
        for finding in missing:
            out.append(f"| {finding.control_id} | {analysis.title_of(finding.control_id)} |")

    unclear = grouped[Coverage.UNCLEAR]
    if unclear:
        out.append("")
        out.append("## Controls a person should read")
        out.append("")
        deferred = sum(1 for f in unclear if f.deferred)
        out.append(
            f"{len(unclear)} {_plural(len(unclear), 'control')} the tool will not "
            f"place. Each one is explained below. This is where its judgement runs "
            f"out and yours starts."
        )
        if deferred:
            out.append("")
            out.append(
                f"{deferred} of them are there because the only text on the subject "
                f"says the work is not done, or not done yet. Those are closer to "
                f"gaps than to coverage."
            )
        out.append("")
        for finding in unclear:
            out.append(f"**{finding.control_id} — {analysis.title_of(finding.control_id)}**")
            out.append("")
            if finding.deferred:
                out.append(
                    "Every mention of this subject says it is not done, or not done "
                    "yet. Treat it as a gap until someone confirms otherwise."
                )
            else:
                out.append(
                    "The subject appears, but the document does not go on to say "
                    "what is done about it."
                )
            out.append("")
            for hit in finding.hits[:3]:
                out.append(f"- {_cite(analysis, hit.document, hit.line)}: {hit.excerpt}")
            out.append("")

    addressed = grouped[Coverage.ADDRESSED]
    if addressed:
        out.append("")
        out.append("## Controls the set speaks to")
        out.append("")
        out.append(
            "The documents named below say something on each subject. That is not "
            "the same as the control being implemented, and this tool makes no "
            "claim that it is."
        )
        out.append("")
        out.append("| Control | Subject | Where |")
        out.append("| --- | --- | --- |")
        for finding in addressed:
            where = ", ".join(finding.documents)
            out.append(
                f"| {finding.control_id} | {analysis.title_of(finding.control_id)} | {where} |"
            )

    out.extend(_render_hygiene(analysis))
    out.extend(_render_cross_references(analysis))
    out.extend(_render_skipped(analysis))
    out.extend(_render_unassessed(analysis, grouped[Coverage.NOT_ASSESSED]))
    out.extend(_render_limits(analysis))

    return "\n".join(out).rstrip() + "\n"


def _render_hygiene(analysis: Analysis) -> list[str]:
    problems = [f for f in analysis.hygiene if f.status is not Status.PRESENT]
    if not problems:
        return []

    out = ["", "## Document hygiene", ""]
    out.append(
        f"{len(problems)} {_plural(len(problems), 'point')} about the documents "
        f"themselves rather than what they cover."
    )
    out.append("")

    stale = [f for f in problems if f.status is Status.STALE]
    if stale:
        out.append("### Reviews that are overdue")
        out.append("")
        for finding in stale:
            out.append(
                f"- **{finding.document}** — {finding.detail} "
                f"({_cite(analysis, finding.document, finding.line)})"
            )
        out.append("")

    odd = [f for f in problems if f.status in {Status.AMBIGUOUS, Status.UNPARSED}]
    if odd:
        out.append("### Dates that need rewriting")
        out.append("")
        for finding in odd:
            out.append(
                f"- **{finding.document}** — {finding.detail} "
                f"({_cite(analysis, finding.document, finding.line)})"
            )
        out.append("")

    absent = [f for f in problems if f.status is Status.MISSING]
    if absent:
        out.append("### Fields not filled in")
        out.append("")
        out.append("| Document | Missing |")
        out.append("| --- | --- |")
        by_document: dict[str, list[str]] = {}
        for finding in absent:
            by_document.setdefault(finding.document, []).append(finding.check)
        for document in sorted(by_document):
            out.append(f"| {document} | {', '.join(by_document[document])} |")

    return out


def _render_cross_references(analysis: Analysis) -> list[str]:
    if not analysis.cross_references:
        return []
    out = ["", "## Documents referred to but not supplied", ""]
    out.append(
        "Each of these is either a document that exists and was not included in "
        "the folder, or one that was never written. An auditor will ask which."
    )
    out.append("")
    for finding in analysis.cross_references:
        out.append(f"- {_cite(analysis, finding.document, finding.line)}: {finding.detail}")
    return out


def _render_skipped(analysis: Analysis) -> list[str]:
    if not analysis.skipped:
        return []
    out = ["", "## Files that could not be read", ""]
    out.append(
        "Nothing in these was examined, so any control they cover will appear "
        "above as not addressed. Convert them and run again before treating the "
        "gap list as complete."
    )
    out.append("")
    for skipped in analysis.skipped:
        out.append(f"- `{skipped.path}` — {skipped.reason}")
    return out


def _render_unassessed(analysis: Analysis, unassessed: list[Finding]) -> list[str]:
    if not unassessed:
        return []
    out = ["", "## Controls this tool did not examine", ""]
    out.append(
        f"The lexicon has no signature for these {len(unassessed)} controls. They "
        f"are listed so the silence is visible: their absence from the gap list "
        f"above means nothing was checked, not that nothing is wrong."
    )
    out.append("")
    ids = ", ".join(f.control_id for f in unassessed)
    out.append(ids)
    return out


def _render_limits(analysis: Analysis) -> list[str]:
    return [
        "",
        "## What this report does not say",
        "",
        (
            "It does not say any control is met. Matching words in a document shows "
            "the subject was written about; whether the words are true of the "
            "organisation, and whether what they describe is adequate, are judgements "
            "only a person can make."
        ),
        "",
        "It does not score or rate anything, and it produces no percentage.",
        "",
        (
            "It reads only the documents in the folder given to it. Evidence held "
            "elsewhere -- tickets, logs, screenshots, records in a system -- is "
            "outside what it can see."
        ),
        "",
        (
            "Where a document names a subject only to say the work is not done, or "
            "not done yet, that is reported as something to read rather than as "
            "coverage. The tool does not decide it; it refuses to hide it."
        ),
        "",
        (
            f"The same folder and the same lexicon produce the same report every "
            f"time, so two runs can be compared directly. Only the run date "
            f"({analysis.run_date.isoformat()}) and anything derived from it will "
            f"differ."
        ),
    ]


def render_json(analysis: Analysis) -> str:
    """Machine-readable output, with the same refusals as the Markdown."""
    payload = {
        "source": analysis.source,
        "framework": analysis.framework.name,
        "run_date": analysis.run_date.isoformat(),
        "documents_read": list(analysis.documents_read),
        "controls_in_framework": len(analysis.framework.controls),
        "controls_examined": analysis.examined,
        "claims_no_control_is_met": True,
        "produces_no_score": True,
        "controls": [
            {
                "id": finding.control_id,
                "title": analysis.title_of(finding.control_id),
                "coverage": finding.coverage.value,
                "only_deferral_language": finding.deferred,
                "documents": list(finding.documents),
                "evidence": [
                    {
                        "document": hit.document,
                        "unit": analysis.units.get(hit.document, "line"),
                        "position": hit.line,
                        "term": hit.term,
                        "excerpt": hit.excerpt,
                    }
                    for hit in finding.hits
                ],
            }
            for finding in analysis.findings
        ],
        "hygiene": [
            {
                "document": finding.document,
                "check": finding.check,
                "status": finding.status.value,
                "detail": finding.detail,
                "position": finding.line,
            }
            for finding in analysis.hygiene
            if finding.status is not Status.PRESENT
        ],
        "cross_references": [
            {
                "document": finding.document,
                "detail": finding.detail,
                "position": finding.line,
            }
            for finding in analysis.cross_references
        ],
        "skipped": [{"path": str(s.path), "reason": s.reason} for s in analysis.skipped],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
