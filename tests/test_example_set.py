"""The bundled example set, run end to end.

Every other test file works on documents written inside the test. This one
runs the whole pipeline over the files a user gets when they clone the
repository, which is the only way to find out whether the parts fit
together.

It has already earned its place. The first run against this set reported
control A.8.8 as addressed on the strength of a sentence saying vulnerability
scanning had not started, which would have kept a genuine gap out of the gap
list. No unit test would have caught that, because no unit test would have
thought to write that sentence.

Each planted defect in examples/meltemi-logistics/README.md is asserted here.
The two files are meant to be read together: if a check is removed, the
assertion fails and the README stops being a promise nobody keeps.
"""

from __future__ import annotations

import json
import sys
import unittest
from datetime import date
from pathlib import Path

from audit_readiness_ledger.documents import load_directory
from audit_readiness_ledger.hygiene import Status, check_cross_references, check_document
from audit_readiness_ledger.lexicon_loader import load_framework, load_signatures
from audit_readiness_ledger.report import Analysis, render_json, render_markdown
from audit_readiness_ledger.signatures import Coverage, evaluate_all

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "meltemi-logistics"
DOCUMENTS = EXAMPLES / "documents"

# Fixed so the expected results do not change with the calendar. It sits
# after every approval date in the set and after one review date, which is
# the overdue one.
TODAY = date(2026, 8, 10)


def run():
    loaded = load_directory(DOCUMENTS)
    framework = load_framework("iso-27001-2022")
    signatures = load_signatures("iso-27001-2022", framework)
    documents = list(loaded.documents)
    return Analysis(
        framework=framework,
        findings=tuple(evaluate_all(framework.ids, signatures, documents)),
        hygiene=tuple(f for d in documents for f in check_document(d, TODAY)),
        cross_references=tuple(check_cross_references(documents)),
        documents_read=tuple(d.name for d in documents),
        units=loaded.units,
        skipped=loaded.skipped,
        source="examples/meltemi-logistics/documents",
        run_date=TODAY,
    )


class TheSetIsWhereItShouldBe(unittest.TestCase):
    def test_the_documents_folder_exists_and_is_not_empty(self):
        self.assertTrue(DOCUMENTS.is_dir())
        self.assertGreater(len(list(DOCUMENTS.iterdir())), 5)

    def test_the_readme_is_outside_the_folder_that_gets_analysed(self):
        """A note about the example set is not part of the example set."""
        self.assertTrue((EXAMPLES / "README.md").exists())
        self.assertFalse((DOCUMENTS / "README.md").exists())

    def test_the_word_document_is_a_real_one(self):
        analysis = run()
        self.assertIn("logging-and-monitoring-sop.docx", analysis.documents_read)
        self.assertEqual(analysis.units["logging-and-monitoring-sop.docx"], "paragraph")


class EveryPlantedDefectIsFound(unittest.TestCase):
    """One test per row of the table in the example set's README."""

    def setUp(self):
        self.analysis = run()

    def hygiene(self, document: str, check: str):
        return next(f for f in self.analysis.hygiene if f.document == document and f.check == check)

    def test_the_incident_plan_has_no_owner(self):
        finding = self.hygiene("incident-response-plan.md", "owner")
        self.assertIs(finding.status, Status.MISSING)

    def test_the_incident_plan_is_otherwise_complete(self):
        """So the missing owner is the finding, not one of six."""
        for check in ("approver", "version", "approval date", "classification"):
            with self.subTest(check=check):
                self.assertIs(
                    self.hygiene("incident-response-plan.md", check).status, Status.PRESENT
                )

    def test_the_backup_procedure_review_is_overdue(self):
        finding = self.hygiene("backup-and-recovery-procedure.md", "next review")
        self.assertIs(finding.status, Status.STALE)
        self.assertIn("2025-03-01", finding.detail)

    def test_the_acceptable_use_review_date_is_ambiguous(self):
        finding = self.hygiene("acceptable-use-and-remote-working.md", "next review")
        self.assertIs(finding.status, Status.AMBIGUOUS)
        self.assertIn("YYYY-MM-DD", finding.detail)

    def test_the_scanned_pdf_is_reported_not_ignored(self):
        reasons = {str(s.path): s.reason for s in self.analysis.skipped}
        self.assertIn("supplier-security-standard.pdf", reasons)
        self.assertIn(".pdf", reasons["supplier-security-standard.pdf"])

    def test_both_dangling_references_are_found(self):
        targets = " ".join(f.detail for f in self.analysis.cross_references)
        self.assertIn("Human Resources Security Standard", targets)
        self.assertIn("Records Retention Standard", targets)

    def test_a_reference_that_resolves_is_not_reported(self):
        """The policy cites the Access Control Policy, which is in the folder."""
        targets = " ".join(f.detail for f in self.analysis.cross_references)
        self.assertNotIn("Access Control Policy", targets)

    def test_the_notes_file_admits_a_gap_and_is_not_counted_as_coverage(self):
        for control in ("A.8.8", "A.8.32"):
            with self.subTest(control=control):
                finding = next(f for f in self.analysis.findings if f.control_id == control)
                self.assertIs(finding.coverage, Coverage.UNCLEAR)
                self.assertTrue(finding.deferred)
                self.assertIn("operations-notes.txt", finding.documents)

    def test_change_management_is_found_across_the_line_it_is_wrapped_on(self):
        """The notes wrap "change management" mid-term. It is still found."""
        finding = next(f for f in self.analysis.findings if f.control_id == "A.8.32")
        self.assertTrue(finding.hits)

    def test_the_notes_file_has_none_of_the_control_fields(self):
        missing = [
            f
            for f in self.analysis.hygiene
            if f.document == "operations-notes.txt" and f.status is Status.MISSING
        ]
        self.assertEqual(len(missing), 6)


class TheSetAlsoContainsRealCoverage(unittest.TestCase):
    """A fixture where everything is broken proves nothing works."""

    def setUp(self):
        self.analysis = run()
        self.grouped = self.analysis.by_coverage

    def test_the_ordinary_policies_are_matched(self):
        addressed = {f.control_id: f.documents for f in self.grouped[Coverage.ADDRESSED]}
        for control, document in (
            ("A.5.15", "access-control-policy.md"),
            ("A.5.24", "incident-response-plan.md"),
            ("A.7.2", "physical-security-instruction.md"),
            ("A.8.13", "backup-and-recovery-procedure.md"),
            ("A.8.15", "logging-and-monitoring-sop.docx"),
        ):
            with self.subTest(control=control):
                self.assertIn(control, addressed)
                self.assertIn(document, addressed[control])

    def test_the_deliberate_absences_appear_in_the_gap_list(self):
        gaps = {f.control_id for f in self.grouped[Coverage.NOT_ADDRESSED]}
        for control in ("A.5.7", "A.6.1", "A.6.3", "A.6.4", "A.8.28"):
            with self.subTest(control=control):
                self.assertIn(control, gaps)

    def test_the_gap_list_is_neither_empty_nor_the_whole_framework(self):
        gaps = self.grouped[Coverage.NOT_ADDRESSED]
        self.assertGreater(len(gaps), 5)
        self.assertLess(len(gaps), self.analysis.examined)


class TheReportOnTheExampleSetHoldsItsLine(unittest.TestCase):
    def setUp(self):
        self.markdown = render_markdown(run())

    def test_it_still_refuses_to_score(self):
        self.assertNotRegex(self.markdown, r"\d+\s*%")
        self.assertIn("does not say any control is met", self.markdown)

    def test_it_says_how_much_of_the_framework_it_looked_at(self):
        self.assertRegex(self.markdown, r"(All 93|\d+ of 93) controls were examined")

    def test_it_explains_the_deferral_finding_in_words(self):
        self.assertIn("not done, or not done yet", self.markdown)

    def test_two_runs_produce_the_same_bytes(self):
        self.assertEqual(self.markdown, render_markdown(run()))

    def test_the_json_output_parses_and_covers_every_control(self):
        payload = json.loads(render_json(run()))
        self.assertEqual(len(payload["controls"]), 93)
        self.assertTrue(payload["claims_no_control_is_met"])


class TheCommittedReportIsUpToDate(unittest.TestCase):
    """The report in the repository has to be the one the code produces.

    It is committed so a reader can see real output before installing
    anything. A committed file that nobody regenerates is worse than none,
    so drifting from it fails the build with the command that fixes it.
    """

    def test_it_matches_what_the_code_produces_now(self):
        sys.path.insert(0, str(EXAMPLES.parent.parent / "scripts"))
        from refresh_example_report import REPORT, build

        self.assertTrue(REPORT.exists(), "run scripts/refresh_example_report.py")
        self.assertEqual(
            REPORT.read_text(encoding="utf-8"),
            build(),
            "The committed example report is stale. Run: python scripts/refresh_example_report.py",
        )


if __name__ == "__main__":
    unittest.main()
