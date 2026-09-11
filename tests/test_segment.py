from paper_finder.segment import (
    _crop_rects,
    _split_stem_and_options,
    content_lines,
    is_noise,
    looks_like_mcq,
    mentions_figure,
    segment_mcq,
    segment_structured,
)


def _line(text, x0=72.0, page=3, in_body=True, y_frac=0.3, height=842.0):
    y0 = y_frac * height
    return {
        "text": text,
        "x0": x0,
        "page": page,
        "in_body": in_body,
        "y_frac": y_frac,
        "y0": y0,
        "y1": y0 + 12.0,
        "height": height,
    }


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


def test_structured_start_ignores_a_margin_number_with_no_prose_after_it():
    lines = _structured_lines()
    # a stray "2" in the left margin (e.g. a graph axis label) inside question 1,
    # with only an answer line + [Total] before the real question 2 -- no prose
    # follows it and the real "2" downstream is a rival margin number
    lines.insert(5, _line("2", x0=49.6, page=4, y_frac=0.75))
    assert [q.number for q in segment_structured(lines)] == [1, 2]


def test_structured_start_survives_a_figure_between_number_and_prose():
    # CIE 9231 often puts a graph or a displayed formula right after the question
    # number, so the first prose/part line is several lines down.
    lines = [
        _line("1", x0=49.6, page=2, y_frac=0.07),
        _line("The continuous random variable X has probability density function.", page=2),
        _line("[Total: 8]", x0=498.0, page=3, y_frac=0.9),
        _line("2", x0=49.6, page=4, y_frac=0.07),
        _line("f(x)", x0=116.0, page=4, y_frac=0.09),  # a graph axis label
        _line("0", x0=131.0, page=4, y_frac=0.21),
        _line("6", x0=444.0, page=4, y_frac=0.21),
        _line("As shown in the diagram, the random variable X has pdf f given by.", page=4),
        _line("(a) Find the value of k.", page=4),
        _line("[Total: 6]", x0=498.0, page=5, y_frac=0.8),
    ]
    assert [q.number for q in segment_structured(lines)] == [1, 2]


def test_structured_start_survives_a_full_page_graph_before_any_prose():
    # 9709 Pure Maths opens many questions with a full-width graph whose axis
    # labels ("x", "y", "4pi", "-1"...) run past the body lookahead before the
    # first sentence. A margin number at the very top of a page still starts one.
    lines = [
        _line("1", x0=49.3, page=4, y_frac=0.078),
        _line("The sum of the first 20 terms of an arithmetic progression is 1410.", page=4),
        _line("[Total: 5]", x0=498.0, page=4, y_frac=0.9),
        _line("2", x0=49.3, page=5, y_frac=0.078),
        _line("x", x0=530.9, page=5, y_frac=0.212),
        _line("y", x0=142.0, page=5, y_frac=0.089),
        _line("−1", x0=82.3, page=5, y_frac=0.220),
        _line("4π", x0=89.8, page=5, y_frac=0.221),
        _line("2π", x0=242.3, page=5, y_frac=0.221),
        _line("π", x0=346.2, page=5, y_frac=0.220),
        _line("−6", x0=120.0, page=5, y_frac=0.30),
        _line("−4", x0=120.0, page=5, y_frac=0.35),
        _line("The diagram shows part of the graph of y = f(x).", page=5, y_frac=0.55),
        _line("[Total: 6]", x0=498.0, page=5, y_frac=0.9),
        _line("3", x0=49.3, page=6, y_frac=0.078),
        _line("The fifth, sixth and seventh terms of a geometric progression.", page=6),
        _line("[Total: 4]", x0=498.0, page=6, y_frac=0.9),
    ]
    assert [q.number for q in segment_structured(lines)] == [1, 2, 3]


def test_structured_start_deep_into_a_shared_page_with_prose():
    # 9709 Stats packs short questions two to a page -- question 2 can begin past
    # the half-way mark of the page it shares with question 1's answer space.
    lines = [
        _line("1", x0=49.3, page=2, y_frac=0.078),
        _line("The 40 members of a club include Ranuf and Saed.", page=2),
        _line("[Total: 4]", x0=498.0, page=2, y_frac=0.45),
        _line("2", x0=49.3, page=2, y_frac=0.512),
        _line("An ordinary fair die is thrown repeatedly until a 1 or a 6 is obtained.", page=2),
        _line("(a) Find the probability that it takes at least 3 throws.", page=2),
        _line("[Total: 6]", x0=498.0, page=3, y_frac=0.9),
        _line("3", x0=49.3, page=4, y_frac=0.078),
        _line("The weights of apples are normally distributed.", page=4),
        _line("[Total: 5]", x0=498.0, page=4, y_frac=0.9),
    ]
    assert [q.number for q in segment_structured(lines)] == [1, 2, 3]


def test_structured_start_number_shares_its_line_with_the_opening_words():
    # 2024+ 9709 papers sometimes set a two-digit question number on the same
    # line as the first words ("10 The equation of a circle is ..."). The bare
    # question 3 that follows opens with a graph, so it is only found if 2 was.
    lines = [
        _line("1", x0=49.6, page=2, y_frac=0.07),
        _line("A first question about vectors.", page=2),
        _line("[Total: 5]", x0=498.0, page=3, y_frac=0.9),
        _line("2 The equation of a circle is x^2 + y^2 = 4.", x0=49.6, page=4, y_frac=0.07),
        _line("Find the centre and radius.", page=4),
        _line("[Total: 3]", x0=498.0, page=5, y_frac=0.9),
        _line("3", x0=49.6, page=6, y_frac=0.06),
        _line("y", x0=296.9, page=6, y_frac=0.10),  # opens with a graph
        _line("The diagram shows the curve y = f(x).", page=6, y_frac=0.5),
    ]
    qs = segment_structured(lines)
    assert [q.number for q in qs] == [1, 2, 3]
    assert "equation of a circle" in qs[1].text


def test_structured_start_rejected_when_only_a_bare_number_follows():
    # a stray margin number followed by more numbers (a table column) is not a start
    lines = [
        _line("1", x0=49.6, page=2, y_frac=0.07),
        _line("A first question about vectors and matrices.", page=2),
        _line("[Total: 5]", x0=498.0, page=3, y_frac=0.9),
        _line("2", x0=49.6, page=4, y_frac=0.07),
        _line("3", x0=49.6, page=4, y_frac=0.10),
        _line("4", x0=49.6, page=4, y_frac=0.13),
    ]
    assert [q.number for q in segment_structured(lines)] == [1]


def test_split_stem_uses_last_valid_option_block():
    texts = ["A", "V", "stem text?", "A", "one", "B", "two", "C", "three", "D", "four"]
    stem, options = _split_stem_and_options(texts)
    assert "stem text?" in " ".join(stem)
    assert options["A"] == ["one"]
    assert options["D"] == ["four"]


def test_mentions_figure():
    assert mentions_figure("Fig. 1.1 shows the arrangement of the apparatus.")
    assert mentions_figure("The diagram shows a metal block.")
    assert mentions_figure("The graph shows the variation with time of the velocity.")
    assert mentions_figure("Complete Table 7.1 to show the charges on each quark.")
    assert not mentions_figure("A ball is thrown horizontally with a speed of 10 m/s.")
    assert not mentions_figure("State what is meant by a fundamental particle.")


def test_segment_sets_has_figure():
    mcq = segment_mcq(_mcq_lines(n=2))
    assert all(q.has_figure is False for q in mcq)  # "Stem for question N" — no figure

    lines = _structured_lines()
    lines[8] = _line("Fig. 2.1 shows a block on a rough slope.", page=6)
    q1, q2 = segment_structured(lines)
    assert q1.has_figure is False
    assert q2.has_figure is True


def test_crop_rects_single_page_stops_at_next_question():
    q1_block = [
        _line("1", x0=49.6, page=3, y_frac=0.10),
        _line("Stem of question 1.", page=3, y_frac=0.14),
    ]
    next_start = _line("2", x0=49.6, page=3, y_frac=0.45)
    rects = _crop_rects(q1_block, next_start)
    assert len(rects) == 1
    page, x0, y0, x1, y1 = rects[0]
    assert page == 3
    assert (x0, x1) == (40.0, 555.0)
    assert y0 == round(0.10 * 842.0 - 4.0, 1)  # first line, minus headroom
    assert y1 == round(0.45 * 842.0 - 4.0, 1)  # next question's first line


def test_crop_rects_last_question_runs_to_body_bottom():
    block = [_line("40", x0=49.6, page=15, y_frac=0.10), _line("Last stem.", page=15, y_frac=0.14)]
    (rect,) = _crop_rects(block, None)
    assert rect[4] == round(0.93 * 842.0, 1)


def test_crop_rects_spans_a_blank_middle_page():
    # question 2 covers pages 4-6; page 5 is a full-page diagram with no text line
    block = [
        _line("2", x0=49.6, page=4, y_frac=0.07),
        _line("(a) Look at Fig 2.1.", page=4, y_frac=0.20),
        _line("(b) Now calculate.", page=6, y_frac=0.15),
    ]
    next_start = _line("3", x0=49.6, page=6, y_frac=0.60)
    rects = _crop_rects(block, next_start)
    assert [r[0] for r in rects] == [4, 5, 6]  # the blank page is not dropped
    assert rects[1][2] == round(0.055 * 842.0, 1)  # page 5 top = body band top
    assert rects[1][4] == round(0.93 * 842.0, 1)  # page 5 bottom = body band bottom
    assert rects[2][4] == round(0.60 * 842.0 - 4.0, 1)  # page 6 bottom = q3 start


def test_crop_rects_uses_block_extremes_not_first_last_line():
    # PDF block order is not y-order: a footer-ish line comes first in the list
    block = [
        _line("noise near bottom", page=3, y_frac=0.80),
        _line("1", x0=49.6, page=3, y_frac=0.10),
        _line("real stem", page=3, y_frac=0.14),
    ]
    (rect,) = _crop_rects(block, None)
    assert rect[2] == round(0.10 * 842.0 - 4.0, 1)  # top = min y0 over the block


def test_segment_mcq_records_crop_rects():
    lines = [_line("Paper 1 Multiple Choice", x0=100, page=1, y_frac=0.05)]
    for q in range(1, 3):
        base = 0.1 + 0.4 * (q - 1)
        lines.append(_line(str(q), x0=49.6, page=3, y_frac=base))
        lines.append(_line(f"Stem for question {q} about physics?", page=3, y_frac=base + 0.03))
        for opt in ("A", "B", "C", "D"):
            lines.append(_line(opt, page=3, y_frac=base + 0.06))
            lines.append(_line(f"option {opt.lower()} {q}", page=3, y_frac=base + 0.08))
    questions = segment_mcq(lines)
    assert [q.number for q in questions] == [1, 2]
    assert all(len(q.crop_rects) == 1 for q in questions)
    assert all(rect[0] == 3 for q in questions for rect in q.crop_rects)
    # q1's crop ends where q2 begins
    assert questions[0].crop_rects[0][4] == round(0.5 * 842.0 - 4.0, 1)


def test_content_lines_drops_trailing_data_sheet():
    # CIE Chemistry appends a constants data sheet + periodic table after the
    # last question, inside the same qp PDF. A front-cover sentence that starts
    # the same way must NOT trip the cutoff -- only the standalone heading does.
    lines = [
        _line(
            "Important values, constants and standards are printed in the question paper.",
            page=1,
            y_frac=0.4,
        ),
        _line("40 What is the identity of X?", x0=49.6, page=15, y_frac=0.1),
        _line("A. one", page=15, y_frac=0.2),
        _line("Important values, constants and standards", page=19, y_frac=0.1),
        _line("molar gas constant", page=19, y_frac=0.2),
        _line("The Periodic Table of Elements", page=20, y_frac=0.05),
        _line("H hydrogen 1.0", page=20, y_frac=0.1),
    ]
    kept = [line["text"] for line in content_lines(lines)]
    assert kept == [
        "Important values, constants and standards are printed in the question paper.",
        "40 What is the identity of X?",
        "A. one",
    ]


def test_segment_mcq_stops_at_trailing_data_sheet():
    lines = [_line("Paper 1 Multiple Choice", x0=100, page=1)]
    lines.append(_line("1", x0=49.6, page=2))
    lines.append(_line("Stem for question 1 about chemistry?", page=2))
    for opt in ("A", "B", "C", "D"):
        lines.append(_line(opt, page=2))
        lines.append(_line(f"option {opt.lower()} 1", page=2))
    lines.append(_line("Important values, constants and standards", page=3))
    lines.append(_line("molar gas constant", page=3))
    lines.append(_line("The Periodic Table of Elements", page=4))
    lines.append(_line("H hydrogen 1.0", page=4))

    questions = segment_mcq(lines)
    assert len(questions) == 1
    assert "molar gas constant" not in questions[0].text
    assert questions[0].crop_rects[-1][0] == 2  # crop stops on the question's own page


def test_noise_matches_furniture_but_not_questions():
    assert is_noise("© Cambridge University Press & Assessment 2026")
    assert is_noise("9702/11/M/J/26")
    assert is_noise("Downloaded from PapaCambridge - https://papacambridge.com/")
    assert is_noise("9702/22 Question Paper June 2026")
    assert is_noise("DO NOT WRITE IN THIS MARGIN")
    assert is_noise("ĬÕĊ®Ġ´íÈõÏĪÅĊÞü·Ā×")  # barcode font
    assert is_noise(",\x01\x01\x01\t\x01\x05,")  # barcode control chars
    assert not is_noise("A ball is thrown vertically upwards.")
