# Audit Readiness Ledger

[![CI](https://github.com/v-k-tsalikidis/Audit-Readiness-Ledger/actions/workflows/ci.yml/badge.svg)](https://github.com/v-k-tsalikidis/Audit-Readiness-Ledger/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB.svg)](pyproject.toml)

Point it at a folder of security policies. It tells you which ISO 27001
Annex A controls **no document in that folder addresses**.

It never tells you a control is met. That is the whole design.

Part of the Ledger tools: small local-first instruments that record a decision
and the evidence behind it.

```bash
pip install -e .
audit-readiness-ledger examples/meltemi-logistics/documents
```

The example set is bundled and fictional, so the first command you run
shows you what the tool does without you handing it your own policies to
find out. The report it produces is committed at
[examples/meltemi-logistics/example-report.md](examples/meltemi-logistics/example-report.md)
if you would rather read the output before installing anything.

## Why it refuses to score

Most tools in this space return a coverage percentage. A percentage cannot
be checked, cannot be defended to an auditor, and reads as an achievement
when it is really an average of guesses.

Whether a control is *met* depends on whether the words in the document are
true of the organisation and whether what they describe is adequate. No
matcher can see that. What a matcher can establish is the opposite: that
across every document supplied, nothing mentions this subject at all. That
is a fact, it is checkable, and it is where audit findings come from.

So the report leads with a list of controls no document addresses, and every
positive result is worded as "the set speaks to this", with the file and
line so you can go and read it yourself.

## What it does

- **Matches deterministically.** Exact terms on word boundaries, from a
  lexicon you can open and argue with. The same folder gives the same report
  every time. No model, no network, nothing leaves the machine.
- **Reads .md, .txt, .rst and .docx**, including the tables Word documents
  keep their control block in. Anything it cannot read is listed in the
  report, because a gap list computed from half the folder is wrong in your
  favour.
- **Checks the documents themselves** — owner, approver, version, approval
  date, classification, review date — and finds the ones whose review date
  passed, the ones written `05/03/2027` where nobody can tell March from
  May, and the ones citing a document that was never supplied.
- **Covers all 93 Annex A controls**, and proves it. One realistic policy
  sentence per control is run through the whole lexicon in the test suite,
  which asserts the right control matches and that no unrelated one does.
  A signature that cannot fire would otherwise show up as a permanent gap
  and nobody could tell it from a real one.
- **Says what it did not look at.** If a control ever has no signature, it
  is listed by identifier in every report rather than quietly dropped, so
  its absence from the gap list cannot be mistaken for good news.
- **Reads Greek document sets**, including Greek field labels and month
  names in genitive form.

## What it does not do

It does not say a control is met. It does not score, rate or grade. It only
reads the folder you give it, so evidence living in tickets, logs or a
system is outside what it can see. And it does not decide the cases it
cannot decide — where a document names a subject without saying what is done
about it, or says the work has not started, it hands those to you and says
which is which.

## Using it

```bash
audit-readiness-ledger POLICIES/                       # report to the terminal
audit-readiness-ledger POLICIES/ -o report.md          # report to a file
audit-readiness-ledger POLICIES/ --format json         # for another tool
audit-readiness-ledger POLICIES/ --today 2026-08-10    # reproducible run
audit-readiness-ledger --list-frameworks               # what can be examined
```

`--today` matters more than it looks. Whether a review date is overdue
depends on the day you ran it, so a report that goes into an audit file
should carry the date it was judged against and be reproducible from it.

**Exit codes.** A run that completes exits 0 whatever it found, because
finding gaps is not an error and this tool does not decide your set failed.
A run that could not happen exits 1. If you want a pipeline to break on
gaps, ask for it with `--fail-on-gaps`, which exits 2 — your policy, stated
in your own pipeline.

## The lexicon

Signatures live in
[src/audit_readiness_ledger/lexicon/iso-27001-2022.yaml](src/audit_readiness_ledger/lexicon/iso-27001-2022.yaml)
and are meant to be read and edited:

```yaml
A.8.15:
  title: Logging
  anchors:
    - [audit log, audit logs, event log, event logs, logging, log retention]
    - [retained, retention, protected, reviewed, generated]
  required: 2
  avoid: [logistics, login, logistic]
```

The first group is the subject and is mandatory. Without that rule a control
whose second group holds ordinary verbs fires on any document containing one
of them — "Backup retention is 30 days" raised a match against Logging on
the word "retention" alone, which is how a lexicon quietly stops meaning
anything. `avoid` removes a hit when the term is being used in another
sense, which is what keeps a logistics company out of the logging control.

A signature naming a control that does not exist, or asking for more groups
than it defines, is rejected when the lexicon loads rather than producing a
quietly wrong report.

## Frameworks

| Catalogue | Controls | Can be examined |
| --- | --- | --- |
| ISO/IEC 27001:2022 Annex A | 93 | 93 |
| NIST CSF 2.0 | 106 | not yet — catalogue only |

Catalogues are built from the published sources by
`scripts/build_catalogue.py`. ISO standard text is copyright and is not
reproduced: only control identifiers and short titles are used, which are
facts about the standard rather than its content. NIST CSF 2.0 is public
domain.

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests -q
ruff check src tests scripts && ruff format --check src tests scripts
mypy src
```

Four of the defects the tests now guard against were found by running the
tool over real prose rather than by unit testing. A document saying
vulnerability scanning had not started was being counted as coverage.
Multi-word terms were being missed wherever a hard-wrapped line split them
in half. And "audit testing is planned in advance" was being read as work
postponed rather than work scheduled. And twenty-two signatures were
asking for a subject plus something done about it while accepting a single
phrase for both, because the supporting group had borrowed a word from the
subject. All four would have produced confidently wrong reports.

After changing the lexicon, the checks or the report layout, regenerate the
committed example report or the build will tell you it is stale:

```bash
python scripts/refresh_example_report.py
```

## Licence and boundaries

Apache-2.0. See [LICENSE](LICENSE).

[DISCLAIMER.md](DISCLAIMER.md) states what this tool is not: it is not an
audit, not an opinion on compliance, and no output of it should be shown to
an auditor as evidence of conformity. It also covers how the ISO standard's
copyright is respected here, and why a report inherits the classification of
the documents it read.
