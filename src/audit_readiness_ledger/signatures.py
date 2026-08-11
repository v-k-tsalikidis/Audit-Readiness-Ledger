"""Deterministic matching of control signatures against document text.

The design rests on one decision, and everything else follows from it: the
tool reports that a control is **not addressed**, and never that a control
is satisfied. Absence is something a lexicon can establish. Adequacy is a
judgement about whether the words are true of the organisation, and no
matcher can see that.

So a match here means "this document set says something on this subject",
which is a claim that can be checked by opening the document at the line
cited. It is deliberately weaker than "this control is met".

Matching is exact-term and case-insensitive, on word boundaries. There is
no stemming and no fuzzy distance, because both make results hard to
predict and impossible to explain to an auditor. Word variants are written
out in the lexicon instead, where they can be read and argued with.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class Coverage(Enum):
    """What the document set says about a control.

    Four states, and the fourth matters as much as the others.
    NOT_ASSESSED means this tool has no signature for the control, so it
    looked at nothing. Reporting that as a gap would blame the user for a
    limitation of the lexicon, which is the fastest way for a tool like
    this to lose the reader's trust.

    A two-state result would also force every partial signal into either
    covered or missing, and the partial ones are exactly where a person
    needs to look.
    """

    ADDRESSED = "addressed"
    UNCLEAR = "unclear"
    NOT_ADDRESSED = "not addressed"
    NOT_ASSESSED = "not assessed"


@dataclass(frozen=True)
class TermHit:
    """One term found in one place, kept so a finding can be checked."""

    term: str
    document: str
    line: int
    excerpt: str


@dataclass(frozen=True)
class Signature:
    """What a document must say for a control to count as addressed.

    The first group is the subject and is mandatory. The rest describe
    what is being done about it, and `required_groups` counts how many
    groups in total must be satisfied within the same document.

    Making the subject mandatory is not a refinement, it is the thing that
    stops the lexicon producing noise. Without it a control whose second
    group holds ordinary verbs -- retained, reviewed, approved -- fires on
    any document containing one of them. In testing, "Backup retention is
    30 days" raised a partial match against the logging control purely on
    the word "retention". The subject was absent, so the control should
    never have been considered at all.

    `disqualifiers` remove a hit when the term is being used in another
    sense. "log" in a document about logistics is the obvious case.
    """

    control_id: str
    anchor_groups: tuple[frozenset[str], ...]
    required_groups: int = 2
    supporting: frozenset[str] = field(default_factory=frozenset)
    disqualifiers: frozenset[str] = field(default_factory=frozenset)
    note: str = ""

    def __post_init__(self) -> None:
        if not self.anchor_groups:
            raise ValueError(f"{self.control_id}: needs at least one anchor group")
        if self.required_groups < 1:
            raise ValueError(f"{self.control_id}: required_groups must be at least 1")
        if self.required_groups > len(self.anchor_groups):
            raise ValueError(
                f"{self.control_id}: requires {self.required_groups} groups but "
                f"only {len(self.anchor_groups)} are defined, so it can never match"
            )


@dataclass(frozen=True)
class Finding:
    """The result for one control, with the evidence behind it."""

    control_id: str
    coverage: Coverage
    documents: tuple[str, ...]
    hits: tuple[TermHit, ...]
    groups_matched: int
    groups_required: int
    deferred: bool = False

    @property
    def explanation(self) -> str:
        if self.coverage is Coverage.NOT_ASSESSED:
            return "No signature is defined for this control, so it was not examined."
        if self.coverage is Coverage.NOT_ADDRESSED:
            return "No document in the set mentions this subject."
        subject = "subject" if self.groups_matched == 1 else "subjects"
        where = ", ".join(self.documents)
        if self.deferred:
            return (
                f"The subject appears in {where}, but every mention says it is "
                f"not done, or not done yet. Read it before treating this as covered."
            )
        if self.coverage is Coverage.UNCLEAR:
            return (
                f"{self.groups_matched} of {self.groups_required} required "
                f"{subject} found, in {where}. A person should read it."
            )
        return f"Addressed in {where}."


# Terms are matched whole. Without this, "log" matches "logistics" and
# "access" matches "accessory", which is how a lexicon quietly stops
# meaning anything.
def _pattern(term: str) -> re.Pattern[str]:
    escaped = re.escape(term.lower())
    # Allow the term to be followed by common suffixes only when the
    # lexicon did not already spell out the variant it wants.
    return re.compile(rf"(?<![\w-]){escaped}(?![\w-])", re.IGNORECASE)


_PATTERN_CACHE: dict[str, re.Pattern[str]] = {}


def pattern_for(term: str) -> re.Pattern[str]:
    if term not in _PATTERN_CACHE:
        _PATTERN_CACHE[term] = _pattern(term)
    return _PATTERN_CACHE[term]


def _excerpt(text: str, limit: int = 160) -> str:
    """One line of context, whitespace normalised, short enough to read."""
    flattened = " ".join(text.split())
    return flattened if len(flattened) <= limit else flattened[: limit - 3] + "..."


@dataclass(frozen=True)
class Document:
    """A document reduced to what the matcher needs."""

    name: str
    lines: tuple[str, ...]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def find(self, term: str) -> list[TermHit]:
        """Every place this term appears, with enough context to check it.

        Documents are hard-wrapped, and a wrap lands wherever the width
        runs out -- including in the middle of "change management". Reading
        one line at a time would report that document as never mentioning
        change management at all, which is a false gap and worse than no
        finding.

        So a multi-word term is also matched across each pair of adjacent
        lines. Two lines is enough, because a wrap only ever splits a term
        at one point, and stopping at two keeps the rule bounded: no term
        can be assembled out of text that was paragraphs apart.
        """
        regex = pattern_for(term)
        hits: list[TermHit] = []
        matched_alone: set[int] = set()

        for number, line in enumerate(self.lines, start=1):
            if regex.search(line):
                matched_alone.add(number)
                hits.append(TermHit(term, self.name, number, _excerpt(line)))

        if " " not in term.strip():
            return hits

        for number in range(1, len(self.lines)):
            first, second = self.lines[number - 1], self.lines[number]
            if number in matched_alone or number + 1 in matched_alone:
                continue
            joined = first.rstrip() + " " + second.lstrip()
            if regex.search(joined):
                hits.append(TermHit(term, self.name, number, _excerpt(joined)))

        hits.sort(key=lambda hit: hit.line)
        return hits


def _disqualified(document: Document, signature: Signature, hit: TermHit) -> bool:
    """True when the line carrying the hit shows the term means something else."""
    if not signature.disqualifiers:
        return False
    line = document.lines[hit.line - 1]
    return any(pattern_for(word).search(line) for word in signature.disqualifiers)


# A sentence can name a subject and in the same breath say the organisation
# does not do it. "Vulnerability scanning was discussed with the supplier
# but has not started" mentions vulnerability management and admits there is
# none. Counting that as addressed keeps a real gap out of the gap list,
# which is the one failure this tool cannot afford.
#
# The list is deliberately narrow. A bare "not" would catch "USB devices
# that are not company issued are prohibited", which is a control, not an
# absence. Only forms that postpone or deny the activity itself are here.
DEFERRAL = re.compile(
    r"\b(?:"
    r"ha(?:s|ve)\s+not\s+(?:started|begun|been\s+\w+)"
    r"|(?:is|are|was|were)\s+not\s+(?:yet\s+)?(?:in\s+place|implemented|defined|documented|established)"
    r"|not\s+yet"
    r"|no\s+formal"
    r"|there\s+is\s+(?:currently\s+)?no\b"
    r"|(?:do|does)\s+not\s+currently"
    # "planned for next year" postpones. "planned in advance" is the
    # opposite -- it describes a control working as intended -- so the
    # phrase alone is not enough and a future time has to follow it.
    r"|planned\s+for\s+(?:next|later|the\s+(?:next|coming|following)|20\d\d|q[1-4]\b)"
    r"|will\s+be\s+(?:implemented|developed|introduced|written|defined)"
    r"|to\s+be\s+(?:implemented|developed|introduced|written|defined)"
    r"|under\s+discussion"
    r"|on\s+the\s+list\s+for"
    r")",
    re.IGNORECASE,
)


def _is_deferral(line: str) -> bool:
    return bool(DEFERRAL.search(line))


def _dedupe(hits: list[TermHit]) -> list[TermHit]:
    """One citation per place. Several terms hitting one line is one place.

    Without this a reader is shown the same sentence twice under the same
    control and reasonably concludes the tool is broken.
    """
    seen: set[tuple[str, int]] = set()
    kept: list[TermHit] = []
    for hit in hits:
        key = (hit.document, hit.line)
        if key in seen:
            continue
        seen.add(key)
        kept.append(hit)
    return kept


def evaluate(signature: Signature, documents: list[Document]) -> Finding:
    """Decide what the set says about one control.

    Groups must be satisfied within a single document. Two documents each
    mentioning half the subject do not together describe a procedure, and
    treating them as if they did is how a gap gets hidden.
    """
    best_matched = 0
    best_hits: list[TermHit] = []
    matching_documents: list[str] = []
    deferred_only = False

    for document in documents:
        matched_groups = 0
        document_hits: list[TermHit] = []
        subject_hits: list[TermHit] = []
        subject_found = False
        for index, group in enumerate(signature.anchor_groups):
            group_hits: list[TermHit] = []
            for term in sorted(group):
                group_hits.extend(
                    hit
                    for hit in document.find(term)
                    if not _disqualified(document, signature, hit)
                )
            if group_hits:
                matched_groups += 1
                document_hits.extend(group_hits)
                if index == 0:
                    subject_found = True
                    subject_hits = group_hits

        # No subject, no finding. A supporting verb on its own says nothing.
        if not subject_found:
            continue

        document_hits = _dedupe(document_hits)

        # Every place this document names the subject says the thing is not
        # done, or not done yet. It cannot be what addresses the control.
        defers = all(_is_deferral(document.lines[hit.line - 1]) for hit in subject_hits)

        if matched_groups >= signature.required_groups and not defers:
            matching_documents.append(document.name)
            best_hits.extend(document_hits)
            best_matched = max(best_matched, matched_groups)
        elif matched_groups > best_matched and not matching_documents:
            best_matched = matched_groups
            best_hits = document_hits
            deferred_only = defers
        elif defers and not matching_documents and not best_hits:
            best_matched = matched_groups
            best_hits = document_hits
            deferred_only = True

    if matching_documents:
        coverage = Coverage.ADDRESSED
        deferred_only = False
    elif best_matched > 0:
        coverage = Coverage.UNCLEAR
        matching_documents = sorted({hit.document for hit in best_hits})
    else:
        coverage = Coverage.NOT_ADDRESSED
        deferred_only = False

    return Finding(
        control_id=signature.control_id,
        coverage=coverage,
        documents=tuple(sorted(set(matching_documents))),
        hits=tuple(_dedupe(best_hits)),
        groups_matched=best_matched,
        groups_required=signature.required_groups,
        deferred=deferred_only,
    )


def not_assessed(control_id: str) -> Finding:
    """A control the lexicon does not cover yet."""
    return Finding(
        control_id=control_id,
        coverage=Coverage.NOT_ASSESSED,
        documents=(),
        hits=(),
        groups_matched=0,
        groups_required=0,
    )


def evaluate_all(
    control_ids: list[str],
    signatures: dict[str, Signature],
    documents: list[Document],
) -> list[Finding]:
    """Evaluate every control in the catalogue, in catalogue order.

    Iteration is over the catalogue rather than over the lexicon, so a
    control with no signature is reported as unexamined instead of
    silently vanishing from the report.
    """
    return [
        evaluate(signatures[cid], documents) if cid in signatures else not_assessed(cid)
        for cid in control_ids
    ]
