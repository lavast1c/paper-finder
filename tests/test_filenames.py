import pytest

from paper_finder.filenames import parse_filename


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


def test_label():
    assert parse_filename("9702_s23_qp_12.pdf").label == "9702/s23/qp/12"
    assert parse_filename("9702_s23_gt.pdf").label == "9702/s23/gt"
