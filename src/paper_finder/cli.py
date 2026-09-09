"""Command-line entry point.

paper-finder init-db     create papers.db and its schema
paper-finder ingest      scan data/raw/ and record papers in the database
paper-finder extract     pull text out of every recorded PDF into data/processed/
paper-finder segment     split extracted question papers into questions
paper-finder answers     read answers from mark schemes and link them
paper-finder topics      load syllabus topic labels from labels/question_topics.tsv
paper-finder figures     render a cropped image of every question into data/crops/
paper-finder classify    label questions with syllabus topics via an LLM (needs "classify")
paper-finder build       run ingest -> extract -> segment -> answers -> topics -> figures
paper-finder download    fetch past-paper PDFs from a mirror into data/raw/
paper-finder publish     push the question bank to Supabase (needs the "publish" extra)
paper-finder search      find the paper a question came from
paper-finder evaluate    score search against eval/validation.tsv
paper-finder papers      list what is currently recorded
paper-finder questions   preview segmented questions
paper-finder serve       run the local web UI (needs the "web" extra)
"""

from __future__ import annotations

import argparse
import sys

from paper_finder import config
from paper_finder.db import connect, init_db
from paper_finder.download import download
from paper_finder.evaluate import evaluate, load_validation
from paper_finder.extract import extract_all
from paper_finder.figures import render_all
from paper_finder.ingest import ingest
from paper_finder.labels import load_topic_labels
from paper_finder.marks import extract_answers_all
from paper_finder.search import search
from paper_finder.segment import segment_all
from paper_finder.topics import TOPICS


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


def _cmd_segment(_args: argparse.Namespace) -> None:
    report = segment_all()
    total = sum(report.segmented.values())
    print(f"Papers segmented        : {len(report.segmented)}")
    for filename, count in report.segmented.items():
        print(f"    {filename}  ->  {count} questions")
    print(f"Total questions         : {total}")
    if report.unparsed:
        print(f"No questions found      : {', '.join(report.unparsed)}")
    if report.no_text_layer:
        print(f"No text layer           : {', '.join(report.no_text_layer)}")
    if report.missing_json:
        print(f"Not extracted yet       : {', '.join(report.missing_json)}")
        print("    Run: paper-finder extract")

    # Re-segmenting DELETEs every question, which cascades question_topics to
    # empty. Warn if the label file has data rows but the table is now bare.
    from paper_finder.labels import default_path

    path = default_path()
    has_labels = path.exists() and any(
        line.strip() and not line.strip().startswith("#")
        for line in path.read_text(encoding="utf-8").splitlines()
    )
    if has_labels:
        with connect() as conn:
            if conn.execute("SELECT COUNT(*) FROM question_topics").fetchone()[0] == 0:
                print("\nTopic labels cleared by re-segmenting. Run: paper-finder topics")


def _cmd_answers(_args: argparse.Namespace) -> None:
    report = extract_answers_all()
    total = sum(report.linked.values())
    print(f"Mark schemes read       : {len(report.linked)}")
    for filename, count in report.linked.items():
        print(f"    {filename}  ->  {count} answers linked")
    print(f"Total answers linked    : {total}")
    if report.no_question_paper:
        print(f"No matching question paper: {', '.join(report.no_question_paper)}")
    if report.missing_json:
        print(f"Not extracted yet       : {', '.join(report.missing_json)}  (run: extract)")


def _cmd_topics(_args: argparse.Namespace) -> None:
    report = load_topic_labels()
    print(f"Label rows read          : {report.rows}")
    print(f"Questions labelled       : {report.labelled}")
    print(f"Questions unlabelled     : {report.unlabelled}  (run: paper-finder classify)")
    for topic in TOPICS:
        count = report.counts.get(topic.code, 0)
        print(f"    {topic.code}  {topic.number:>2}. {topic.name:<32} {count:>4}")
    if report.orphans:
        print(f"Labels with no question  : {len(report.orphans)}")
        for ref in report.orphans[:10]:
            print(f"    - {ref}")
        if len(report.orphans) > 10:
            print(f"    ... and {len(report.orphans) - 10} more")
        print("    (those papers are not in data/raw/ -- run: paper-finder build)")


def _cmd_figures(args: argparse.Namespace) -> None:
    # `build` calls this with its own namespace, which has none of these flags.
    report = render_all(
        limit=getattr(args, "limit", None),
        only=getattr(args, "only", None),
        force=getattr(args, "force", False),
        dry_run=getattr(args, "dry_run", False),
    )
    verb = "would render" if report.dry_run else "written"
    print(f"Papers with crops       : {len(report.rendered)}")
    for filename, count in report.rendered.items():
        print(f"    {filename}  ->  {count} crops")
    print(f"Crop files {verb:<12} : {report.total_rendered}")
    if report.skipped_existing:
        print(f"Already rendered (kept) : {report.skipped_existing}  (use --force to redo)")
    if report.skipped_rotated:
        print(f"Rotated pages skipped   : {', '.join(report.skipped_rotated)}")
        print("    extract.py needs page-rotation handling before these can be cropped.")
    if report.bad_rects:
        print(f"Bad rectangles          : {len(report.bad_rects)}")
        for line in report.bad_rects[:10]:
            print(f"    - {line}")
    if report.missing_pdf:
        print(f"PDF missing from raw/   : {', '.join(report.missing_pdf)}")
    if not report.rendered and not report.skipped_existing:
        print("Nothing to render. Run: paper-finder build")


def _cmd_classify(args: argparse.Namespace) -> None:
    try:
        # Imported here so the other commands work without the optional classify extra.
        from paper_finder.classify import classify_questions
    except ImportError:
        print('Install the classify extra:  pip install -e ".[classify]"')
        return

    try:
        report = classify_questions(
            only=args.only,
            limit=args.limit,
            relabel=args.relabel,
            model=args.model,
            dry_run=args.dry_run,
        )
    except ImportError as exc:  # anthropic not installed -> claude_labeller raised
        print(exc)
        return

    verb = "Would label" if report.dry_run else "Labelled"
    print(f"Questions considered    : {report.considered}")
    print(f"{verb}                 : {report.labelled}")
    if report.declined:
        print(f"Model gave no code      : {report.declined}")
    print(f"Already labelled (kept) : {report.skipped_existing}")
    if report.unknown_codes:
        print(f"Unknown codes dropped   : {', '.join(report.unknown_codes)}")
    print(f"Rows in the TSV         : {report.written}")
    if not report.dry_run and report.labelled:
        print("\nReview labels/question_topics.tsv, then run: paper-finder topics")


def _cmd_build(_args: argparse.Namespace) -> None:
    for step in (_cmd_ingest, _cmd_extract, _cmd_segment, _cmd_answers, _cmd_topics, _cmd_figures):
        print(f"\n>>> {step.__name__.removeprefix('_cmd_')}")
        step(_args)


def _parse_years(text: str) -> list[int]:
    if "-" in text:
        lo, hi = (int(part) for part in text.split("-", 1))
        return list(range(lo, hi + 1))
    return [int(text)]


def _int_list(text: str) -> list[int]:
    return [int(part) for part in text.split(",") if part.strip()]


def _str_list(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


def _scope_from_args(args: argparse.Namespace) -> dict:
    scope = {key: list(value) for key, value in config.DOWNLOAD_SCOPE.items()}
    if args.subject:
        scope["subjects"] = list(args.subject)
    if args.years:
        scope["years"] = _parse_years(args.years)
    if args.sessions:
        scope["sessions"] = _str_list(args.sessions)
    if args.papers:
        scope["papers"] = _int_list(args.papers)
    if args.variants:
        scope["variants"] = _int_list(args.variants)
    return scope


def _cmd_download(args: argparse.Namespace) -> None:
    report = download(scope=_scope_from_args(args), limit=args.limit, dry_run=args.dry_run)

    if args.dry_run:
        print(f"Would fetch : {len(report.would_fetch)}")
        for url in report.would_fetch:
            print(f"    {url}")
        if report.skipped_existing:
            print(f"Already in data/raw/ : {len(report.skipped_existing)}")
        return

    print(f"Downloaded           : {len(report.downloaded)}")
    for name in report.downloaded:
        print(f"    + {name}")
    print(f"Already in data/raw/ : {len(report.skipped_existing)}")
    print(f"Not on mirror (404)  : {len(report.not_found)}")
    if report.failed:
        print(f"Failed               : {len(report.failed)}")
        for name, reason in report.failed:
            print(f"    ! {name}  {reason}")

    if report.aborted:
        print(f"\nABORTED: {report.aborted}")
    elif report.downloaded:
        print("\nNew PDFs added. Now run:  paper-finder build")


def _cmd_search(args: argparse.Namespace) -> None:
    init_db()
    hits = search(args.query, limit=args.limit)
    if not hits:
        print("No match. Have you run: paper-finder build ?")
        return
    for rank, hit in enumerate(hits, start=1):
        marks = f"[{hit.marks} mark{'' if hit.marks == 1 else 's'}]" if hit.marks else ""
        print(f"\n{rank}. {hit.label}  {marks}")
        print(f"   {_shorten(hit.question_text.splitlines()[0], 220)}")
        if hit.answer:
            answer = hit.answer if hit.answer.count("\n") == 0 else hit.answer.replace("\n", " ")
            print(f"   Answer: {_shorten(answer, 240)}")
        location = hit.filename
        if hit.page_start:
            location += f" (page {hit.page_start})"
        print(f"   {location}")


def _shorten(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _cmd_evaluate(_args: argparse.Namespace) -> None:
    cases = load_validation()
    result = evaluate(cases)
    print(f"Validation cases : {result.total}")
    print(f"Top-1 accuracy   : {result.top1_accuracy:.0%}  ({result.top1}/{result.total})")
    print(f"Top-5 accuracy   : {result.top5_accuracy:.0%}  ({result.top5}/{result.total})")
    if result.misses:
        print("\nNot the #1 hit:")
        for case, rank in result.misses:
            where = f"rank {rank}" if rank != -1 else "not in top 5"
            print(f"  [{where}] {case.phrase}  (want {case.filename} Q{case.question_number})")


def _cmd_questions(args: argparse.Namespace) -> None:
    init_db()
    sql = """
        SELECT p.filename, q.question_number, q.question_text, q.page_start
        FROM questions q JOIN papers p ON p.id = q.paper_id
    """
    params: list[object] = []
    if args.paper:
        sql += " WHERE p.filename LIKE ?"
        params.append(f"%{args.paper}%")
    sql += " ORDER BY p.filename, q.question_number"
    if args.limit:
        sql += " LIMIT ?"
        params.append(args.limit)

    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()

    if not rows:
        print("No questions. Run: paper-finder segment")
        return
    for r in rows:
        head = r["question_text"].splitlines()[0]
        if len(head) > 90:
            head = head[:87] + "..."
        print(f"{r['filename']:<22} Q{r['question_number']:<3} p{r['page_start']:<2}  {head}")
    print(f"\n{len(rows)} questions")


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


def _cmd_publish(args: argparse.Namespace) -> None:
    try:
        # Imported here so the other commands work without the optional publish extra.
        from paper_finder.publish import publish
    except ImportError:
        print('Install the publish extra:  pip install -e ".[publish]"')
        return

    report = publish(dry_run=args.dry_run, db_url=args.db_url)
    verb = "Would publish" if report.dry_run else "Published"
    print(f"{verb} papers    : {report.papers}")
    print(f"{verb} questions : {report.questions}  ({report.answers} with an answer)")
    if not report.dry_run:
        print("\nNo PDFs and no source URLs were sent. Now sign in to the deployed site.")


def _cmd_serve(args: argparse.Namespace) -> None:
    try:
        # Imported here so the other commands work without the optional web extra.
        import uvicorn

        from paper_finder.web.app import create_app
    except ImportError:
        print('Install the web extra:  pip install -e ".[web]"')
        return

    app = create_app(serve_pdfs=not args.no_pdfs)
    print(f"Paper Finder  ->  http://{args.host}:{args.port}   (Ctrl-C to stop)")
    if args.no_pdfs:
        print("PDF and question-crop serving disabled (--no-pdfs).")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


def _force_utf8_output() -> None:
    # CIE text contains Greek letters and maths symbols; the Windows console
    # defaults to cp1252 and would raise UnicodeEncodeError on print().
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> None:
    _force_utf8_output()
    parser = argparse.ArgumentParser(prog="paper-finder", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init-db", help="create papers.db and its schema")
    p_init.set_defaults(func=_cmd_init_db)

    p_ingest = sub.add_parser("ingest", help="scan data/raw/ and record papers")
    p_ingest.set_defaults(func=_cmd_ingest)

    p_extract = sub.add_parser("extract", help="extract text from recorded PDFs")
    p_extract.set_defaults(func=_cmd_extract)

    p_segment = sub.add_parser("segment", help="split question papers into questions")
    p_segment.set_defaults(func=_cmd_segment)

    p_answers = sub.add_parser("answers", help="link mark-scheme answers to questions")
    p_answers.set_defaults(func=_cmd_answers)

    p_topics = sub.add_parser("topics", help="load syllabus topic labels into the database")
    p_topics.set_defaults(func=_cmd_topics)

    p_classify = sub.add_parser(
        "classify", help="label questions with syllabus topics via an LLM (needs 'classify' extra)"
    )
    p_classify.add_argument("--only", help="only questions whose filename contains this substring")
    p_classify.add_argument("--limit", type=int, default=None, help="stop after N questions")
    p_classify.add_argument(
        "--relabel", action="store_true", help="also re-send questions that already have an llm row"
    )
    p_classify.add_argument(
        "--model", help=f"override the model (default: {config.CLASSIFY_MODEL})"
    )
    p_classify.add_argument(
        "--dry-run", action="store_true", help="run the model but do not write the TSV"
    )
    p_classify.set_defaults(func=_cmd_classify)

    p_figures = sub.add_parser(
        "figures", help="render a cropped image of every question into data/crops/"
    )
    p_figures.add_argument("--only", help="only papers whose filename contains this substring")
    p_figures.add_argument("--limit", type=int, default=None, help="stop after N crop files")
    p_figures.add_argument(
        "--force", action="store_true", help="re-render crops that already exist"
    )
    p_figures.add_argument("--dry-run", action="store_true", help="count crops, write nothing")
    p_figures.set_defaults(func=_cmd_figures)

    p_build = sub.add_parser(
        "build", help="ingest -> extract -> segment -> answers -> topics -> figures"
    )
    p_build.set_defaults(func=_cmd_build)

    p_download = sub.add_parser("download", help="fetch past papers from a mirror into data/raw/")
    p_download.add_argument(
        "--subject",
        action="append",
        metavar="CODE",
        help="subject code, repeatable (default: config scope)",
    )
    p_download.add_argument("--years", help="e.g. 2022-2024 or 2023")
    p_download.add_argument("--sessions", help="comma list, e.g. s,w")
    p_download.add_argument("--papers", help="comma list, e.g. 1,2")
    p_download.add_argument("--variants", help="comma list, e.g. 1,2,3")
    p_download.add_argument(
        "--limit", type=int, default=None, help="stop after N successful downloads"
    )
    p_download.add_argument(
        "--dry-run", action="store_true", help="list candidate URLs, fetch nothing"
    )
    p_download.set_defaults(func=_cmd_download)

    p_publish = sub.add_parser("publish", help="push the question bank to Supabase")
    p_publish.add_argument("--db-url", help="Postgres URI (default: SUPABASE_DB_URL env / .env)")
    p_publish.add_argument("--dry-run", action="store_true", help="count rows, send nothing")
    p_publish.set_defaults(func=_cmd_publish)

    p_search = sub.add_parser("search", help="find the paper a question came from")
    p_search.add_argument("query", help="a few words of the question")
    p_search.add_argument("--limit", type=int, default=5, help="number of results")
    p_search.set_defaults(func=_cmd_search)

    p_evaluate = sub.add_parser("evaluate", help="score search against eval/validation.tsv")
    p_evaluate.set_defaults(func=_cmd_evaluate)

    p_questions = sub.add_parser("questions", help="preview segmented questions")
    p_questions.add_argument("--paper", help="filter by filename substring, e.g. qp_12")
    p_questions.add_argument("--limit", type=int, default=0, help="max rows to show")
    p_questions.set_defaults(func=_cmd_questions)

    p_papers = sub.add_parser("papers", help="list papers recorded in the database")
    p_papers.set_defaults(func=_cmd_papers)

    p_serve = sub.add_parser("serve", help="run the local web UI")
    p_serve.add_argument(
        "--host", default="127.0.0.1", help="bind address (default: localhost only)"
    )
    p_serve.add_argument("--port", type=int, default=8000, help="port (default: 8000)")
    p_serve.add_argument(
        "--no-pdfs",
        action="store_true",
        help="do not serve PDFs or question-crop images (required for public hosting)",
    )
    p_serve.set_defaults(func=_cmd_serve)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
