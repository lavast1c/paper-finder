"""Command-line entry point.

paper-finder init-db     create papers.db and its schema
paper-finder ingest      scan data/raw/ and record papers in the database
paper-finder extract     pull text out of every recorded PDF into data/processed/
paper-finder papers      list what is currently recorded
"""

from __future__ import annotations

import argparse

from paper_finder.db import connect, init_db
from paper_finder.extract import extract_all
from paper_finder.ingest import ingest


def _cmd_init_db(_args: argparse.Namespace) -> None:
    init_db()
    print("Initialised schema in papers.db")


def _cmd_ingest(_args: argparse.Namespace) -> None:
    report = ingest()
    print(f"PDFs found in data/raw/ : {report.found}")
    print(f"Ingested / updated      : {report.ingested}")
    if report.pruned:
        print(f"Pruned (file removed)   : {len(report.pruned)}")
        for name in report.pruned:
            print(f"    - {name}")
    if report.skipped:
        print(f"Skipped (unrecognised)  : {len(report.skipped)}")
        for name in report.skipped:
            print(f"    - {name}")
    if report.unknown_subjects:
        codes = ", ".join(report.unknown_subjects)
        print(f"Unknown subject codes   : {codes}")
        print("    Add them to SUBJECTS in src/paper_finder/config.py, then re-run ingest.")


def _cmd_extract(_args: argparse.Namespace) -> None:
    report = extract_all()
    print(f"Extracted               : {len(report.extracted)}")
    if report.no_text_layer:
        print(f"No text layer (need OCR): {len(report.no_text_layer)}")
        for name in report.no_text_layer:
            print(f"    - {name}")
    if report.missing_pdf:
        print(f"PDF missing from raw/   : {len(report.missing_pdf)}")
        for name in report.missing_pdf:
            print(f"    - {name}")
    if not report.extracted:
        print("Nothing to extract. Run: paper-finder ingest")


def _cmd_papers(_args: argparse.Namespace) -> None:
    init_db()  # so the command is safe to run before any ingest
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT filename, subject_code, subject_name, year, session,
                   paper, variant, paper_type
            FROM papers
            ORDER BY subject_code, year, session, paper, variant, paper_type
            """
        ).fetchall()

    if not rows:
        print("No papers recorded yet.")
        print("Put PDFs in data/raw/ and run: paper-finder ingest")
        return

    for r in rows:
        if r["paper"] is None:
            paper_variant = "-"
        else:
            paper_variant = f"{r['paper']}{r['variant'] if r['variant'] is not None else ''}"
        subject = r["subject_name"] or r["subject_code"]
        print(
            f"{r['filename']:<24}  {subject:<12} {r['year']} {r['session']}  "
            f"paper {paper_variant:<3}  {r['paper_type']}"
        )
    print(f"\n{len(rows)} papers")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="paper-finder", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init-db", help="create papers.db and its schema")
    p_init.set_defaults(func=_cmd_init_db)

    p_ingest = sub.add_parser("ingest", help="scan data/raw/ and record papers")
    p_ingest.set_defaults(func=_cmd_ingest)

    p_extract = sub.add_parser("extract", help="extract text from recorded PDFs")
    p_extract.set_defaults(func=_cmd_extract)

    p_papers = sub.add_parser("papers", help="list papers recorded in the database")
    p_papers.set_defaults(func=_cmd_papers)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
