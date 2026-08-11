"""Tests for the document hygiene checks.

Dates carry most of the risk here. A wrong reading puts a wrong date into
an audit file, and the failure is silent, so the parser is tested on the
formats a real Greek or European document set actually contains.
"""

from __future__ import annotations

import unittest
from datetime import date

from audit_readiness_ledger.hygiene import (
    Status,
    check_cross_references,
    check_document,
    find_field,
    parse_date,
)
from audit_readiness_ledger.signatures import Document

TODAY = date(2026, 8, 10)


def doc(name: str, *lines: str) -> Document:
    return Document(name, tuple(lines))


def finding(findings, check):
    return next(f for f in findings if f.check == check)


class DatesAreReadOrRefused(unittest.TestCase):
    def test_iso(self):
        self.assertEqual(parse_date("2027-01-31").value, date(2027, 1, 31))

    def test_european_day_first(self):
        self.assertEqual(parse_date("31/01/2027").value, date(2027, 1, 31))

    def test_dotted_and_dashed_are_both_read(self):
        self.assertEqual(parse_date("31.01.2027").value, date(2027, 1, 31))
        self.assertEqual(parse_date("31-01-2027").value, date(2027, 1, 31))

    def test_written_month(self):
        self.assertEqual(parse_date("31 January 2027").value, date(2027, 1, 31))

    def test_greek_month_with_accents(self):
        self.assertEqual(parse_date("31 Ιανουαρίου 2027").value, date(2027, 1, 31))

    def test_an_ambiguous_numeric_date_says_so(self):
        parsed = parse_date("05/03/2027")
        self.assertEqual(parsed.value, date(2027, 3, 5))
        self.assertTrue(parsed.ambiguous)

    def test_an_unambiguous_numeric_date_does_not(self):
        self.assertFalse(parse_date("31/01/2027").ambiguous)

    def test_iso_is_never_ambiguous(self):
        self.assertFalse(parse_date("2027-03-05").ambiguous)

    def test_a_date_that_cannot_exist_is_refused(self):
        self.assertIsNone(parse_date("2027-02-30"))

    def test_text_with_no_date_returns_nothing(self):
        self.assertIsNone(parse_date("reviewed regularly"))


class LabelledFieldsAreFound(unittest.TestCase):
    def test_a_colon_separated_field(self):
        value, line, _ = find_field(doc("p.md", "Owner: Jane Doe"), "owner")
        self.assertEqual(value, "Jane Doe")
        self.assertEqual(line, 1)

    def test_a_table_row_from_a_word_document(self):
        value, _, _ = find_field(doc("p.docx", "Document Owner | Jane Doe"), "owner")
        self.assertEqual(value, "Jane Doe")

    def test_prose_is_not_mistaken_for_a_field(self):
        """ "the owner of the system is responsible" is a sentence, not metadata."""
        self.assertIsNone(
            find_field(doc("p.md", "The owner of the system is responsible."), "owner")
        )

    def test_an_unfilled_template_placeholder_does_not_count(self):
        for placeholder in ("TBD", "N/A", "-", "To be confirmed"):
            with self.subTest(placeholder=placeholder):
                self.assertIsNone(find_field(doc("p.md", f"Owner: {placeholder}"), "owner"))

    def test_a_greek_label(self):
        value, _, _ = find_field(doc("p.md", "Ιδιοκτήτης: Μαρία Παπαδοπούλου"), "owner")
        self.assertEqual(value, "Μαρία Παπαδοπούλου")


class ReviewDatesAreTheHeadlineCheck(unittest.TestCase):
    def test_a_past_review_date_is_stale_and_counts_the_days(self):
        result = finding(
            check_document(doc("p.md", "Next review: 2025-08-10"), TODAY), "next review"
        )
        self.assertIs(result.status, Status.STALE)
        self.assertIn("365 days ago", result.detail)

    def test_a_future_review_date_is_present(self):
        result = finding(
            check_document(doc("p.md", "Next review: 2027-01-01"), TODAY), "next review"
        )
        self.assertIs(result.status, Status.PRESENT)

    def test_a_missing_review_date_is_missing(self):
        result = finding(check_document(doc("p.md", "Owner: Jane"), TODAY), "next review")
        self.assertIs(result.status, Status.MISSING)

    def test_a_review_date_that_is_not_a_date_is_flagged_separately(self):
        result = finding(check_document(doc("p.md", "Review date: annually"), TODAY), "next review")
        self.assertIs(result.status, Status.UNPARSED)
        self.assertIn("annually", result.detail)

    def test_an_ambiguous_future_date_asks_for_iso(self):
        result = finding(
            check_document(doc("p.md", "Next review: 05/03/2027"), TODAY), "next review"
        )
        self.assertIs(result.status, Status.AMBIGUOUS)
        self.assertIn("YYYY-MM-DD", result.detail)

    def test_staleness_outranks_ambiguity(self):
        """An overdue review matters more than how the date was written."""
        result = finding(
            check_document(doc("p.md", "Next review: 05/03/2020"), TODAY), "next review"
        )
        self.assertIs(result.status, Status.STALE)


class TheUsualMissingFields(unittest.TestCase):
    def test_a_document_with_nothing_reports_every_field_missing(self):
        findings = check_document(doc("p.md", "Some prose about backups."), TODAY)
        self.assertTrue(all(f.status is Status.MISSING for f in findings))
        self.assertEqual(len(findings), 6)

    def test_a_complete_control_block_reports_nothing_missing(self):
        document = doc(
            "p.md",
            "Owner: Jane Doe",
            "Approved by: The CISO",
            "Version: 2.1",
            "Effective date: 2026-01-01",
            "Classification: Internal",
            "Next review: 2027-01-01",
        )
        findings = check_document(document, TODAY)
        self.assertTrue(all(f.status is Status.PRESENT for f in findings))

    def test_a_present_field_cites_the_line_it_came_from(self):
        document = doc("p.md", "# Backup Policy", "", "Owner: Jane Doe")
        result = finding(check_document(document, TODAY), "owner")
        self.assertEqual(result.line, 3)
        self.assertIn("Jane Doe", result.excerpt)


class ReferencesToDocumentsThatWereNotSupplied(unittest.TestCase):
    def test_prose_with_no_trigger_word_makes_no_claim(self):
        """A title mentioned in passing is not a reference to be resolved."""
        documents = [doc("backup.md", "The Access Control Policy was updated last year.")]
        self.assertEqual(check_cross_references(documents), [])

    def test_the_trigger_words_cover_how_policies_actually_cite(self):
        for sentence in (
            "Restores follow the Access Control Policy.",
            "Access is governed by the Access Control Policy.",
            "Roles are set out in the Access Control Policy.",
            "Rights are documented in the Access Control Policy.",
        ):
            with self.subTest(sentence=sentence):
                findings = check_cross_references([doc("backup.md", sentence)])
                self.assertEqual(len(findings), 1)

    def test_a_reference_introduced_by_a_trigger_word_is_checked(self):
        documents = [doc("backup.md", "Access is granted as per the Access Control Policy.")]
        findings = check_cross_references(documents)
        self.assertEqual(len(findings), 1)
        self.assertIn("Access Control Policy", findings[0].detail)

    def test_a_reference_that_resolves_is_not_reported(self):
        documents = [
            doc("backup.md", "Access is granted as per the Access Control Policy."),
            doc("access-control-policy.md", "# Access Control Policy"),
        ]
        self.assertEqual(check_cross_references(documents), [])

    def test_the_same_missing_reference_is_reported_once_per_document(self):
        documents = [
            doc(
                "b.md",
                "See the Access Control Policy.",
                "Again, see the Access Control Policy.",
            )
        ]
        self.assertEqual(len(check_cross_references(documents)), 1)


class ResultsAreReproducible(unittest.TestCase):
    def test_today_is_injected_so_the_same_run_repeats(self):
        document = doc("p.md", "Next review: 2026-08-09")
        first = check_document(document, TODAY)
        second = check_document(document, TODAY)
        self.assertEqual(first, second)

    def test_the_same_document_on_a_later_date_becomes_stale(self):
        document = doc("p.md", "Next review: 2026-08-15")
        self.assertIs(
            finding(check_document(document, TODAY), "next review").status, Status.PRESENT
        )
        self.assertIs(
            finding(check_document(document, date(2026, 9, 1)), "next review").status, Status.STALE
        )


if __name__ == "__main__":
    unittest.main()
