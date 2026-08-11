# Disclaimer and boundaries

## Independent work

**Audit Readiness Ledger** is an independent, open-source tool written by
Vasileios Tsalikidis. It is not affiliated with, endorsed by, or associated
with ISO, IEC, NIST, NATO, the NATO Communications and Information Agency,
the European Union, ENISA, the Hellenic Armed Forces, or any government
body, standards body or certification body.

## It is not an audit, and not an opinion on compliance

The tool reports which controls a folder of documents does not mention. It
does not say that any control is met, does not score, rate or grade, and
does not produce anything that can be presented as evidence of conformity.
Certification against ISO/IEC 27001 is carried out by an accredited
certification body reading your actual practice. Nothing here substitutes
for that, and no output of this tool should be shown to an auditor as if it
did.

A control the tool marks as addressed means only that some document says
something on the subject. Whether the statement is true of the organisation,
and whether what it describes is adequate, are judgements only a person can
make.

## Standards text

The ISO/IEC 27001:2022 standard is copyright ISO/IEC and its text is not
reproduced here. The catalogue in this repository holds control identifiers
and short control titles, which are facts about the structure of the
standard rather than its content. Working with the standard requires a
licensed copy, which you buy from ISO or from your national standards body.

NIST Cybersecurity Framework 2.0 is a United States government publication
in the public domain.

## Data

Nothing leaves the machine. The tool makes no network requests, sends no
telemetry, and calls no model or external service. It reads the folder you
point it at and writes the report where you tell it to.

The bundled example set under `examples/` is fictional. Meltemi Logistics,
its systems and the people in its documents are invented. Nothing in it
comes from any real organisation, and nothing comes from the author's
service.

## Use on real document sets

Policy sets usually carry a confidentiality marking. Running this tool does
not change that. The report it produces quotes lines from those documents,
so the report inherits the classification of the most sensitive document it
read. Handle it accordingly, and do not paste it into an issue tracker, a
chat tool, or a public repository without checking first.
