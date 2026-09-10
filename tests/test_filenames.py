import pytest

from paper_finder.filenames import build_filename, parse_filename


@pytest.mark.parametrize(
    "name, expected",
    [
        (
            "9702_s23_qp_12.pdf",
            dict(subject_code="9702", year=2023, session="s", paper_type="qp", paper=1, variant=2),
        ),
        (
            "9702_w21_ms_42.pdf",
            dict(subject_code="9702", year=2021, session="w", paper_type="ms", paper=4, variant=2),
        ),
        (
            "9709_m22_qp_12.pdf",
            dict(subject_code="9709", year=2022, session="m", paper_type="qp", paper=1, variant=2),
        ),
        (
            "9702_s02_qp_1.pdf",
            dict(
                subject_code="9702",
                year=2002,
                session="s",
                paper_type="qp",
                paper=1,
                variant=None,
            ),
        ),
        (
            "9702_s23_gt.pdf",
            dict(
                subject_code="9702",
                year=2023,
                session="s",
                paper_type="gt",
                paper=None,
                variant=None,
            ),
        ),
    ],
)
def test_parse_valid(name, expected):
    parsed = parse_filename(name)
    assert parsed is not None
    for attr, value in expected.items():
        assert getattr(parsed, attr) == value


@pytest.mark.parametrize(
    "name",
    ["random.pdf", "notes.txt", "9702-s23-qp-12.pdf", "9702_s23.pdf", "9702_x23_qp_12.pdf", ""],
)
def test_parse_invalid(name):
    assert parse_filename(name) is None


def test_case_and_whitespace_normalised():
    parsed = parse_filename("  9702_S23_QP_12.PDF  ")
    assert parsed is not None
    assert parsed.filename == "9702_s23_qp_12.pdf"


def test_subject_name_resolved():
    assert parse_filename("9702_s23_qp_12.pdf").subject_name == "Physics"


def test_unknown_subject_code_is_none():
    assert parse_filename("1234_s23_qp_12.pdf").subject_name is None


def test_9231_paper_splits_into_two_subjects():
    # Further Mathematics 9231: Paper 1 and Paper 4 are effectively separate
    # subjects with their own syllabus content.
    assert parse_filename("9231_s24_qp_11.pdf").subject_name == "Further Pure Mathematics"
    assert parse_filename("9231_w23_ms_43.pdf").subject_name == "Further Probability & Statistics"
    # a paper without an override falls back to the plain subject name
    assert parse_filename("9231_s24_qp_21.pdf").subject_name == "Further Mathematics"


def test_label():
    assert parse_filename("9702_s23_qp_12.pdf").label == "9702/s23/qp/12"
    assert parse_filename("9702_s23_gt.pdf").label == "9702/s23/gt"


@pytest.mark.parametrize(
    "args, expected",
    [
        (("9702", "s", 2023, "qp", 1, 2), "9702_s23_qp_12.pdf"),
        (("9702", "w", 2021, "ms", 4, 2), "9702_w21_ms_42.pdf"),
        (("9702", "s", 2002, "qp", 1), "9702_s02_qp_1.pdf"),
        (("9702", "s", 2023, "gt"), "9702_s23_gt.pdf"),
    ],
)
def test_build_filename(args, expected):
    assert build_filename(*args) == expected


@pytest.mark.parametrize(
    "name",
    [
        "9702_s23_qp_12.pdf",
        "9702_w21_ms_42.pdf",
        "9709_m22_qp_12.pdf",
        "9702_s02_qp_1.pdf",
        "9702_s23_gt.pdf",
    ],
)
def test_build_filename_round_trips_with_parse(name):
    p = parse_filename(name)
    rebuilt = build_filename(p.subject_code, p.session, p.year, p.paper_type, p.paper, p.variant)
    assert rebuilt == name


@pytest.mark.parametrize(
    "args",
    [
        ("9702", "s", 2023, "qp", None, 2),  # variant without paper
        ("9702", "x", 2023, "qp", 1),  # bad session
        ("97020", "s", 2023, "qp", 1),  # 5-digit code
        ("9702", "s", 1850, "qp", 1),  # year out of range
        ("9702", "s", 2023, "QP", 1),  # non-lowercase type
    ],
)
def test_build_filename_rejects_bad_input(args):
    with pytest.raises(ValueError):
        build_filename(*args)
