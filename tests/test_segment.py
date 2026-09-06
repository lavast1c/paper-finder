from paper_finder.segment import (
    _is_noise,
    _split_stem_and_options,
    looks_like_mcq,
    segment_mcq,
)


def _line(text, x0=70.0, page=3, in_body=True):
    return {"text": text, "x0": x0, "page": page, "in_body": in_body}


def _mcq_lines(n=3):
    """A minimal MCQ paper: cover line + n questions, each numbered in the margin."""
    lines = [_line("Paper 1 Multiple Choice", x0=100, page=1)]
    for q in range(1, n + 1):
        lines.append(_line(str(q), x0=49.6))  # question number in the margin
        lines.append(_line(f"Stem for question {q} about physics?"))
        for opt in ("A", "B", "C", "D"):
            lines.append(_line(opt))
            lines.append(_line(f"option {opt.lower()} {q}"))
    return lines


def test_looks_like_mcq():
    assert looks_like_mcq(_mcq_lines()) is True
    assert looks_like_mcq([_line("Section A: Answer all questions", page=1)]) is False


def test_segment_mcq_basic():
    questions = segment_mcq(_mcq_lines(n=3))
    assert [q.number for q in questions] == [1, 2, 3]
    assert questions[0].text.startswith("Stem for question 1 about physics?")
    assert "A. option a 1" in questions[0].text
    assert "D. option d 3" in questions[2].text


def test_question_number_needs_left_margin():
    # A "2" that is not in the margin (e.g. a diagram label) must not start Q2.
    lines = _mcq_lines(n=2)
    lines.insert(3, _line("2", x0=200.0))  # stray "2" mid-question-1
    questions = segment_mcq(lines)
    assert [q.number for q in questions] == [1, 2]


def test_number_out_of_sequence_is_ignored():
    lines = _mcq_lines(n=2)
    lines.insert(3, _line("7", x0=49.6))  # wrong number in the margin
    questions = segment_mcq(lines)
    assert [q.number for q in questions] == [1, 2]


def test_lines_outside_body_are_dropped():
    lines = _mcq_lines(n=2)
    lines.append(_line("10", x0=294.0, in_body=False))  # centred page number
    lines.append(_line("9702/11 Question Paper June 2026", in_body=False))
    questions = segment_mcq(lines)
    assert "9702" not in questions[-1].text
    assert not questions[-1].text.rstrip().endswith("10")


def test_split_stem_uses_last_valid_option_block():
    texts = ["A", "V", "stem text?", "A", "one", "B", "two", "C", "three", "D", "four"]
    stem, options = _split_stem_and_options(texts)
    assert "stem text?" in " ".join(stem)
    assert options["A"] == ["one"]
    assert options["D"] == ["four"]


def test_noise_matches_furniture_but_not_questions():
    assert _is_noise("© Cambridge University Press & Assessment 2026")
    assert _is_noise("9702/11/M/J/26")
    assert _is_noise("Downloaded from PapaCambridge - https://papacambridge.com/")
    assert _is_noise("9702/11 Question Paper June 2026")
    assert not _is_noise("A ball is thrown vertically upwards.")
