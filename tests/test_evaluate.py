from paper_finder.evaluate import DEFAULT_VALIDATION, Case, evaluate, load_validation


def test_default_validation_file_parses():
    cases = load_validation()
    assert len(cases) >= 15
    assert all(c.filename.endswith(".pdf") and c.question_number > 0 for c in cases)


def test_load_validation_skips_comments_and_blanks(tmp_path):
    path = tmp_path / "v.tsv"
    path.write_text("# a comment\n\nphrase one\t9702_s26_qp_11.pdf\t7\n", encoding="utf-8")
    cases = load_validation(path)
    assert cases == [Case("phrase one", "9702_s26_qp_11.pdf", 7)]


class _Hit:
    def __init__(self, filename, question_number):
        self.filename = filename
        self.question_number = question_number


def test_evaluate_counts_top1_and_top5(monkeypatch):
    import paper_finder.evaluate as ev

    responses = {
        "hit at 1": [_Hit("f.pdf", 1)],
        "hit at 3": [_Hit("x", 9), _Hit("y", 9), _Hit("f.pdf", 2)],
        "miss": [_Hit("z", 9)],
    }
    monkeypatch.setattr(ev, "search", lambda phrase, limit=5, db_path=None: responses[phrase])

    cases = [
        Case("hit at 1", "f.pdf", 1),
        Case("hit at 3", "f.pdf", 2),
        Case("miss", "f.pdf", 3),
    ]
    result = evaluate(cases)
    assert result.top1 == 1
    assert result.top5 == 2
    assert {rank for _, rank in result.misses} == {3, -1}


def test_default_validation_path_exists():
    assert DEFAULT_VALIDATION.exists()
