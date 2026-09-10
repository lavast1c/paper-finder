from paper_finder.marks import (
    _answer_crop_rects,
    parse_mcq_answers,
    parse_structured_answers,
)

_MS_H = 595.0


def _lines(texts):
    return [
        {
            "text": t,
            "x0": 50.0,
            "page": 2,
            "in_body": True,
            "y_frac": 0.3,
            "y0": 0.3 * _MS_H,
            "y1": 0.3 * _MS_H + 10.0,
            "height": _MS_H,
        }
        for t in texts
    ]


def _ln(text, page=2, y0=100.0, height=_MS_H):
    return {
        "text": text,
        "x0": 80.0,
        "page": page,
        "in_body": True,
        "y_frac": y0 / height,
        "y0": y0,
        "y1": y0 + 10.0,
        "height": height,
    }


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


def _row(text, x0, page=6, y0=100.0):
    return {
        "text": text,
        "x0": x0,
        "page": page,
        "in_body": True,
        "y_frac": y0 / _MS_H,
        "y0": y0,
        "y1": y0 + 10.0,
        "height": _MS_H,
    }


def test_structured_answers_read_bare_number_labels_in_the_table():
    # CIE 9231: a question with no lettered parts is labelled with a bare number
    # in the Question column. It must still be picked up once the table starts.
    lines = [
        _row("Cambridge International – Mathematics-Specific Marking Principles", 60, page=3),
        _row("1", 68, page=3, y0=80.0),  # a marking principle, NOT question 1
        _row("Unless a particular method has been specified, allow full marks.", 90, page=3, y0=95),
        _row("Question", 69, page=6, y0=55.0),
        _row("1", 87, page=6, y0=80.0),
        _row("H0: the die is fair", 122, page=6, y0=95.0),
        _row("Question", 69, page=7, y0=55.0),
        _row("2", 87, page=7, y0=80.0),
        _row("mean = 4.7", 122, page=7, y0=95.0),
        _row("3(a)", 81, page=8, y0=80.0),
        _row("chi-squared = 2.1", 122, page=8, y0=95.0),
    ]
    answers = parse_structured_answers(lines)
    assert [a.question_number for a in answers] == [1, 2, 3]
    assert "H0: the die is fair" in answers[0].answer_text
    assert "mean = 4.7" in answers[1].answer_text
    # the page-3 marking principle did not become question 1's text
    assert "Unless a particular method" not in answers[0].answer_text


def test_structured_answers_ignore_stray_small_integers_in_the_body():
    lines = [
        _row("Question", 69, page=6, y0=55.0),
        _row("1(a)", 55, page=6, y0=80.0),
        _row("2", 106, page=6, y0=95.0),  # a coefficient, near-ish the margin
        _row("k + 12c = 2", 122, page=6, y0=110.0),
        _row("1(b)", 54, page=6, y0=200.0),
        _row("IQR = 4", 122, page=6, y0=215.0),
        _row("2(a)", 55, page=7, y0=80.0),
        _row("next question", 122, page=7, y0=95.0),
    ]
    answers = parse_structured_answers(lines)
    assert [a.question_number for a in answers] == [1, 2]
    assert "k + 12c = 2" in answers[0].answer_text
    assert "IQR = 4" in answers[0].answer_text


def test_answer_crop_rects_single_page_stops_at_next_question():
    block = [_ln("1(a)", y0=100.0), _ln("mark point", y0=130.0)]
    next_start = _ln("2(a)", y0=300.0)
    rects = _answer_crop_rects(block, next_start)
    assert len(rects) == 1
    page, x0, y0, x1, y1 = rects[0]
    assert page == 2
    assert (x0, x1) == (55.0, 795.0)
    assert y0 == round(100.0 - 4.0, 1)
    assert y1 == round(300.0 - 4.0, 1)


def test_answer_crop_rects_last_question_runs_to_body_bottom():
    block = [_ln("5(a)", y0=400.0), _ln("mark point", y0=430.0)]
    rects = _answer_crop_rects(block, None)
    assert len(rects) == 1
    assert rects[0][4] == round(0.915 * _MS_H, 1)


def test_answer_crop_rects_spans_pages_and_uses_block_extremes():
    block = [
        _ln("3(b)", page=4, y0=520.0),  # not the first line in reading order
        _ln("3(a)", page=4, y0=90.0),
        _ln("continued", page=6, y0=200.0),  # nothing on page 5
    ]
    rects = _answer_crop_rects(block, None)
    assert [r[0] for r in rects] == [4, 5, 6]
    assert rects[0][2] == round(90.0 - 4.0, 1)  # top = min y0 on the first page


def test_answer_crop_rects_drops_a_sliver():
    block = [_ln("6(a)", y0=200.0)]
    next_start = _ln("7(a)", y0=210.0)  # only 10 pt tall -> below _MS_CROP_MIN_HEIGHT
    assert _answer_crop_rects(block, next_start) == ()
