"""Label every question with its CIE syllabus sections, using an LLM.

``classify_questions()`` reads the segmented question bank, sends the questions it
has no label for (in batches) to a :data:`Labeller`, filters the returned codes
against :data:`paper_finder.topics.CODES`, and merges the result into
``labels/question_topics.tsv`` -- the file ``paper-finder topics`` loads.

The :data:`Labeller` seam mirrors ``download.Fetcher`` / ``publish._psycopg
_connector``: the default (:func:`claude_labeller`) calls Claude via the optional
``[classify]`` extra, but every test injects a fake and never imports
``anthropic``. Network I/O, so this is **not** part of ``paper-finder build`` --
same rule as ``download`` and ``publish``.

Design guards, from the plan:

* batched (20) so ~980 questions are ~50 calls with the taxonomy prompt cached;
* structured output (a forced tool call) so the model cannot answer in prose;
* codes outside the taxonomy are dropped into ``report.unknown_codes``, never
  written;
* a question the model declines to label gets **no row**, never a fabricated one;
* at most 3 codes per question, so an over-tagged answer is trimmed not trusted;
* ``hand`` rows in the TSV are never touched; ``llm`` rows are replaced only for
  the questions in this run (``--relabel`` widens that to already-labelled ones).
"""

from __future__ import annotations

import os
import textwrap
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from paper_finder import config
from paper_finder.db import connect, init_db
from paper_finder.labels import LabelRow, default_path, parse_labels
from paper_finder.publish import _read_dotenv
from paper_finder.topics import CODES, TOPICS

MAX_CODES_PER_QUESTION = 3


def _resolve_api_key() -> str | None:
    """``ANTHROPIC_API_KEY`` from the env, else the gitignored ``.env`` (same
    lookup as ``publish`` / ``publish-figures``). ``None`` lets the SDK raise its
    own "no key" error."""
    return os.environ.get("ANTHROPIC_API_KEY") or _read_dotenv(config.PROJECT_ROOT / ".env").get(
        "ANTHROPIC_API_KEY"
    )


@dataclass(frozen=True)
class QuestionRef:
    """One question handed to the labeller."""

    filename: str
    question_number: int
    is_mcq: bool
    text: str


@dataclass(frozen=True)
class Label:
    """A labeller's verdict for one question. ``topic_codes`` may be empty
    (the model declined) or contain unknown codes (filtered out on merge)."""

    filename: str
    question_number: int
    topic_codes: tuple[str, ...]


Labeller = Callable[[list[QuestionRef]], list[Label]]


@dataclass
class ClassifyReport:
    considered: int = 0  # unlabelled (or, with --relabel, all) questions sent
    labelled: int = 0  # questions that came back with >= 1 valid code
    declined: int = 0  # sent but got no usable code
    skipped_existing: int = 0  # already in the TSV, left alone
    unknown_codes: list[str] = field(default_factory=list)  # codes the model invented
    written: int = 0  # total rows in the rewritten TSV
    dry_run: bool = False


_QUESTIONS_SQL = """
SELECT p.filename, q.question_number, q.is_mcq, q.question_text
FROM questions q
JOIN papers p ON p.id = q.paper_id
WHERE p.paper_type = 'qp'
ORDER BY p.year DESC, p.session DESC, p.paper, p.variant, q.question_number
"""


def load_questions(db_path: Path | None = None) -> list[QuestionRef]:
    init_db(db_path)
    with connect(db_path) as conn:
        rows = conn.execute(_QUESTIONS_SQL).fetchall()
    return [
        QuestionRef(
            filename=r["filename"],
            question_number=r["question_number"],
            is_mcq=bool(r["is_mcq"]),
            text=r["question_text"] or "",
        )
        for r in rows
    ]


def _existing_rows(path: Path) -> dict[tuple[str, int], LabelRow]:
    if not path.exists():
        return {}
    return {(r.filename, r.question_number): r for r in parse_labels(path)}


_TSV_HEADER = """\
# Syllabus topic labels for the question bank.
#
# One row per labelled question:
#     filename <TAB> question_number <TAB> topic_codes <TAB> source
#
# topic_codes : comma-separated CIE 9702 AS syllabus section codes (s01..s11),
#               multi-label -- list every section the question tests.
# source      : "hand" (reviewed by a person) or "llm" (`paper-finder classify`).
#
# Keyed on (filename, question_number), NOT questions.id -- `paper-finder build`
# reassigns ids every run. Sorted by (filename, question_number). No question
# text lives here, only public paper metadata + the section enum.
#
# Populate with:  paper-finder classify   (writes llm rows here)
# then load with: paper-finder topics
"""


def write_labels(rows: Sequence[LabelRow], path: Path) -> None:
    """Rewrite the whole TSV, sorted by (filename, question_number)."""
    ordered = sorted(rows, key=lambda r: (r.filename, r.question_number))
    lines = [_TSV_HEADER]
    for r in ordered:
        lines.append(f"{r.filename}\t{r.question_number}\t{','.join(r.topic_codes)}\t{r.source}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _batched(items: Sequence, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def classify_questions(
    *,
    labeller: Labeller | None = None,
    db_path: Path | None = None,
    path: Path | None = None,
    only: str | None = None,
    limit: int | None = None,
    relabel: bool = False,
    batch_size: int | None = None,
    model: str | None = None,
    dry_run: bool = False,
) -> ClassifyReport:
    """Classify unlabelled questions and merge the result into the TSV.

    ``only`` keeps questions whose filename contains that substring. ``limit``
    caps how many are sent (after ``only``), so an interrupted run resumes and a
    seeding run stays small. ``relabel`` re-sends questions that already have an
    ``llm`` row (``hand`` rows are always kept). Returns a :class:`ClassifyReport`;
    with ``dry_run`` nothing is written.
    """
    path = path if path is not None else default_path()
    batch_size = batch_size or config.CLASSIFY_BATCH_SIZE
    report = ClassifyReport(dry_run=dry_run)

    questions = load_questions(db_path)
    if only:
        questions = [q for q in questions if only in q.filename]

    existing = _existing_rows(path)
    hand = {k: r for k, r in existing.items() if r.source == "hand"}
    llm = {k: r for k, r in existing.items() if r.source == "llm"}

    def is_candidate(q: QuestionRef) -> bool:
        key = (q.filename, q.question_number)
        if key in hand:
            return False  # a person has ruled on it
        return relabel or key not in llm

    candidates = [q for q in questions if is_candidate(q)]
    report.skipped_existing = len(questions) - len(candidates)
    if limit is not None:
        candidates = candidates[:limit]
    report.considered = len(candidates)

    if not candidates:
        # Nothing to do -- leave the file exactly as it is.
        report.written = len(existing)
        return report

    if labeller is None:
        labeller = claude_labeller(model or config.CLASSIFY_MODEL)

    fresh: dict[tuple[str, int], LabelRow] = {}
    unknown: set[str] = set()
    for batch in _batched(candidates, batch_size):
        for label in labeller(list(batch)):
            key = (label.filename, label.question_number)
            clean: list[str] = []
            for code in label.topic_codes:
                if code in CODES:
                    if code not in clean:
                        clean.append(code)
                else:
                    unknown.add(code)
            clean = clean[:MAX_CODES_PER_QUESTION]
            if clean:
                fresh[key] = LabelRow(label.filename, label.question_number, tuple(clean), "llm")

    labelled_keys = {(q.filename, q.question_number) for q in candidates} & fresh.keys()
    report.labelled = len(labelled_keys)
    report.declined = report.considered - report.labelled
    report.unknown_codes = sorted(unknown)

    # Merge: all hand rows, every llm row we did not just refresh, then the new ones.
    merged: dict[tuple[str, int], LabelRow] = dict(hand)
    for key, row in llm.items():
        if key not in fresh:
            merged[key] = row
    merged.update(fresh)

    report.written = len(merged)
    if not dry_run:
        write_labels(list(merged.values()), path)
    return report


# --------------------------------------------------------------------------- LLM

_TOOL = {
    "name": "record_topics",
    "description": "Record the CIE 9702 AS syllabus section(s) each question tests.",
    "input_schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "n": {"type": "integer", "description": "the question number given"},
                        "codes": {
                            "type": "array",
                            "items": {"type": "string", "enum": sorted(CODES)},
                            "description": (
                                "1-3 section codes, most central first; omit the "
                                "question entirely if none fit"
                            ),
                        },
                    },
                    "required": ["n", "codes"],
                },
            }
        },
        "required": ["questions"],
    },
}


def _taxonomy_prompt() -> str:
    parts = [
        "You classify Cambridge International AS & A Level Physics (9702) exam "
        "questions by syllabus section. The sections are:\n"
    ]
    for t in TOPICS:
        parts.append(f"{t.code} — {t.name}\n{textwrap.fill(t.blurb, 92)}\n")
    parts.append(
        "\nFor each question, give every section it genuinely tests (most "
        "questions: one; a question that spans two, e.g. 'define force then check "
        "unit homogeneity', gets both). At most three, ordered by centrality. If "
        "no section fits, leave that question out of your answer. Use only the "
        "codes listed above."
    )
    return "\n".join(parts)


def _render_batch(batch: Sequence[QuestionRef]) -> str:
    out = []
    for q in batch:
        kind = "multiple-choice" if q.is_mcq else "structured"
        body = " ".join(q.text.split())[:1200]
        out.append(f"--- question {q.question_number} ({kind}) ---\n{body}")
    return "\n\n".join(out)


def claude_labeller(model: str) -> Labeller:
    """The real labeller: one forced ``record_topics`` tool call per batch, with
    the taxonomy in a cached system block. Needs the ``[classify]`` extra."""
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - exercised via the CLI hint
        raise ImportError(
            'paper-finder classify needs the [classify] extra: pip install -e ".[classify]"'
        ) from exc

    client = anthropic.Anthropic(api_key=_resolve_api_key())
    system = [
        {
            "type": "text",
            "text": _taxonomy_prompt(),
            "cache_control": {"type": "ephemeral"},
        }
    ]

    def label(batch: list[QuestionRef]) -> list[Label]:
        by_number = {q.question_number: q for q in batch}
        message = client.messages.create(
            model=model,
            max_tokens=2048,
            system=system,
            tools=[_TOOL],
            tool_choice={"type": "tool", "name": "record_topics"},
            messages=[{"role": "user", "content": _render_batch(batch)}],
        )
        labels: list[Label] = []
        for block in message.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            for item in block.input.get("questions", []):
                q = by_number.get(item.get("n"))
                if q is None:
                    continue
                codes = tuple(str(c) for c in item.get("codes", []))
                labels.append(Label(q.filename, q.question_number, codes))
        return labels

    return label
