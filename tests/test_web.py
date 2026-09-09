import pytest
from fastapi.testclient import TestClient

from paper_finder.db import connect, init_db
from paper_finder.web.app import create_app, resolve_pdf

QP = "9702_s26_qp_11.pdf"


@pytest.fixture
def corpus(tmp_path):
    db_path = tmp_path / "papers.db"
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / QP).write_bytes(b"%PDF-1.4\n%fake pdf\n")

    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute(
            """INSERT INTO papers (id, subject_code, subject_name, year, session,
                   paper, variant, paper_type, filename)
               VALUES (1, '9702', 'Physics', 2026, 's', 1, 1, 'qp', ?)""",
            (QP,),
        )
        conn.executemany(
            """INSERT INTO questions
                   (id, paper_id, question_number, question_text, marks, is_mcq,
                    page_start, has_figure)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (1, 1, 1, "A ball is thrown horizontally with a speed of 10 m/s.", 1, 1, 4, 0),
                (2, 1, 2, "What is an SI base quantity?\nA. ampere\nB. charge", 1, 1, 3, 0),
                (3, 1, 3, "A block rests on a rough slope in equilibrium.", 9, 0, 5, 1),
            ],
        )
        conn.executemany(
            "INSERT INTO answers (question_id, answer_text, source) VALUES (?, ?, ?)",
            [
                (1, "C", "mark_scheme"),
                (3, "3(a) resultant force is zero\nB1\n3(b) ...long mark scheme...", "mark_scheme"),
            ],
        )
        conn.executemany(
            "INSERT INTO question_topics (question_id, topic_code) VALUES (?, ?)",
            [(1, "s02"), (2, "s01"), (3, "s03"), (3, "s04")],  # q3 multi-label
        )
        conn.execute("INSERT INTO questions_fts(questions_fts) VALUES ('rebuild')")
        conn.commit()
    return db_path, raw_dir


@pytest.fixture
def client(corpus):
    db_path, raw_dir = corpus
    return TestClient(create_app(db_path=db_path, raw_dir=raw_dir))


def test_index_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Paper Finder" in r.text


def test_static_assets_served(client):
    for asset in ("/static/app.js", "/static/common.js", "/static/style.css", "/static/index.html"):
        assert client.get(asset).status_code == 200


def test_search_returns_expected_hit(client):
    body = client.get("/api/search", params={"q": "ball thrown horizontally speed"}).json()
    assert body["query"] == "ball thrown horizontally speed"
    assert body["count"] >= 1
    top = body["results"][0]
    assert top["question_number"] == 1
    assert top["answer"] == "C"
    assert top["session_name"] == "May/June"
    assert top["paper_variant"] == "11"
    assert top["title"] == "Physics · May/June 2026 · Paper 11 · Q1"
    assert top["pdf_url"] == "/pdf/9702_s26_qp_11.pdf#page=4"
    assert top["has_figure"] is False


def test_search_payload_flags_figure_questions(client):
    body = client.get("/api/search", params={"q": "block rests rough slope equilibrium"}).json()
    top = body["results"][0]
    assert top["question_number"] == 3
    assert top["has_figure"] is True


@pytest.mark.parametrize("q", ["", "   ", "!!!", "()"])
def test_empty_and_punctuation_queries_are_ok(client, q):
    r = client.get("/api/search", params={"q": q})
    assert r.status_code == 200
    assert r.json() == {"query": q, "count": 0, "results": []}


def test_limit_is_floored_and_capped(client):
    assert len(client.get("/api/search", params={"q": "a", "limit": 0}).json()["results"]) <= 1
    # a match-everything-ish query with a huge limit must not error
    big = client.get("/api/search", params={"q": "ball OR quantity OR block", "limit": 999})
    assert big.status_code == 200
    assert big.json()["count"] <= 3


def test_stats_counts(client):
    s = client.get("/api/stats").json()
    assert s == {
        "papers": 1,
        "question_papers": 1,
        "questions": 3,
        "answers": 2,
        "subjects": ["Physics"],
    }


def test_pdf_served_for_recorded_paper(client):
    r = client.get(f"/pdf/{QP}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_pdf_404_for_valid_name_not_in_db(client):
    assert client.get("/pdf/9702_s26_qp_12.pdf").status_code == 404


@pytest.mark.parametrize("name", ["notapaper.pdf", "9702_s26_qp_11.pdf.bak", "papers.db"])
def test_pdf_404_for_garbage_name(client, name):
    assert client.get(f"/pdf/{name}").status_code == 404


@pytest.mark.parametrize(
    "name", ["../papers.db", "..%2Fpapers.db", "", "/etc/passwd", "9702_S26_QP_11"]
)
def test_resolve_pdf_rejects_bad_names(corpus, name):
    db_path, raw_dir = corpus
    assert resolve_pdf(name, raw_dir=raw_dir, db_path=db_path) is None


def test_pdfs_disabled(corpus):
    db_path, raw_dir = corpus
    client = TestClient(create_app(db_path=db_path, raw_dir=raw_dir, serve_pdfs=False))
    assert client.get(f"/pdf/{QP}").status_code == 404
    top = client.get("/api/search", params={"q": "ball thrown"}).json()["results"][0]
    assert top["pdf_url"] is None


def test_search_kind_filter(client):
    q = "ball quantity block rests slope"  # spans q1/q2 (mcq) and q3 (theory)
    all_nums = {
        r["question_number"] for r in client.get("/api/search", params={"q": q}).json()["results"]
    }
    assert all_nums == {1, 2, 3}

    mcq = client.get("/api/search", params={"q": q, "kind": "mcq"}).json()["results"]
    assert {r["question_number"] for r in mcq} == {1, 2}

    theory = client.get("/api/search", params={"q": q, "kind": "theory"}).json()["results"]
    assert {r["question_number"] for r in theory} == {3}


def test_structured_answer_passed_through(client):
    body = client.get("/api/search", params={"q": "block rests rough slope equilibrium"}).json()
    top = body["results"][0]
    assert top["question_number"] == 3
    assert top["marks"] == 9
    assert "resultant force is zero" in top["answer"]


def test_config_empty_in_local_mode(client):
    assert client.get("/api/config").json() == {}


def test_config_populated_in_cloud_mode(client, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://demo.supabase.co/")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_x")
    assert client.get("/api/config").json() == {
        "supabase_url": "https://demo.supabase.co",  # trailing slash stripped
        "supabase_key": "sb_publishable_x",
    }


def test_search_and_stats_are_501_in_cloud_mode(client, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://demo.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_x")
    assert client.get("/api/search", params={"q": "ball"}).status_code == 501
    assert client.get("/api/stats").status_code == 501


def test_health_ok_in_local_mode(client):
    assert client.get("/api/health").json() == {"ok": True}


# ------------------------------------------------------------------ topic browse


def test_api_topics_counts(client):
    body = client.get("/api/topics").json()
    by_code = {t["code"]: t for t in body["topics"]}
    assert len(body["topics"]) == 11
    assert by_code["s01"]["count"] == 1
    assert by_code["s03"]["count"] == 1
    assert by_code["s04"]["count"] == 1
    assert by_code["s07"]["count"] == 0
    assert body["total"] == 3
    assert body["unlabelled"] == 0


def test_api_topics_kind_filter(client):
    body = client.get("/api/topics", params={"kind": "theory"}).json()
    by_code = {t["code"]: t for t in body["topics"]}
    assert by_code["s03"]["count"] == 1  # q3 is theory
    assert by_code["s02"]["count"] == 0  # q1 is mcq
    assert body["total"] == 1


def test_api_browse_payload_and_total(client):
    body = client.get("/api/browse", params={"topics": "s03,s04"}).json()
    assert body["count"] == 1  # q3 carries both codes, returned once
    assert body["offset"] == 0
    top = body["results"][0]
    # went through result_payload
    assert top["question_number"] == 3
    assert top["title"] == "Physics · May/June 2026 · Paper 11 · Q3"
    assert top["pdf_url"] == "/pdf/9702_s26_qp_11.pdf#page=5"
    assert set(top["topic_codes"]) == {"s03", "s04"}


def test_api_browse_count_is_total_not_page_length(client):
    body = client.get("/api/browse", params={"topics": "s01,s02,s03,s04", "limit": 1}).json()
    assert body["count"] == 3
    assert len(body["results"]) == 1


def test_api_browse_unknown_codes_degrade_to_empty(client):
    body = client.get("/api/browse", params={"topics": "s99,nope"}).json()
    assert body["count"] == 0
    assert body["results"] == []


def test_topic_endpoints_501_in_cloud_mode(client, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://demo.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_x")
    assert client.get("/api/topics").status_code == 501
    assert client.get("/api/browse", params={"topics": "s01"}).status_code == 501
