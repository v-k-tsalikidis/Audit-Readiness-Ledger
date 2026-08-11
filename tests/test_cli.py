"""Tests for the command line.

The exit code carries a claim, so most of these are about exit codes. A
tool that exits 1 on a document set with gaps is telling the user the set
failed, and this tool does not say that anywhere else.

They run `main()` in process rather than spawning a subprocess, so a
failure points at a line instead of at a shell.
"""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from audit_readiness_ledger.cli import build_parser, main, parse_today, today_here

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples" / "meltemi-logistics"
DOCUMENTS = EXAMPLES / "documents"
RUN_DATE = "2026-08-10"


def run(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class GapsAreNotErrors(unittest.TestCase):
    """The decision this module exists to protect."""

    def test_a_set_with_gaps_still_exits_zero(self):
        code, out, _ = run(str(DOCUMENTS), "--today", RUN_DATE)
        self.assertEqual(code, 0)
        self.assertIn("## Controls no document addresses", out)

    def test_fail_on_gaps_is_opt_in_and_exits_two(self):
        code, _, _ = run(str(DOCUMENTS), "--today", RUN_DATE, "--fail-on-gaps")
        self.assertEqual(code, 2)

    def test_two_is_not_one_so_a_gap_is_distinguishable_from_a_broken_run(self):
        gaps, _, _ = run(str(DOCUMENTS), "--today", RUN_DATE, "--fail-on-gaps")
        broken, _, _ = run("/no/such/folder")
        self.assertNotEqual(gaps, broken)
        self.assertEqual(broken, 1)


class ItRefusesRatherThanReportNothing(unittest.TestCase):
    def test_a_framework_without_a_lexicon_is_refused_with_a_reason(self):
        code, _, err = run(str(DOCUMENTS), "--framework", "nist-csf-2.0")
        self.assertEqual(code, 1)
        self.assertIn("No lexicon", err)
        self.assertIn("iso-27001-2022", err)

    def test_an_unknown_framework_is_refused(self):
        code, _, _ = run(str(DOCUMENTS), "--framework", "iso-9001")
        self.assertEqual(code, 1)

    def test_a_missing_folder_says_which_one(self):
        code, _, err = run("/no/such/folder")
        self.assertEqual(code, 1)
        self.assertIn("/no/such/folder", err)

    def test_a_folder_with_nothing_readable_says_what_it_reads(self):
        with TemporaryDirectory() as temporary:
            (Path(temporary) / "scan.pdf").write_bytes(b"%PDF-1.4\n")
            code, _, err = run(temporary)
        self.assertEqual(code, 1)
        self.assertIn(".docx", err)

    def test_no_folder_at_all_points_at_the_example_set(self):
        code, _, err = run()
        self.assertEqual(code, 1)
        self.assertIn("examples/meltemi-logistics/documents", err)


class TheReportGoesWhereItWasAsked(unittest.TestCase):
    def test_markdown_goes_to_standard_output(self):
        _, out, _ = run(str(DOCUMENTS), "--today", RUN_DATE)
        self.assertTrue(out.startswith("# Audit readiness:"))

    def test_json_is_valid_and_carries_the_refusals(self):
        _, out, _ = run(str(DOCUMENTS), "--today", RUN_DATE, "--format", "json")
        payload = json.loads(out)
        self.assertTrue(payload["claims_no_control_is_met"])
        self.assertEqual(len(payload["controls"]), 93)

    def test_output_writes_a_file_and_leaves_stdout_clean(self):
        with TemporaryDirectory() as temporary:
            target = Path(temporary) / "nested" / "report.md"
            code, out, err = run(str(DOCUMENTS), "--today", RUN_DATE, "-o", str(target))
            self.assertEqual(code, 0)
            self.assertEqual(out, "")
            self.assertIn("# Audit readiness:", target.read_text(encoding="utf-8"))
            self.assertIn(str(target), err)

    def test_the_summary_goes_to_stderr_so_a_pipe_still_tells_you_something(self):
        _, out, err = run(str(DOCUMENTS), "--today", RUN_DATE)
        self.assertIn("Examined 93 of 93 controls", err)
        self.assertNotIn("Examined 93 of 93 controls", out)

    def test_unreadable_files_are_mentioned_on_stderr_too(self):
        _, _, err = run(str(DOCUMENTS), "--today", RUN_DATE)
        self.assertIn("could not be read", err)


class TheRunCanBeRepeated(unittest.TestCase):
    def test_the_same_date_gives_the_same_bytes(self):
        first = run(str(DOCUMENTS), "--today", RUN_DATE)[1]
        second = run(str(DOCUMENTS), "--today", RUN_DATE)[1]
        self.assertEqual(first, second)

    def test_a_later_date_makes_a_review_overdue(self):
        early = run(str(DOCUMENTS), "--today", "2026-08-10")[1]
        late = run(str(DOCUMENTS), "--today", "2027-06-01")[1]
        self.assertNotEqual(early, late)
        self.assertIn("acceptable-use-and-remote-working.md", late)

    def test_a_date_that_is_not_a_date_is_rejected_before_anything_runs(self):
        with self.assertRaises(SystemExit) as caught:
            build_parser().parse_args([str(DOCUMENTS), "--today", "10/08/2026"])
        self.assertEqual(caught.exception.code, 2)

    def test_parse_today_names_the_format_it_wants(self):
        with self.assertRaises(Exception) as caught:
            parse_today("not a date")
        self.assertIn("YYYY-MM-DD", str(caught.exception))

    def test_the_default_date_is_a_real_local_date(self):
        self.assertIsInstance(today_here(), date)


class TheCommittedReportIsWhatTheCommandProduces(unittest.TestCase):
    """The README tells people to run one command. This is its output.

    If these ever diverge, the file in the repository is advertising
    something the tool does not do.
    """

    def test_they_match_byte_for_byte(self):
        _, out, _ = run("examples/meltemi-logistics/documents", "--today", RUN_DATE)
        committed = (EXAMPLES / "example-report.md").read_text(encoding="utf-8")
        body = committed.split("\n\n", 1)[1]
        self.assertEqual(out, body)


class ListingFrameworksIsHonestAboutCoverage(unittest.TestCase):
    def test_it_says_how_much_of_each_framework_can_be_examined(self):
        code, out, _ = run("--list-frameworks")
        self.assertEqual(code, 0)
        self.assertIn("93 of 93", out)
        self.assertIn("no lexicon yet", out)


if __name__ == "__main__":
    unittest.main()
