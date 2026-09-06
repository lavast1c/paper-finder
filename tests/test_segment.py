from paper_finder.segment import (
    _split_stem_and_options,
    is_noise,
    looks_like_mcq,
    segment_mcq,
    segment_structured,
)


def _line(text, x0=72.0, page=3, in_body=True, y_frac=0.3):
    return {"text": text, "x0": x0, "page": page, "in_body": in_body, "y_frac": y_frac}


def _mcq_lines(n=3):
    """A minimal MCQ paper: cover line + n questions, each numbered in the margin."""
    lines = [_line("Paper 1 Multiple Choice", x0=100, page=1)]
    for q in range(1, n + 1):
        lines.append(_line(str(q), x0=49.6))
        lines.append(_line(f"Stem for question {q} about physics?"))
        for opt in ("A", "B", "C", "D"):
            lines.append(_line(opt))
            lines.append(_line(f"option {opt.lower()} {q}"))
    return lines


def _structured_lines():
    """A minimal structured paper: 2 questions, each numbered top-of-page + [Total]."""
    return [
        _line("Paper 2 AS Level Structured Questions", x0=100, page=1),
        _line("1", x0=49.6, page=4, y_frac=0.07),
        _line("(a) State what is meant by kinetic energy.", page=4),
        _line(" ......................................................... [1]", page=4),
        _line("(b) Calculate the speed of the ball.", page=4),
        _line("speed = ................ m s [2]", page=4),
        _line("[Total: 3]", x0=498.0, page=5, y_frac=0.9),
        _line("2", x0=49.6, page=6, y_frac=0.07),
        _line("A block slides down a rough slope.", page=6),
        _line("(a) Determine the friction force.", page=6),
        _line("[Total: 5]", x0=498.0, page=7, y_frac=0.8),
    ]


def test_looks_like_mcq():
    assert looks_like_mcq(_mcq_lines()) is True
    assert looks_like_mcq(_structured_lines()) is False


def test_segment_mcq_basic():
    questions = segment_mcq(_mcq_lines(n=3))
    assert [q.number for q in questions] == [1, 2, 3]
    assert questions[0].text.startswith("Stem for question 1 about physics?")
    assert "A. option a 1" in questions[0].text
    assert "D. option d 3" in questions[2].text
    assert all(q.is_mcq for q in questions)


def test_question_number_needs_left_margin():
    lines = _mcq_lines(n=2)
    lines.insert(3, _line("2", x0=200.0))  # stray "2" mid-question-1
    assert [q.number for q in segment_mcq(lines)] == [1, 2]


def test_number_out_of_sequence_is_ignored():
    lines = _mcq_lines(n=2)
    lines.insert(3, _line("7", x0=49.6))
    assert [q.number for q in segment_mcq(lines)] == [1, 2]


def test_segment_structured_basic():
    questions = segment_structured(_structured_lines())
    assert [q.number for q in questions] == [1, 2]
    assert questions[0].marks == 3
    assert questions[1].marks == 5
    assert not questions[0].is_mcq
    assert "kinetic energy" in questions[0].text
    assert "friction force" in questions[1].text
    # dotted answer lines and [N] mark brackets are stripped
    assert "......" not in questions[0].text
    assert "[1]" not in questions[0].text
    assert "[Total" not in questions[0].text


def test_structured_start_needs_top_of_page():
    lines = _structured_lines()
    # a mid-page "2" in the left margin (e.g. a graph axis label) inside question 1
    lines.insert(5, _line("2", x0=49.6, page=4, y_frac=0.55))
    assert [q.number for q in segment_structured(lines)] == [1, 2]


def test_split_stem_uses_last_valid_option_block():
    texts = ["A", "V", "stem text?", "A", "one", "B", "two", "C", "three", "D", "four"]
    stem, options = _split_stem_and_options(texts)
    assert "stem text?" in " ".join(stem)
    assert options["A"] == ["one"]
    assert options["D"] == ["four"]


def test_noise_matches_furniture_but_not_questions():
    assert is_noise("© Cambridge University Press & Assessment 2026")
    assert is_noise("9702/11/M/J/26")
    assert is_noise("Downloaded from PapaCambridge - https://papacambridge.com/")
    assert is_noise("9702/22 Question Paper June 2026")
    assert is_noise("DO NOT WRITE IN THIS MARGIN")
    assert is_noise("ĬÕĊ®Ġ´íÈõÏĪÅĊÞü·Ā×")  # barcode font
    assert is_noise(",\x01\x01\x01\t\x01\x05,")  # barcode control chars
    assert not is_noise("A ball is thrown vertically upwards.")
