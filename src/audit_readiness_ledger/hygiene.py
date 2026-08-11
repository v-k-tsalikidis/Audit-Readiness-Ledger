"""Checks on the documents themselves, rather than on what they cover.

These are the findings auditors raise that have nothing to do with the
subject matter. A policy nobody owns. A procedure whose review date passed
two years ago. A document that refers to another one which does not exist
in the set. None of them need a language model, and all of them are
embarrassing to be told about by an auditor rather than by yourself.

Two decisions shape the module.

**Today is passed in, never read from the clock.** A test that calls
`date.today()` starts failing on a date nobody chose, and a report that
cannot be reproduced tomorrow is not evidence.

**An ambiguous date is reported as ambiguous.** "05/03/2027" is 5 March in
Greece and 3 May in the United States, and a document set often contains
both conventions. Guessing silently would put a wrong date in an audit
file, so the parser reads day-first and says when the other reading was
also possible.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from enum import Enum

from .signatures import Document


class Status(Enum):
    PRESENT = "present"
    MISSING = "missing"
    STALE = "stale"
    AMBIGUOUS = "ambiguous"
    UNPARSED = "unparsed"


@dataclass(frozen=True)
class HygieneFinding:
    document: str
    check: str
    status: Status
    detail: str
    line: int | None = None
    excerpt: str = ""


# Labels are matched at the start of a line or straight after a table
# pipe, because that is where a document control block puts them. Matching
# them anywhere would catch "the owner of the system is responsible", which
# is prose, not metadata.
_LABEL_SEPARATOR = r"\s*[:|\t]\s*"

FIELD_LABELS: dict[str, tuple[str, ...]] = {
    "owner": (
        "document owner",
        "owner",
        "policy owner",
        "process owner",
        "ιδιοκτήτης",
        "υπεύθυνος",
    ),
    "approver": ("approved by", "approver", "authorised by", "authorized by", "εγκρίθηκε από"),
    "version": ("version", "revision", "έκδοση", "αναθεώρηση"),
    "approved_on": (
        "approval date",
        "approved on",
        "date approved",
        "effective date",
        "ημερομηνία έγκρισης",
    ),
    "next_review": (
        "next review",
        "review date",
        "review due",
        "next review date",
        "επόμενη αναθεώρηση",
    ),
    "classification": ("classification", "confidentiality", "sensitivity", "διαβάθμιση"),
}

# A field is only meaningful when it has a value. These are the ways a
# template says "nobody filled this in".
PLACEHOLDERS = {
    "",
    "-",
    "--",
    "n/a",
    "na",
    "tbd",
    "tbc",
    "todo",
    "xxx",
    "<name>",
    "[name]",
    "to be confirmed",
    "to be defined",
    "pending",
    "none",
}

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
    # Greek month names appear in Greek document sets, in genitive form.
    "ιανουαριου": 1,
    "φεβρουαριου": 2,
    "μαρτιου": 3,
    "απριλιου": 4,
    "μαιου": 5,
    "ιουνιου": 6,
    "ιουλιου": 7,
    "αυγουστου": 8,
    "σεπτεμβριου": 9,
    "οκτωβριου": 10,
    "νοεμβριου": 11,
    "δεκεμβριου": 12,
}

ISO_DATE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
NUMERIC_DATE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b")
WRITTEN_DATE = re.compile(r"\b(\d{1,2})\s+([^\W\d_]{3,12})\s+(\d{4})\b", re.UNICODE)


@dataclass(frozen=True)
class ParsedDate:
    value: date
    ambiguous: bool
    raw: str


def _fold(text: str) -> str:
    """Lower-case and strip Greek accents so month names match either way."""
    lowered = text.lower()
    decomposed = unicodedata.normalize("NFD", lowered)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def parse_date(text: str) -> ParsedDate | None:
    """Read the first date in a string, day-first where the format allows.

    Returns None rather than a guess when nothing parses, so a caller can
    tell "no date here" from "a date I could not read".
    """
    match = ISO_DATE.search(text)
    if match:
        year, month, day = (int(g) for g in match.groups())
        try:
            return ParsedDate(date(year, month, day), False, match.group(0))
        except ValueError:
            return None

    match = NUMERIC_DATE.search(text)
    if match:
        first, second, year = (int(g) for g in match.groups())
        # Day-first is the European convention and this tool is used there.
        # When both readings are valid the finding says so.
        ambiguous = first <= 12 and second <= 12 and first != second
        day, month = (first, second) if first > 12 or second <= 12 else (second, first)
        try:
            return ParsedDate(date(year, month, day), ambiguous, match.group(0))
        except ValueError:
            return None

    match = WRITTEN_DATE.search(text)
    if match:
        day_text, name, year_text = match.group(1), _fold(match.group(2)), match.group(3)
        if name in MONTHS:
            try:
                return ParsedDate(
                    date(int(year_text), MONTHS[name], int(day_text)), False, match.group(0)
                )
            except ValueError:
                return None
    return None


def _label_pattern(label: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?:^|\|)\s*{re.escape(label)}{_LABEL_SEPARATOR}(.+?)\s*(?:\||$)",
        re.IGNORECASE,
    )


def find_field(document: Document, field: str) -> tuple[str, int, str] | None:
    """First labelled value for a field, with the line it came from."""
    for number, line in enumerate(document.lines, start=1):
        for label in FIELD_LABELS[field]:
            match = _label_pattern(label).search(line)
            if not match:
                continue
            value = match.group(1).strip()
            if _fold(value) in PLACEHOLDERS:
                continue
            return value, number, " ".join(line.split())
    return None


def check_document(document: Document, today: date) -> list[HygieneFinding]:
    """Every hygiene finding for one document, in a stable order."""
    findings: list[HygieneFinding] = []

    for field, human in (
        ("owner", "owner"),
        ("approver", "approver"),
        ("version", "version"),
        ("approved_on", "approval date"),
        ("classification", "classification"),
    ):
        found = find_field(document, field)
        if found is None:
            findings.append(
                HygieneFinding(
                    document.name,
                    human,
                    Status.MISSING,
                    f"No {human} is stated anywhere in the document.",
                )
            )
        else:
            value, line, excerpt = found
            findings.append(
                HygieneFinding(document.name, human, Status.PRESENT, value, line, excerpt)
            )

    findings.append(_check_review_date(document, today))
    return findings


def _check_review_date(document: Document, today: date) -> HygieneFinding:
    """The check that finds documents everyone forgot about."""
    found = find_field(document, "next_review")
    if found is None:
        return HygieneFinding(
            document.name,
            "next review",
            Status.MISSING,
            "No review date is stated, so nothing says when this is due to be looked at again.",
        )

    value, line, excerpt = found
    parsed = parse_date(value)
    if parsed is None:
        return HygieneFinding(
            document.name,
            "next review",
            Status.UNPARSED,
            f"A review date is stated as {value!r} but it could not be read as a date.",
            line,
            excerpt,
        )

    if parsed.value < today:
        overdue = (today - parsed.value).days
        return HygieneFinding(
            document.name,
            "next review",
            Status.STALE,
            f"The review was due on {parsed.value.isoformat()}, {overdue} days ago.",
            line,
            excerpt,
        )

    if parsed.ambiguous:
        return HygieneFinding(
            document.name,
            "next review",
            Status.AMBIGUOUS,
            f"{parsed.raw!r} reads as {parsed.value.isoformat()} day-first, but "
            f"the other convention is also possible. Write it as YYYY-MM-DD.",
            line,
            excerpt,
        )

    return HygieneFinding(
        document.name,
        "next review",
        Status.PRESENT,
        parsed.value.isoformat(),
        line,
        excerpt,
    )


# A reference is a document name in quotes, in title case, or after the
# word "see". Anything looser matches ordinary prose.
REFERENCE = re.compile(
    r"(?:see|refer to|described in|defined in|documented in|specified in|set out in"
    r"|as per|in accordance with|governed by|follows?|according to)\s+"
    r"(?:the\s+)?([A-Z][\w-]*(?:\s+[A-Z][\w-]*){1,5}\s+"
    r"(?:Policy|Procedure|Standard|Guideline|Instruction|Plan|Register))",
)


def check_cross_references(documents: list[Document]) -> list[HygieneFinding]:
    """Documents pointing at documents that are not in the set.

    A procedure that says "as described in the Access Control Policy" when
    no such document was supplied is either an incomplete submission or a
    document that was never written. An auditor will ask which, and it is
    better to know first.
    """
    titles = set()
    for document in documents:
        titles.add(
            _fold(document.name.rsplit("/", 1)[-1].rsplit(".", 1)[0])
            .replace("-", " ")
            .replace("_", " ")
        )
        # Only real headings. Treating every early line as a title made a
        # sentence containing a reference resolve that reference against
        # itself, so nothing was ever reported missing.
        for line in document.lines[:12]:
            stripped = line.strip()
            if stripped.startswith("#"):
                heading = stripped.lstrip("#").strip()
                if heading:
                    titles.add(_fold(heading))

    findings: list[HygieneFinding] = []
    for document in documents:
        seen: set[str] = set()
        for number, line in enumerate(document.lines, start=1):
            for match in REFERENCE.finditer(line):
                target = match.group(1).strip()
                folded = _fold(target)
                if folded in seen:
                    continue
                if any(folded in title or title in folded for title in titles if title):
                    continue
                seen.add(folded)
                findings.append(
                    HygieneFinding(
                        document.name,
                        "cross-reference",
                        Status.MISSING,
                        f"Refers to {target!r}, which is not among the documents supplied.",
                        number,
                        " ".join(line.split()),
                    )
                )
    return findings
