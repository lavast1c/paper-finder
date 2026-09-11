import pytest

from paper_finder.db import connect, init_db
from paper_finder.publish import _read_dotenv, publish, read_local, resolve_db_url
from paper_finder.topics import CODES


@pytest.fixture
def local_db(tmp_path):
    """A local SQLite corpus: one qp with 2 questions (1 answered), one qp with
    no questions, and one ms row — only the first qp should be published."""
    db_path = tmp_path / "papers.db"
    init_db(db_path)
    with connect(db_path) as conn:
        conn.executemany(
            """INSERT INTO papers (id, subject_code, subject_name, year, session,
                   paper, variant, paper_type, filename)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (1, "9702", "Physics", 2026, "s", 1, 1, "qp", "9702_s26_qp_11.pdf"),
                (2, "9702", "Physics", 2026, "s", 1, 1, "ms", "9702_s26_ms_11.pdf"),
                (3, "9702", "Physics", 2026, "s", 2, 1, "qp", "9702_s26_qp_21.pdf"),
            ],
        )
        conn.executemany(
            """INSERT INTO questions
                   (id, paper_id, question_number, question_text, marks, is_mcq,
                    page_start, has_figure, crop_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (1, 1, 1, "A ball is thrown horizontally.", 1, 1, 4, 0, 1),
                (2, 1, 2, "A block rests on a slope, as shown in Fig. 2.1.", 9, 0, 5, 1, 3),
            ],
        )
        conn.execute(
            """INSERT INTO answers
                   (question_id, answer_text, source, answer_crop_rects, answer_crop_count)
               VALUES (1, 'C', 'mark_scheme', '[[1,0,0,1,1],[1,0,0,1,1]]', 2)"""
        )
        conn.executemany(
            "INSERT INTO question_topics (question_id, topic_code) VALUES (?, ?)",
            [(1, "s02"), (2, "s04"), (2, "s03")],
        )
        conn.commit()
    return db_path


class FakeCursor:
    """A cursor context manager that records SQL and can raise partway through."""

    def __init__(self, log, fail_on):
        self.log = log
        self.fail_on = fail_on

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.log.append(("execute", sql, list(params) if params else None))
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError("boom")

    def executemany(self, sql, rows):
        self.log.append(("executemany", sql, list(rows)))
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError("boom")


class FakeConn:
    """Mimics psycopg3: `with conn` commits on clean exit, rolls back on raise."""

    def __init__(self, log, fail_on=None):
        self.log = log
        self.fail_on = fail_on
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        if exc_type is None:
            self.committed = True
        else:
            self.rolled_back = True
        return False

    def cursor(self):
        return FakeCursor(self.log, self.fail_on)


def test_read_local_only_qp_with_questions(local_db):
    papers, questions = read_local(local_db)
    assert [p[7] for p in papers] == ["9702_s26_qp_11.pdf"]  # not the ms, not the empty qp
    assert len(questions) == 2
    assert questions[0][3] == "A ball is thrown horizontally."
    assert (questions[0][5], questions[1][5]) == (False, True)  # has_figure -> real bool
    assert questions[0][6] == "C"  # answer_text flattened in
    assert questions[1][6] is None
    assert questions[0][7] == ["s02"]  # topic codes -> sorted list, [] when none
    assert questions[1][7] == ["s03", "s04"]
    assert (questions[0][8], questions[1][8]) == (1, 3)  # crop_count rides at index 8
    assert (questions[0][9], questions[1][9]) == (2, 0)  # answer_crop_count; 0 when no answer row
    assert (questions[0][10], questions[1][10]) == (True, False)  # is_mcq -> real bool


def test_dry_run_counts_and_sends_nothing(local_db):
    calls = []
    report = publish(db_path=local_db, dry_run=True, connect_pg=lambda url: calls.append(url))
    assert (report.papers, report.questions, report.answers) == (1, 2, 1)
    assert report.dry_run is True
    assert calls == []


def test_publish_statement_order_and_commit(local_db):
    log = []
    conn = FakeConn(log)
    publish(db_path=local_db, db_url="postgres://x", connect_pg=lambda url: conn)

    kinds = [row[0] for row in log]
    sqls = [row[1] for row in log]
    assert kinds == ["execute", "executemany", "executemany", "executemany"]
    assert "DELETE FROM public.papers" in sqls[0]
    assert "INSERT INTO public.topics" in sqls[1]
    assert "INSERT INTO public.papers" in sqls[2]
    assert "INSERT INTO public.questions" in sqls[3]
    assert conn.committed and not conn.rolled_back

    # the topics upsert carries every taxonomy, each row tagged with its subject
    topic_rows = log[1][2]
    assert {r[0] for r in topic_rows} == set(CODES)
    by_code = {r[0]: r for r in topic_rows}
    assert by_code["s01"][4] == "Physics"
    assert by_code["fp1"][4] == "Further Pure Mathematics"
    assert by_code["fs1"][4] == "Further Probability & Statistics"
    assert by_code["pm1"][4] == "Pure Mathematics 1"
    assert by_code["ch01"][4] == "Chemistry"
    assert by_code["ps1"][4] == "Probability & Statistics 1"

    # every question row carries the is_mcq bool as its last value
    question_rows = log[3][2]
    assert [r[-1] for r in question_rows] == [True, False]


def test_publish_rolls_back_on_failure(local_db):
    log = []
    conn = FakeConn(log, fail_on="INSERT INTO public.questions")
    with pytest.raises(RuntimeError):
        publish(db_path=local_db, db_url="postgres://x", connect_pg=lambda url: conn)
    assert conn.rolled_back and not conn.committed


def test_resolve_db_url_precedence(tmp_path, monkeypatch):
    assert resolve_db_url("explicit://url") == "explicit://url"

    monkeypatch.setenv("SUPABASE_DB_URL", "env://url")
    assert resolve_db_url() == "env://url"


def test_resolve_db_url_error_names_session_pooler(monkeypatch):
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    with pytest.raises(RuntimeError, match="[Ss]ession pooler"):
        resolve_db_url()


def test_read_dotenv_parsing(tmp_path):
    (tmp_path / ".env").write_text(
        '# comment\nSUPABASE_DB_URL = "postgres://a:b@host:5432/postgres"\nBLANK=\n',
        encoding="utf-8",
    )
    values = _read_dotenv(tmp_path / ".env")
    assert values["SUPABASE_DB_URL"] == "postgres://a:b@host:5432/postgres"
    assert values["BLANK"] == ""
