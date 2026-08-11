# Differentiation brief — Audit Readiness Ledger

Written before any code, as the project standard requires. Research dated
2026-08-10.

## The problem

An organisation preparing for an ISO 27001 audit has a folder of policies,
standard operating procedures and instructions. Someone wrote them, often
over several years and often several someones. Nobody can say with
confidence which Annex A controls that folder actually addresses.

The gap is found the expensive way: an auditor reads the set, asks for the
procedure covering a control, and it does not exist. The finding is not
usually that a policy was wrong. It is that a policy was missing, or that it
existed with no owner, or that its review date passed two years ago and
nobody noticed.

## Who it is for

Someone responsible for an ISO 27001 or NIS2 documentation set who has more
documents than time: an internal auditor, a security manager at a company
without a GRC platform, or a consultant taking over someone else's estate.

Not for enterprises already running a GRC suite. They have this covered.

## What already exists

**[policy-lens](https://github.com/davidalex89/policy-lens)** — Apache 2.0,
1 star, 16 commits at the time of writing. The closest thing to this idea. A
local-first analyser that reads a policy document and reports coverage
against NIST 800-53, ISO 27001, SOC 2, CIS v8 and Adobe CCF. It has a test
suite, which most tools in this space do not.

Its mapping is three sequential LLM calls through Ollama: extract statements,
map to control families, score coverage. Temperature is set to 0.1 for
consistency.

**[CISO Assistant](https://github.com/datsproject/ciso)** — a full GRC
platform, 150+ frameworks, automatic control-to-control mapping, risk, audit
and privacy modules. Mature and genuinely good.

**[compliance-trestle](https://github.com/oscal-compass/compliance-trestle)**
— IBM's OSCAL tooling, compliance-as-code in CI.

**Commercial**: Scrut, Drata, ISMS.online and others all offer gap analysis
as part of a subscription.

## Where they leave a gap

**The platforms want structured input.** CISO Assistant and trestle are
excellent once your controls, evidence and mappings are recorded in them.
They do not read the documents you already have. Getting from "a folder of
Word files" to "data in the platform" is the work, and it is the work nobody
has time for.

**policy-lens reads documents, but its answer cannot be audited.** Three
chained LLM calls at temperature 0.1 are more consistent than at 0.7, and
still not deterministic. Two runs can disagree. More importantly, when an
auditor asks why a control was marked covered, the honest answer is that a
model produced that token sequence. That is not evidence, and an audit trail
built on it does not survive scrutiny.

It also requires Ollama installed and a multi-gigabyte model pulled before
anything runs, which is a real barrier for the security manager who has
twenty minutes.

## What this does differently

**It is deterministic.** Same folder in, same report out, every time, on any
machine. The mapping is a published lexicon of control signatures plus
document-structure rules, not a model. A user can read the rule that fired.

**It reports absence, never sufficiency.** This is the central design
decision and the one that makes determinism honest. The tool says *no
document in this set addresses A.5.15* — which is checkable and true. It
never says *this policy satisfies A.5.15*, because adequacy is a human
judgement and any tool claiming otherwise is lying to its user. Missing
documents are the most common audit finding, and absence is exactly what a
deterministic method can establish.

**It finds the unglamorous failures.** A policy with no named owner. A review
date in the past. A procedure referring to a system that appears nowhere else
in the set. A control referenced by two documents that contradict each other
on who approves. These are what auditors actually raise, and none of them
need a language model to detect.

**It runs with no model and no service.** Python, a small dependency set, one
command. No Ollama, no download, no account.

**It ships with a document set to run against.** A realistic synthetic
organisation, with policies carrying the defects real ones carry. The user
sees the tool work on their first command instead of having to supply their
own confidential material to find out what it does. No tool in this space
ships test fixtures.

## Scope, and what it will not do

In scope for the first release:

- ISO/IEC 27001:2022 Annex A, and NIST CSF 2.0.
- Markdown, plain text and DOCX input.
- A coverage report naming, per control: addressed / not addressed / unclear,
  with the document and line that triggered each finding.
- Document hygiene: owner, approver, version, review date, expiry.
- Cross-reference integrity within the set.

Explicitly out of scope:

- Any claim that a control is adequately implemented.
- A compliance percentage or maturity score.
- Reading evidence artifacts such as logs, tickets or screenshots.
- Certification advice.

## Data policy

Everything runs locally. Documents are read and never transmitted, stored or
copied. The bundled example set is fictional: invented company, invented
systems, invented names. Nothing from any real organisation, and nothing from
the author's service.

## Why this author

I wrote the security documentation sets that get evaluated, and I have been
on both sides of the inspection: producing the evidence, and sitting on a
multinational evaluation team assessing another headquarters. The failures
this tool looks for are the ones I have watched happen.

That is also why it refuses to score. A number would have made my own
documentation look finished on days when it was not.

## Recruiter signal

It shows that I can take a compliance framework and turn it into working
software, that I understand what an auditor actually asks for, and that I
know where automation stops and judgement starts. For a GRC, ISO 27001 or
internal audit role, that last point is the one that matters.

## Definition of done

Per the project excellence standard: research brief, scope and non-goals,
tests for core and boundary behaviour, deterministic output verified across
runs, a dry run against the bundled document set with results checked by
hand, README with a working ten-second quick start, stated limitations, and
a public-safety note. Nothing is called complete before all of that.
