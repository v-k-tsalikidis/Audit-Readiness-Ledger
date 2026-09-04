"""The command line.

One decision here is worth stating, because it looks like a small thing and
is not: **finding gaps is not an error**.

A tool that exits non-zero because a document set has gaps has quietly
turned itself into a judge. It says the set failed. This one does not make
that claim anywhere else, and the exit code is not the place to start. So a
run that completes exits 0 whatever it found, and a run that could not
happen -- no such folder, nothing readable in it, a lexicon that cannot
load -- exits 1.

Anyone who does want a build to break on gaps can ask for it with
`--fail-on-gaps`, which exits 2. That is a policy the user chose, stated in
their own pipeline, rather than one this tool imposed on them.

The other decision is `--today`. Staleness depends on the date, so a report
run tomorrow differs from one run today. Passing the date makes a run
reproducible, which matters when the output is going into an audit file
and someone has to be able to produce it again.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date, datetime, timezone
from pathlib import Path

from . import __version__
from .documents import READABLE, load_directory
from .hygiene import check_cross_references, check_document
from .lexicon_loader import CATALOGUE, LEXICON, load_framework, load_signatures
from .report import Analysis, render_json, render_markdown
from .signatures import Coverage, evaluate_all

DEFAULT_FRAMEWORK = "iso-27001-2022"


def available_frameworks() -> list[str]:
    return sorted(path.stem for path in CATALOGUE.glob("*.json"))


def frameworks_with_a_lexicon() -> list[str]:
    return sorted(path.stem for path in LEXICON.glob("*.yaml"))


def today_here() -> date:
    """The local calendar date, which is the one on the document."""
    return datetime.now(timezone.utc).astimezone().date()


def parse_today(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"{text!r} is not a date. Write it as YYYY-MM-DD, for example 2026-08-10."
        ) from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audit-readiness-ledger",
        description=(
            "Read a folder of security policies and report which controls none "
            "of them address. It never reports that a control is met."
        ),
        epilog=(
            "Try it on the bundled example set:\n"
            "  audit-readiness-ledger examples/meltemi-logistics/documents\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "folder",
        nargs="?",
        type=Path,
        help="folder holding the policies and procedures to read",
    )
    parser.add_argument(
        "--framework",
        default=DEFAULT_FRAMEWORK,
        help=f"control catalogue to report against (default: {DEFAULT_FRAMEWORK})",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        dest="output_format",
        help="markdown to read, json to feed something else (default: markdown)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="write the report to this file instead of standard output",
    )
    parser.add_argument(
        "--today",
        type=parse_today,
        default=None,
        metavar="YYYY-MM-DD",
        help=(
            "the date to judge review dates against, so a run can be repeated "
            "later and produce the same report (default: today)"
        ),
    )
    parser.add_argument(
        "--fail-on-gaps",
        action="store_true",
        help=(
            "exit 2 when any examined control is addressed by no document. Off "
            "by default: a gap is a finding, not an error"
        ),
    )
    parser.add_argument(
        "--list-frameworks",
        action="store_true",
        help="show which catalogues are available and which have a lexicon",
    )
    parser.add_argument(
        "--web",
        "--ui",
        action="store_true",
        dest="launch_web",
        help="launch the interactive Dual-Engine Assurance & Gatekeeper web dashboard",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"audit-readiness-ledger {__version__}",
    )
    return parser


def _list_frameworks(stream) -> int:
    with_lexicon = set(frameworks_with_a_lexicon())
    print("Catalogues in this build:\n", file=stream)
    for slug in available_frameworks():
        framework = load_framework(slug)
        if slug in with_lexicon:
            examined, total = len(load_signatures(slug, framework)), len(framework.controls)
            state = f"lexicon covers {examined} of {total} controls"
        else:
            state = "no lexicon yet, so nothing can be looked for"
        print(f"  {slug}\n      {framework.name}\n      {state}", file=stream)
    print(
        "\nA catalogue without a lexicon lists the controls but cannot examine\n"
        "any of them, so it is not accepted as --framework.",
        file=stream,
    )
    return 0


def analyse(folder: Path, framework_slug: str, today: date) -> Analysis:
    """Run every stage over one folder. Raises ValueError with a readable reason."""
    framework = load_framework(framework_slug)
    signatures = load_signatures(framework_slug, framework)

    loaded = load_directory(folder)
    documents = list(loaded.documents)
    if not documents:
        # Taken from the reader rather than written out again here, so the
        # message cannot fall behind what the reader actually accepts.
        readable = ", ".join(sorted(READABLE))
        raise ValueError(
            f"Nothing in {folder} could be read. This tool reads {readable}. "
            f"{len(loaded.skipped)} file(s) were skipped; convert them and try again."
        )

    return Analysis(
        framework=framework,
        findings=tuple(evaluate_all(framework.ids, signatures, documents)),
        hygiene=tuple(f for document in documents for f in check_document(document, today)),
        cross_references=tuple(check_cross_references(documents)),
        documents_read=tuple(document.name for document in documents),
        units=loaded.units,
        skipped=loaded.skipped,
        # The path as the user typed it. Just the folder name reads as
        # "Audit readiness: documents", which names nothing.
        source=str(folder),
        run_date=today,
    )


def _summarise(analysis: Analysis, stream) -> None:
    """A line on stderr, so piping the report somewhere still tells you what happened."""
    grouped = analysis.by_coverage
    gaps = len(grouped[Coverage.NOT_ADDRESSED])
    unclear = len(grouped[Coverage.UNCLEAR])
    print(
        f"Read {len(analysis.documents_read)} documents. "
        f"Examined {analysis.examined} of {len(analysis.framework.controls)} controls: "
        f"{gaps} addressed by nothing, {unclear} for a person to read.",
        file=stream,
    )
    if analysis.skipped:
        print(
            f"{len(analysis.skipped)} file(s) could not be read; they are listed in the report.",
            file=stream,
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_frameworks:
        return _list_frameworks(sys.stdout)

    if args.launch_web:
        try:
            import pandas  # noqa: F401
            import streamlit  # noqa: F401
        except ImportError:
            print(
                "The web assurance suite requires 'streamlit' and 'pandas'.\n"
                "Install them with:\n"
                "  pip install 'audit-readiness-ledger[web]'\n"
                "or directly via:\n"
                "  pip install streamlit pandas",
                file=sys.stderr,
            )
            return 1

        import subprocess

        app_path = Path(__file__).resolve().parent / "app.py"
        return subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)]).returncode

    if args.folder is None:
        parser.print_usage(sys.stderr)
        print(
            "\nGive it a folder to read. To see what it does first:\n"
            "  audit-readiness-ledger examples/meltemi-logistics/documents",
            file=sys.stderr,
        )
        return 1

    if args.framework not in frameworks_with_a_lexicon():
        known = ", ".join(frameworks_with_a_lexicon()) or "none"
        print(
            f"No lexicon for {args.framework!r}, so every control would come back "
            f"unexamined and the report would say nothing.\n"
            f"Frameworks that can be examined: {known}.\n"
            f"Run --list-frameworks to see the catalogues in this build.",
            file=sys.stderr,
        )
        return 1

    today = args.today or today_here()

    try:
        analysis = analyse(args.folder, args.framework, today)
    except (FileNotFoundError, NotADirectoryError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1

    rendered = render_json(analysis) if args.output_format == "json" else render_markdown(analysis)

    if args.output:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        except OSError as error:
            print(f"Could not write {args.output}: {error}", file=sys.stderr)
            return 1
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(rendered)

    _summarise(analysis, sys.stderr)

    if args.fail_on_gaps and analysis.by_coverage[Coverage.NOT_ADDRESSED]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
