from paper_finder.marks import parse_mcq_answers, parse_structured_answers


def _lines(texts):
    return [{"text": t, "x0": 50.0, "page": 2, "in_body": True, "y_frac": 0.3} for t in texts]


def test_parse_mcq_answers_reads_triples():
    lines = _lines(["Question", "Answer", "Marks", "1", "D", "1", "2", "B", "1", "3", "C", "1"])
    answers = parse_mcq_answers(lines)
    assert [(a.question_number, a.answer_text, a.marks) for a in answers] == [
        (1, "D", 1),
        (2, "B", 1),
        (3, "C", 1),
    ]


def test_parse_stops_at_sequence_break():
    lines = _lines(["1", "D", "1", "3", "C", "1"])  # missing question 2
    answers = parse_mcq_answers(lines)
    assert [a.question_number for a in answers] == [1]


def test_parse_ignores_page_furniture_between_rows():
    lines = _lines(["1", "D", "1", "9702/11", "Page 3 of 3", "2", "A", "1"])
    answers = parse_mcq_answers(lines)
    assert [a.question_number for a in answers] == [1, 2]


def test_parse_structured_answers_groups_by_question():
    lines = _lines(
        [
            "General marking principles",  # pre-table noise, before any label
            "1(a)",
            "area under the graph",
            "B1",
            "1(b)(i)",
            "distance = 390 m",
            "A1",
            "2(a)",
            "resultant force is zero",
            "B1",
        ]
    )
    answers = parse_structured_answers(lines)
    assert [a.question_number for a in answers] == [1, 2]
    assert "area under the graph" in answers[0].answer_text
    assert "distance = 390 m" in answers[0].answer_text
    assert answers[1].answer_text.startswith("2(a)")
