"""Load control signatures from the lexicon and check them against the catalogue.

Two mistakes are easy to make in a file like the lexicon and expensive to
find later: writing a signature for a control identifier that does not
exist, and writing one that can never match because it asks for more
groups than it defines. Both are caught here, at load time, rather than
showing up as a quietly wrong report.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from .signatures import Signature

PACKAGE = Path(__file__).resolve().parent
CATALOGUE = PACKAGE / "catalogue"
LEXICON = PACKAGE / "lexicon"


@dataclass(frozen=True)
class Control:
    """One control from a published catalogue."""

    id: str
    title: str
    grouping: str


@dataclass(frozen=True)
class Framework:
    name: str
    controls: tuple[Control, ...]
    licence: str

    @property
    def ids(self) -> list[str]:
        return [control.id for control in self.controls]


def load_framework(slug: str) -> Framework:
    """Read a generated catalogue file."""
    data = json.loads((CATALOGUE / f"{slug}.json").read_text(encoding="utf-8"))
    controls = []
    for entry in data["controls"]:
        controls.append(
            Control(
                id=entry["id"],
                # CSF carries its outcome text; ISO carries only a short title.
                title=entry.get("title") or entry.get("text", ""),
                grouping=entry.get("theme") or entry.get("category", ""),
            )
        )
    return Framework(
        name=data["framework"],
        controls=tuple(controls),
        licence=data.get("licence", ""),
    )


def load_signatures(slug: str, framework: Framework) -> dict[str, Signature]:
    """Read the lexicon and refuse anything that cannot be true."""
    path = LEXICON / f"{slug}.yaml"
    if not path.exists():
        return {}

    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw = document.get("signatures") or {}
    known = set(framework.ids)

    signatures: dict[str, Signature] = {}
    problems: list[str] = []

    for control_id, entry in raw.items():
        if control_id not in known:
            problems.append(
                f"{control_id}: not a control in {framework.name}. "
                f"A signature for a control that does not exist can never fire."
            )
            continue
        groups = tuple(
            frozenset(term.strip().lower() for term in group if term.strip())
            for group in entry.get("anchors", [])
        )
        if not groups or any(not group for group in groups):
            problems.append(f"{control_id}: has an empty anchor group")
            continue
        try:
            signatures[control_id] = Signature(
                control_id=control_id,
                anchor_groups=groups,
                required_groups=int(entry.get("required", 2)),
                disqualifiers=frozenset(term.strip().lower() for term in entry.get("avoid", [])),
                note=entry.get("note", ""),
            )
        except ValueError as error:
            problems.append(str(error))

    if problems:
        raise ValueError("The lexicon has entries that cannot work:\n  " + "\n  ".join(problems))

    return signatures


def coverage_of_lexicon(slug: str) -> tuple[int, int]:
    """How much of the framework the lexicon currently speaks to.

    Reported openly in the output. A reader who knows 60 of 93 controls
    were examined can weigh the result; a reader who assumes all 93 were
    cannot.
    """
    framework = load_framework(slug)
    return len(load_signatures(slug, framework)), len(framework.controls)
