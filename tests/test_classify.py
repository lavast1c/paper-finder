import pytest

from paper_finder.classify import (
    Label,
    QuestionRef,
    classify_questions,
    claude_labeller,
)
from paper_finder.db import connect, init_db
from paper_finder.labels import parse_labels

QP = "9702_s26_qp_11.pdf"


@pytest.fixture
def bank(tmp_path):
    """Four qp questions across two papers; nothing labelled yet."""
    db_path = tmp_path / "papers.db"
    init_db(db_path)
    with connect(db_path) as conn:
        conn.executemany(
            """INSERT INTO papers (id, subject_code, subject_name, year, session,
                   paper, variant, paper_type, filename)
               VALUES (?, '9702', 'Physics', ?, ?, ?, ?, 'qp', ?)""",
            [
                (1, 2026, "s", 1, 1, QP),
                (2, 2025, "w", 2, 1, "9702_w25_qp_21.pdf"),
            ],
        )
        conn.executemany(
            """INSERT INTO questions
                   (id, paper_id, question_number, question_text, is_mcq)
               VALUES (?, ?, ?, ?, ?)""",
            [
                (1, 1, 1, "A car accelerates uniformly from rest.", 1),
                (2, 1, 2, "Define electric potential difference.", 1),
                (3, 2, 1, "A wave on a string has frequency 50 Hz.", 0),
                (4, 2, 2, "State the principle of superposition.", 0),
            ],
        )
        conn.commit()
    return db_path, tmp_path / "labels.tsv"


def _recording_labeller(mapping):
    """Fake Labeller: `mapping` maps a question number *or* a
    (filename, number) pair to its codes. Records every number it saw in `seen`.
    A key absent from `mapping` -> that question is left out of the response."""
    seen: list[int] = []
    seen_keys: list[tuple[str, int]] = []

    def label(batch: list[QuestionRef]) -> list[Label]:
        out = []
        for q in batch:
            seen.append(q.question_number)
            seen_keys.append((q.filename, q.question_number))
            codes = mapping.get((q.filename, q.question_number), mapping.get(q.question_number))
            if codes is not None:
                out.append(Label(q.filename, q.question_number, tuple(codes)))
        return out

    label.seen = seen
    label.seen_keys = seen_keys
    return label


def test_labels_only_unlabelled_and_writes_sorted(bank):
    db_path, path = bank
    lab = _recording_labeller(
        {
            (QP, 1): ("s02",),
            (QP, 2): ("s09",),
            ("9702_w25_qp_21.pdf", 1): ("s07",),
            ("9702_w25_qp_21.pdf", 2): ("s08",),
        }
    )
    report = classify_questions(labeller=lab, db_path=db_path, path=path)

    assert report.considered == 4
    assert report.labelled == 4
    rows = parse_labels(path)
    assert [(r.filename, r.question_number, r.topic_codes, r.source) for r in rows] == [
        ("9702_s26_qp_11.pdf", 1, ("s02",), "llm"),
        ("9702_s26_qp_11.pdf", 2, ("s09",), "llm"),
        ("9702_w25_qp_21.pdf", 1, ("s07",), "llm"),
        ("9702_w25_qp_21.pdf", 2, ("s08",), "llm"),
    ]

    # a second run has nothing to do and leaves the file alone
    again = classify_questions(labeller=_recording_labeller({}), db_path=db_path, path=path)
    assert again.considered == 0
    assert again.skipped_existing == 4
    assert parse_labels(path) == rows


def test_relabel_resends_llm_rows_but_never_hand_rows(bank):
    db_path, path = bank
    path.write_text(
        "9702_s26_qp_11.pdf\t1\ts01\thand\n9702_s26_qp_11.pdf\t2\ts03\tllm\n",
        encoding="utf-8",
    )
    lab = _recording_labeller(
        {
            (QP, 1): ("s05",),  # would relabel the hand row -- must be ignored
            (QP, 2): ("s09",),  # llm row -> replaced
            ("9702_w25_qp_21.pdf", 1): ("s07",),
            ("9702_w25_qp_21.pdf", 2): ("s08",),
        }
    )
    classify_questions(labeller=lab, db_path=db_path, path=path, relabel=True)

    # the hand row's question is never even sent to the labeller
    assert (QP, 1) not in lab.seen_keys
    assert set(lab.seen_keys) == {(QP, 2), ("9702_w25_qp_21.pdf", 1), ("9702_w25_qp_21.pdf", 2)}
    rows = {(r.filename, r.question_number): r for r in parse_labels(path)}
    assert rows[(QP, 1)].topic_codes == ("s01",)  # hand, preserved
    assert rows[(QP, 1)].source == "hand"
    assert rows[(QP, 2)].topic_codes == ("s09",)  # llm, replaced
    assert rows[(QP, 2)].source == "llm"
    assert rows[("9702_w25_qp_21.pdf", 1)].topic_codes == ("s07",)


def test_limit_and_only(bank):
    db_path, path = bank
    lab = _recording_labeller({1: ("s02",), 2: ("s09",), 3: ("s07",), 4: ("s08",)})
    report = classify_questions(labeller=lab, db_path=db_path, path=path, only="qp_21", limit=1)
    assert report.considered == 1
    assert lab.seen == [1]  # first question of the w25 paper only
    assert [r.filename for r in parse_labels(path)] == ["9702_w25_qp_21.pdf"]


def test_dry_run_writes_nothing(bank):
    db_path, path = bank
    lab = _recording_labeller({1: ("s02",)})
    report = classify_questions(labeller=lab, db_path=db_path, path=path, limit=1, dry_run=True)
    assert report.labelled == 1
    assert report.dry_run is True
    assert not path.exists()


def test_unknown_codes_dropped_and_reported(bank):
    db_path, path = bank
    lab = _recording_labeller({1: ("s02", "s99"), 2: ("bogus",)})
    report = classify_questions(labeller=lab, db_path=db_path, path=path, limit=2)
    assert report.unknown_codes == ["bogus", "s99"]
    rows = {r.question_number: r for r in parse_labels(path)}
    assert rows[1].topic_codes == ("s02",)
    assert 2 not in rows  # its only code was invalid -> no row


def test_zero_label_question_writes_no_row(bank):
    db_path, path = bank
    lab = _recording_labeller({1: ("s02",), 2: ()})  # q2: model declined
    report = classify_questions(labeller=lab, db_path=db_path, path=path, limit=2)
    assert report.labelled == 1
    assert report.declined == 1
    assert [r.question_number for r in parse_labels(path)] == [1]


def test_codes_capped_at_three(bank):
    db_path, path = bank
    lab = _recording_labeller({1: ("s01", "s02", "s03", "s04", "s05")})
    classify_questions(labeller=lab, db_path=db_path, path=path, limit=1)
    assert parse_labels(path)[0].topic_codes == ("s01", "s02", "s03")


def test_default_labeller_needs_the_extra(monkeypatch):
    """With no injected labeller and anthropic absent, the factory explains the fix."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "anthropic":
            raise ImportError("No module named 'anthropic'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ImportError, match=r"\[classify\]"):
        claude_labeller("claude-sonnet-5")
