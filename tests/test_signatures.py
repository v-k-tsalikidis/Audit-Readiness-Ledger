"""Tests for the matching engine.

The first class is a regression test for the defect that shaped the design.
Before the subject group was made mandatory, a document reading "Backup
retention is 30 days" raised a partial match against the logging control,
because the word "retention" satisfied that control's second group on its
own. A tool that produces findings like that trains its reader to ignore it.
"""

from __future__ import annotations

import unittest

from audit_readiness_ledger.signatures import (
    Coverage,
    Document,
    Finding,
    Signature,
    evaluate,
    evaluate_all,
)


def doc(name: str, *lines: str) -> Document:
    return Document(name, tuple(lines))


LOGGING = Signature(
    control_id="A.8.15",
    anchor_groups=(
        frozenset({"audit log", "event log", "logging"}),
        frozenset({"retained", "retention", "reviewed"}),
    ),
    required_groups=2,
    disqualifiers=frozenset({"logistics", "login"}),
)

BACKUP = Signature(
    control_id="A.8.13",
    anchor_groups=(
        frozenset({"backup", "backups"}),
        frozenset({"restore", "restoration", "recovery"}),
    ),
    required_groups=2,
)


class SubjectIsMandatory(unittest.TestCase):
    def test_supporting_term_alone_produces_nothing(self):
        """The defect this design exists to prevent."""
        finding = evaluate(LOGGING, [doc("backup.md", "Backup retention is 30 days.")])
        self.assertIs(finding.coverage, Coverage.NOT_ADDRESSED)
        self.assertEqual(finding.hits, ())

    def test_subject_alone_is_unclear_not_addressed(self):
        finding = evaluate(LOGGING, [doc("p.md", "Audit log settings are described here.")])
        self.assertIs(finding.coverage, Coverage.UNCLEAR)

    def test_subject_plus_support_is_addressed(self):
        finding = evaluate(LOGGING, [doc("p.md", "Audit log entries are retained for one year.")])
        self.assertIs(finding.coverage, Coverage.ADDRESSED)


class WordBoundaries(unittest.TestCase):
    def test_logistics_does_not_satisfy_logging(self):
        finding = evaluate(LOGGING, [doc("l.md", "The logistics team retained records.")])
        self.assertIs(finding.coverage, Coverage.NOT_ADDRESSED)

    def test_disqualifier_suppresses_a_hit_on_the_same_line(self):
        finding = evaluate(
            LOGGING, [doc("l.md", "The movement logging sheet is retained by logistics.")]
        )
        self.assertIs(finding.coverage, Coverage.NOT_ADDRESSED)

    def test_a_hyphenated_neighbour_is_not_a_match(self):
        finding = evaluate(BACKUP, [doc("d.md", "The backup-adjacent process recovery.")])
        self.assertIs(finding.coverage, Coverage.NOT_ADDRESSED)


class GroupsMustShareADocument(unittest.TestCase):
    def test_halves_in_separate_documents_do_not_combine(self):
        finding = evaluate(
            BACKUP,
            [doc("a.md", "Backups run nightly."), doc("b.md", "Recovery is tested.")],
        )
        self.assertIs(finding.coverage, Coverage.UNCLEAR)

    def test_both_halves_in_one_document_are_addressed(self):
        finding = evaluate(
            BACKUP, [doc("a.md", "Backups run nightly.", "Recovery is tested quarterly.")]
        )
        self.assertIs(finding.coverage, Coverage.ADDRESSED)
        self.assertEqual(finding.documents, ("a.md",))


class EvidenceIsCheckable(unittest.TestCase):
    def test_every_hit_cites_a_real_line(self):
        document = doc("p.md", "Intro.", "Backups run nightly.", "Recovery is tested.")
        finding = evaluate(BACKUP, [document])
        for hit in finding.hits:
            self.assertGreaterEqual(hit.line, 1)
            self.assertLessEqual(hit.line, len(document.lines))
            self.assertIn(hit.term, document.lines[hit.line - 1].lower())

    def test_an_absent_control_explains_itself_without_naming_documents(self):
        finding = evaluate(BACKUP, [doc("p.md", "Nothing relevant.")])
        self.assertEqual(finding.documents, ())
        self.assertIn("No document", finding.explanation)


class UnexaminedIsNotAGap(unittest.TestCase):
    def test_a_control_without_a_signature_is_reported_as_not_assessed(self):
        findings = evaluate_all(["A.8.13", "A.7.4"], {"A.8.13": BACKUP}, [doc("p.md", "x")])
        by_id = {f.control_id: f for f in findings}
        self.assertIs(by_id["A.7.4"].coverage, Coverage.NOT_ASSESSED)
        self.assertIn("no signature", by_id["A.7.4"].explanation.lower())

    def test_every_catalogue_control_appears_in_the_result(self):
        ids = ["A.5.1", "A.8.13", "A.8.15"]
        findings = evaluate_all(ids, {"A.8.13": BACKUP}, [doc("p.md", "x")])
        self.assertEqual([f.control_id for f in findings], ids)


class ResultsAreDeterministic(unittest.TestCase):
    def test_repeated_runs_are_identical(self):
        documents = [
            doc("a.md", "Backups run nightly.", "Recovery is tested."),
            doc("b.md", "Audit log entries are retained."),
        ]
        first = evaluate_all(["A.8.13", "A.8.15"], {"A.8.13": BACKUP, "A.8.15": LOGGING}, documents)
        second = evaluate_all(
            ["A.8.13", "A.8.15"], {"A.8.13": BACKUP, "A.8.15": LOGGING}, documents
        )
        self.assertEqual(first, second)

    def test_document_order_does_not_change_the_verdict(self):
        a, b = (
            doc("a.md", "Backups run nightly."),
            doc("b.md", "Backups run nightly. Recovery tested."),
        )
        self.assertEqual(evaluate(BACKUP, [a, b]).coverage, evaluate(BACKUP, [b, a]).coverage)


class SignaturesThatCannotWorkAreRejected(unittest.TestCase):
    def test_requiring_more_groups_than_exist(self):
        with self.assertRaises(ValueError) as caught:
            Signature("A.1.1", (frozenset({"x"}),), required_groups=2)
        self.assertIn("never match", str(caught.exception))

    def test_no_anchor_groups(self):
        with self.assertRaises(ValueError):
            Signature("A.1.1", ())

    def test_zero_required_groups(self):
        with self.assertRaises(ValueError):
            Signature("A.1.1", (frozenset({"x"}),), required_groups=0)


class LanguageThatDefersIsNotCoverage(unittest.TestCase):
    """The failure that matters most: an admission read as a commitment.

    A sentence can name a subject and in the same breath say the
    organisation does not do it. Counting that as addressed takes a real
    gap off the gap list, which is the one thing this tool must not do.
    """

    signature = Signature(
        control_id="A.8.8",
        anchor_groups=(
            frozenset({"vulnerability scanning", "vulnerability management"}),
            frozenset({"scanned", "remediated", "patched", "monthly"}),
        ),
        required_groups=2,
    )

    def evaluate_line(self, *lines: str) -> Finding:
        return evaluate(self.signature, [Document("notes.md", tuple(lines))])

    def test_an_admission_is_not_addressed(self):
        finding = self.evaluate_line(
            "Vulnerability scanning was discussed with the supplier but has not started.",
            "It would otherwise be scanned monthly.",
        )
        self.assertIs(finding.coverage, Coverage.UNCLEAR)
        self.assertTrue(finding.deferred)

    def test_the_explanation_tells_the_reader_why(self):
        finding = self.evaluate_line(
            "There is no formal vulnerability management process.",
            "Systems would be patched monthly.",
        )
        self.assertIn("not done, or not done yet", finding.explanation)

    def test_a_future_promise_is_not_a_present_control(self):
        for phrase in (
            "Vulnerability scanning is planned for next year.",
            "Vulnerability management will be implemented in 2027.",
            "Vulnerability scanning is not yet in place.",
            "A vulnerability management process is under discussion.",
        ):
            with self.subTest(phrase=phrase):
                finding = self.evaluate_line(phrase, "Systems are patched monthly.")
                self.assertIs(finding.coverage, Coverage.UNCLEAR)

    def test_a_plain_statement_is_still_addressed(self):
        finding = self.evaluate_line(
            "Vulnerability scanning runs against every server.",
            "Findings are remediated monthly.",
        )
        self.assertIs(finding.coverage, Coverage.ADDRESSED)
        self.assertFalse(finding.deferred)

    def test_a_prohibition_is_a_control_not_an_absence(self):
        """ "are not permitted" forbids something. It does not defer anything."""
        finding = self.evaluate_line(
            "Servers that are not scanned are not permitted on the network.",
            "Vulnerability scanning covers every host and results are remediated monthly.",
        )
        self.assertIs(finding.coverage, Coverage.ADDRESSED)

    def test_one_document_deferring_does_not_hide_another_that_does_not(self):
        documents = [
            Document("notes.md", ("Vulnerability scanning has not started.", "monthly")),
            Document("standard.md", ("Vulnerability scanning is run monthly.",)),
        ]
        finding = evaluate(self.signature, documents)
        self.assertIs(finding.coverage, Coverage.ADDRESSED)
        self.assertEqual(finding.documents, ("standard.md",))


class OneCitationPerPlace(unittest.TestCase):
    def test_two_terms_on_one_line_cite_that_line_once(self):
        signature = Signature(
            control_id="A.8.15",
            anchor_groups=(frozenset({"audit log", "logging"}), frozenset({"retained"})),
            required_groups=2,
        )
        document = Document("sop.md", ("Logging produces an audit log that is retained.",))
        finding = evaluate(signature, [document])
        self.assertEqual(len({(h.document, h.line) for h in finding.hits}), len(finding.hits))


class TermsSurviveTheLineWrap(unittest.TestCase):
    """Real documents are hard-wrapped, and a wrap lands mid-term.

    Found by running the tool over the bundled example set: a notes file
    saying "there is no formal change / management standard yet" was
    reported as never mentioning change management, because the wrap put
    the two words on different lines.
    """

    signature = Signature(
        control_id="A.8.32",
        anchor_groups=(frozenset({"change management"}), frozenset({"approved"})),
        required_groups=2,
    )

    def test_a_term_split_by_a_wrap_is_found(self):
        document = Document(
            "notes.md",
            ("Every release goes through change", "management and is approved beforehand."),
        )
        finding = evaluate(self.signature, [document])
        self.assertIs(finding.coverage, Coverage.ADDRESSED)

    def test_a_wrapped_term_still_carries_its_deferral(self):
        """The wrap must not smuggle an admission past the deferral check."""
        document = Document(
            "notes.md",
            ("There is no formal change", "management standard, though changes are approved."),
        )
        finding = evaluate(self.signature, [document])
        self.assertIs(finding.coverage, Coverage.UNCLEAR)
        self.assertTrue(finding.deferred)

    def test_the_citation_points_at_the_line_the_term_starts_on(self):
        document = Document("notes.md", ("Our change", "management is approved."))
        hits = document.find("change management")
        self.assertEqual([hit.line for hit in hits], [1])

    def test_the_excerpt_shows_both_halves_so_it_can_be_checked(self):
        document = Document("notes.md", ("Our change", "management is approved."))
        self.assertIn("change management", document.find("change management")[0].excerpt)

    def test_a_term_on_one_line_is_not_also_reported_from_the_pair(self):
        document = Document("notes.md", ("Change management is defined.", "It is approved."))
        self.assertEqual(len(document.find("change management")), 1)

    def test_a_blank_line_between_paragraphs_stops_the_join(self):
        """Words that were paragraphs apart must not assemble into a term."""
        document = Document("notes.md", ("A note about change", "", "management of staff."))
        self.assertEqual(document.find("change management"), [])

    def test_a_single_word_term_is_unaffected(self):
        document = Document("notes.md", ("backup", "policy"))
        self.assertEqual(len(document.find("backup")), 1)


if __name__ == "__main__":
    unittest.main()
