"""Tests for the report.

Most of these assert the absence of something. That is deliberate: the
project's claim is about what it refuses to say, and a refusal that is not
tested will quietly disappear the first time someone adds a summary line.
"""

from __future__ import annotations

import json
import re
import unittest
from datetime import date
from pathlib import Path

from audit_readiness_ledger.documents import Skipped
from audit_readiness_ledger.hygiene import HygieneFinding, Status
from audit_readiness_ledger.lexicon_loader import Control, Framework
from audit_readiness_ledger.report import Analysis, render_json, render_markdown
from audit_readiness_ledger.signatures import Coverage, Finding, TermHit

RUN_DATE = date(2026, 8, 10)

FRAMEWORK = Framework(
    name="ISO/IEC 27001:2022 Annex A",
    controls=(
        Control("A.8.13", "Information backup", "Technological controls"),
        Control("A.8.15", "Logging", "Technological controls"),
        Control("A.5.1", "Policies for information security", "Organizational controls"),
        Control("A.7.4", "Physical security monitoring", "Physical controls"),
    ),
    licence="Standard text is copyright ISO/IEC and is not reproduced",
)


def analysis(**overrides) -> Analysis:
    defaults: dict = {
        "framework": FRAMEWORK,
        "findings": (
            Finding(
                "A.8.13",
                Coverage.ADDRESSED,
                ("backup.md",),
                (TermHit("backup", "backup.md", 3, "Backups run nightly."),),
                2,
                2,
            ),
            Finding("A.8.15", Coverage.NOT_ADDRESSED, (), (), 0, 2),
            Finding(
                "A.5.1",
                Coverage.UNCLEAR,
                ("policy.md",),
                (TermHit("security policy", "policy.md", 1, "# Security Policy"),),
                1,
                2,
            ),
            Finding("A.7.4", Coverage.NOT_ASSESSED, (), (), 0, 0),
        ),
        "hygiene": (
            HygieneFinding("backup.md", "owner", Status.MISSING, "No owner is stated."),
            HygieneFinding(
                "policy.md",
                "next review",
                Status.STALE,
                "The review was due on 2025-01-01, 586 days ago.",
                4,
                "Next review: 2025-01-01",
            ),
        ),
        "cross_references": (
            HygieneFinding(
                "backup.md",
                "cross-reference",
                Status.MISSING,
                "Refers to 'Access Control Policy', which is not among the documents supplied.",
                9,
                "See the Access Control Policy.",
            ),
        ),
        "documents_read": ("backup.md", "policy.md"),
        "units": {"backup.md": "line", "policy.md": "line"},
        "skipped": (Skipped(Path("scan.pdf"), ".pdf is not a readable format"),),
        "source": "example-set",
        "run_date": RUN_DATE,
    }
    defaults.update(overrides)
    return Analysis(**defaults)


class TheReportRefusesToScore(unittest.TestCase):
    def test_no_percentage_appears_anywhere(self):
        text = render_markdown(analysis())
        self.assertNotRegex(text, r"\d+\s*%")

    def test_no_compliance_or_maturity_language(self):
        text = render_markdown(analysis()).lower()
        for word in ("compliant", "compliance score", "maturity", "rating", "grade"):
            with self.subTest(word=word):
                self.assertNotIn(word, text)

    def test_it_states_that_it_claims_no_control_is_met(self):
        text = render_markdown(analysis())
        self.assertIn("does not say any control is met", text)

    def test_the_addressed_table_disclaims_implementation(self):
        text = render_markdown(analysis())
        self.assertIn("not the same as the control being implemented", text)


class TheGapListLeads(unittest.TestCase):
    def test_controls_no_document_addresses_come_first(self):
        text = render_markdown(analysis())
        gaps = text.index("## Controls no document addresses")
        speaks = text.index("## Controls the set speaks to")
        self.assertLess(gaps, speaks)

    def test_a_missing_control_is_listed_with_its_subject(self):
        text = render_markdown(analysis())
        self.assertIn("| A.8.15 | Logging |", text)

    def test_a_clean_set_says_so_rather_than_showing_an_empty_table(self):
        findings = (Finding("A.8.13", Coverage.ADDRESSED, ("b.md",), (), 2, 2),)
        text = render_markdown(analysis(findings=findings))
        self.assertIn("None. Every control that was examined", text)


class SilenceIsMadeVisible(unittest.TestCase):
    def test_the_header_says_how_many_controls_were_examined(self):
        text = render_markdown(analysis())
        self.assertIn("3 of 4 controls were examined", text)

    def test_unexamined_controls_are_listed_not_hidden(self):
        text = render_markdown(analysis())
        self.assertIn("## Controls this tool did not examine", text)
        self.assertIn("A.7.4", text.split("## Controls this tool did not examine")[1])

    def test_unreadable_files_are_reported_with_their_consequence(self):
        text = render_markdown(analysis())
        self.assertIn("scan.pdf", text)
        self.assertIn("will appear above as not addressed", text)


class CitationsUseTheRightUnit(unittest.TestCase):
    def test_a_word_document_is_cited_by_paragraph(self):
        result = analysis(
            units={"policy.docx": "paragraph"},
            hygiene=(
                HygieneFinding(
                    "policy.docx",
                    "next review",
                    Status.STALE,
                    "The review was due on 2025-01-01, 586 days ago.",
                    4,
                    "x",
                ),
            ),
        )
        self.assertIn("policy.docx paragraph 4", render_markdown(result))

    def test_a_markdown_document_is_cited_by_line(self):
        self.assertIn("policy.md line 4", render_markdown(analysis()))


class HygieneAppearsWhenItMatters(unittest.TestCase):
    def test_an_overdue_review_gets_its_own_heading(self):
        text = render_markdown(analysis())
        self.assertIn("### Reviews that are overdue", text)
        self.assertIn("586 days ago", text)

    def test_missing_fields_are_grouped_by_document(self):
        text = render_markdown(analysis())
        self.assertIn("### Fields not filled in", text)
        self.assertIn("| backup.md | owner |", text)

    def test_a_set_with_clean_hygiene_omits_the_section(self):
        text = render_markdown(analysis(hygiene=(), cross_references=()))
        self.assertNotIn("## Document hygiene", text)


class TheJsonSaysTheSameThings(unittest.TestCase):
    def test_it_is_valid_json(self):
        json.loads(render_json(analysis()))

    def test_it_records_its_own_refusals(self):
        payload = json.loads(render_json(analysis()))
        self.assertTrue(payload["claims_no_control_is_met"])
        self.assertTrue(payload["produces_no_score"])

    def test_every_control_appears_including_unexamined_ones(self):
        payload = json.loads(render_json(analysis()))
        self.assertEqual(len(payload["controls"]), 4)
        coverages = {c["id"]: c["coverage"] for c in payload["controls"]}
        self.assertEqual(coverages["A.7.4"], "not assessed")

    def test_evidence_carries_the_unit_so_a_position_can_be_found(self):
        payload = json.loads(render_json(analysis()))
        backup = next(c for c in payload["controls"] if c["id"] == "A.8.13")
        self.assertEqual(backup["evidence"][0]["unit"], "line")
        self.assertEqual(backup["evidence"][0]["position"], 3)


class TheSameRunProducesTheSameReport(unittest.TestCase):
    def test_markdown_is_byte_identical_across_runs(self):
        self.assertEqual(render_markdown(analysis()), render_markdown(analysis()))

    def test_json_is_byte_identical_across_runs(self):
        self.assertEqual(render_json(analysis()), render_json(analysis()))

    def test_only_the_run_date_ties_the_report_to_a_day(self):
        text = render_markdown(analysis())
        dates = set(re.findall(r"\d{4}-\d{2}-\d{2}", text))
        # 2025-01-01 is quoted from a document, not generated by the run.
        self.assertEqual(dates - {"2025-01-01"}, {"2026-08-10"})


if __name__ == "__main__":
    unittest.main()
