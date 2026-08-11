"""The README makes checkable claims. These check them.

A front page that says "59 of 93 controls" is the first thing a reader
believes and the last thing anyone remembers to update. The numbers there
are facts about the code, so the code asserts them.

Prose is not tested, only figures and commands that can go stale.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from audit_readiness_ledger.cli import build_parser, frameworks_with_a_lexicon
from audit_readiness_ledger.lexicon_loader import coverage_of_lexicon, load_framework

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")


class TheCoverageFiguresAreCurrent(unittest.TestCase):
    def test_the_frameworks_table_matches_the_lexicon(self):
        examined, total = coverage_of_lexicon("iso-27001-2022")
        self.assertIn(f"| {total} | {examined} |", README)

    def test_a_complete_lexicon_is_claimed_only_while_it_is_complete(self):
        examined, total = coverage_of_lexicon("iso-27001-2022")
        claims_complete = f"Covers all {total} Annex A controls" in README
        self.assertEqual(
            claims_complete,
            examined == total,
            f"README claims complete coverage={claims_complete} but the lexicon "
            f"has {examined} of {total}. One of the two has to change.",
        )

    def test_the_csf_catalogue_size_is_right(self):
        self.assertIn(f"| {len(load_framework('nist-csf-2.0').controls)} |", README)

    def test_csf_is_still_honestly_marked_as_not_examinable(self):
        """The moment a CSF lexicon lands, this line has to change."""
        if "nist-csf-2.0" in frameworks_with_a_lexicon():
            self.fail("A CSF lexicon exists now. Update the frameworks table in README.md.")
        self.assertIn("not yet — catalogue only", README)


class TheCommandsInTheReadmeExist(unittest.TestCase):
    def test_every_documented_flag_is_a_real_flag(self):
        known = {option for action in build_parser()._actions for option in action.option_strings}
        documented = set(re.findall(r"(?<![\w-])(--[a-z][a-z-]+)", README))
        # Not flags of this tool.
        documented -= {"--check"}
        self.assertEqual(documented - known, set())

    def test_the_example_command_points_at_the_folder_that_exists(self):
        self.assertIn("audit-readiness-ledger examples/meltemi-logistics/documents", README)
        self.assertTrue((ROOT / "examples" / "meltemi-logistics" / "documents").is_dir())

    def test_the_files_the_readme_links_to_are_there(self):
        for link in re.findall(r"\]\((?!http)([^)#]+)\)", README):
            with self.subTest(link=link):
                self.assertTrue((ROOT / link).exists(), f"README links to missing {link}")


if __name__ == "__main__":
    unittest.main()
