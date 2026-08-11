#!/usr/bin/env python3
"""Build the control catalogue from authoritative sources.

The catalogue is generated rather than hand-typed, because a hand-typed
control list drifts from the standard and nobody notices until an audit.
Run this to regenerate it; the output is committed so the tool works
offline.

NIST CSF 2.0 comes from the NIST Cybersecurity Framework Reference Tool
export. That file carries both CSF 2.0 and the CSF 1.1 subcategories it
replaced, and the withdrawn ones are marked in their own text, so they are
filtered on that marker rather than on a hardcoded list of categories.

ISO/IEC 27001:2022 is different. The standard's text is copyrighted and is
not reproduced here. The catalogue carries the Annex A control identifiers
and their short titles, which are references rather than content, and the
tool tells the user to read the standard itself for the requirement. That
is also why coverage is reported against the control identifier and never
against the requirement wording.

Usage:
    python3 scripts/build_catalogue.py
    python3 scripts/build_catalogue.py --refresh   # re-download from NIST
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "src" / "audit_readiness_ledger" / "catalogue"
CACHE = ROOT / "build" / "nist-csf-2.0-reference.xlsx"

CSF_SOURCE = "https://csrc.nist.gov/extensions/nudp/services/json/csf/download?olirids=all"

SUBCATEGORY = re.compile(r"^([A-Z]{2}\.[A-Z]{2}-\d{2}):\s*(.+)$", re.S)
FUNCTION_NAMES = {
    "GV": "GOVERN",
    "ID": "IDENTIFY",
    "PR": "PROTECT",
    "DE": "DETECT",
    "RS": "RESPOND",
    "RC": "RECOVER",
}


def download_csf() -> Path:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {CSF_SOURCE}")
    request = urllib.request.Request(
        CSF_SOURCE, headers={"User-Agent": "audit-readiness-ledger/catalogue-build"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        CACHE.write_bytes(response.read())
    print(f"  saved {CACHE.stat().st_size // 1024} KB")
    return CACHE


def build_csf(source: Path) -> list[dict]:
    try:
        import openpyxl
    except ImportError:
        sys.exit("openpyxl is required to rebuild the catalogue: pip install openpyxl")

    import warnings

    warnings.filterwarnings("ignore", module="openpyxl")
    sheet = openpyxl.load_workbook(source, read_only=True)["CSF 2.0"]

    entries: dict[str, dict] = {}
    withdrawn = 0
    category_titles: dict[str, str] = {}

    for row in sheet.iter_rows(values_only=True):
        if not row:
            continue
        # Category names arrive in their own column as "Name (GV.OC): text".
        if row[1]:
            match = re.match(r"^(.+?)\s*\(([A-Z]{2}\.[A-Z]{2})\):", str(row[1]).strip())
            if match:
                category_titles[match.group(2)] = match.group(1).strip()
        if not row[2]:
            continue
        match = SUBCATEGORY.match(str(row[2]).strip())
        if not match:
            continue
        identifier, text = match.group(1), " ".join(match.group(2).split())
        # CSF 1.1 subcategories are carried in this export and say so.
        if text.startswith("[Withdrawn"):
            withdrawn += 1
            continue
        entries.setdefault(
            identifier,
            {
                "id": identifier,
                "function": FUNCTION_NAMES[identifier[:2]],
                "category": identifier.split("-")[0],
                "text": text,
            },
        )

    for entry in entries.values():
        entry["category_title"] = category_titles.get(entry["category"], "")

    print(f"  CSF 2.0 subcategories: {len(entries)}  (withdrawn removed: {withdrawn})")
    return sorted(entries.values(), key=lambda e: e["id"])


# Annex A identifiers and short titles. Reference data, not the standard's
# text. Anyone applying these must work from their own copy of ISO/IEC
# 27001:2022; this tool reports which identifiers a document set does not
# address, never whether a requirement is met.
ISO_27001_2022 = {
    "A.5": (
        "Organizational controls",
        [
            "Policies for information security",
            "Information security roles and responsibilities",
            "Segregation of duties",
            "Management responsibilities",
            "Contact with authorities",
            "Contact with special interest groups",
            "Threat intelligence",
            "Information security in project management",
            "Inventory of information and other associated assets",
            "Acceptable use of information and other associated assets",
            "Return of assets",
            "Classification of information",
            "Labelling of information",
            "Information transfer",
            "Access control",
            "Identity management",
            "Authentication information",
            "Access rights",
            "Information security in supplier relationships",
            "Addressing information security within supplier agreements",
            "Managing information security in the ICT supply chain",
            "Monitoring, review and change management of supplier services",
            "Information security for use of cloud services",
            "Information security incident management planning and preparation",
            "Assessment and decision on information security events",
            "Response to information security incidents",
            "Learning from information security incidents",
            "Collection of evidence",
            "Information security during disruption",
            "ICT readiness for business continuity",
            "Legal, statutory, regulatory and contractual requirements",
            "Intellectual property rights",
            "Protection of records",
            "Privacy and protection of personally identifiable information",
            "Independent review of information security",
            "Compliance with policies, rules and standards for information security",
            "Documented operating procedures",
        ],
    ),
    "A.6": (
        "People controls",
        [
            "Screening",
            "Terms and conditions of employment",
            "Information security awareness, education and training",
            "Disciplinary process",
            "Responsibilities after termination or change of employment",
            "Confidentiality or non-disclosure agreements",
            "Remote working",
            "Information security event reporting",
        ],
    ),
    "A.7": (
        "Physical controls",
        [
            "Physical security perimeters",
            "Physical entry",
            "Securing offices, rooms and facilities",
            "Physical security monitoring",
            "Protecting against physical and environmental threats",
            "Working in secure areas",
            "Clear desk and clear screen",
            "Equipment siting and protection",
            "Security of assets off-premises",
            "Storage media",
            "Supporting utilities",
            "Cabling security",
            "Equipment maintenance",
            "Secure disposal or re-use of equipment",
        ],
    ),
    "A.8": (
        "Technological controls",
        [
            "User endpoint devices",
            "Privileged access rights",
            "Information access restriction",
            "Access to source code",
            "Secure authentication",
            "Capacity management",
            "Protection against malware",
            "Management of technical vulnerabilities",
            "Configuration management",
            "Information deletion",
            "Data masking",
            "Data leakage prevention",
            "Information backup",
            "Redundancy of information processing facilities",
            "Logging",
            "Monitoring activities",
            "Clock synchronization",
            "Use of privileged utility programs",
            "Installation of software on operational systems",
            "Networks security",
            "Security of network services",
            "Segregation of networks",
            "Web filtering",
            "Use of cryptography",
            "Secure development life cycle",
            "Application security requirements",
            "Secure system architecture and engineering principles",
            "Secure coding",
            "Security testing in development and acceptance",
            "Outsourced development",
            "Separation of development, test and production environments",
            "Change management",
            "Test information",
            "Protection of information systems during audit testing",
        ],
    ),
}


def build_iso() -> list[dict]:
    controls = []
    for clause, (theme, titles) in ISO_27001_2022.items():
        for index, title in enumerate(titles, start=1):
            controls.append(
                {
                    "id": f"{clause}.{index}",
                    "theme": theme,
                    "clause": clause,
                    "title": title,
                }
            )
    print(f"  ISO 27001:2022 Annex A controls: {len(controls)}")
    return controls


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="re-download the NIST export instead of using the cache",
    )
    args = parser.parse_args()

    CATALOGUE.mkdir(parents=True, exist_ok=True)

    source = CACHE if CACHE.exists() and not args.refresh else download_csf()
    csf = build_csf(source)
    iso = build_iso()

    if len(csf) != 106:
        sys.exit(f"expected 106 CSF 2.0 subcategories, parsed {len(csf)}")
    if len(iso) != 93:
        sys.exit(f"expected 93 Annex A controls, built {len(iso)}")

    (CATALOGUE / "nist-csf-2.0.json").write_text(
        json.dumps(
            {
                "framework": "NIST CSF 2.0",
                "source": CSF_SOURCE,
                "licence": "US Government work, public domain",
                "controls": csf,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    (CATALOGUE / "iso-27001-2022.json").write_text(
        json.dumps(
            {
                "framework": "ISO/IEC 27001:2022 Annex A",
                "source": "Control identifiers and short titles only",
                "licence": "Standard text is copyright ISO/IEC and is not reproduced",
                "controls": iso,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"\nwritten to {CATALOGUE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
