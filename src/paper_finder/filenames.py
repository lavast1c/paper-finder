"""Parse CIE past-paper filenames into structured metadata.

CIE names every past-paper PDF as::

    {code}_{session}{yy}_{type}_{paper}{variant}.pdf

    code     4 digits            e.g. 9702 (Physics)
    session  s | w | m           May/June | Oct/Nov | Feb/March
    yy       2-digit year        e.g. 23  ->  2023
    type     2 letters           qp (question paper), ms (mark scheme), in, gt, er, ...
    paper    1 digit             optional (absent on grade-threshold files)
    variant  1 digit             optional (older papers have no variant)

Examples::

    9702_s23_qp_12.pdf   ->  Physics, May/June 2023, question paper, paper 1 variant 2
    9702_w21_ms_42.pdf   ->  Physics, Oct/Nov 2021, mark scheme,     paper 4 variant 2
    9702_s02_qp_1.pdf    ->  Physics, May/June 2002, question paper,  paper 1 (no variant)
    9702_s23_gt.pdf      ->  Physics, May/June 2023, grade thresholds
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from paper_finder.config import SESSIONS, SUBJECTS

_PATTERN = re.compile(
    r"""
    ^(?P<code>\d{4})
    _(?P<session>[swm])(?P<yy>\d{2})
    _(?P<type>[a-z]{2})
    (?:_(?P<paper>\d)(?P<variant>\d)?)?
    $
    """,
    re.VERBOSE,
)


@dataclass(frozen=True)
class PaperName:
    """Structured form of a CIE past-paper filename."""

    filename: str  # normalised, always lowercase with a .pdf suffix
    subject_code: str
    subject_name: str | None  # None if the code is not in config.SUBJECTS yet
    year: int
    session: str  # 's' | 'w' | 'm'
    session_name: str
    paper_type: str  # 'qp' | 'ms' | 'in' | 'gt' | 'er' | ...
    paper: int | None
    variant: int | None

    @property
    def label(self) -> str:
        """Compact identifier, e.g. ``9702/s23/qp/12``."""
        parts = [self.subject_code, f"{self.session}{self.year % 100:02d}", self.paper_type]
        if self.paper is not None:
            parts.append(f"{self.paper}{self.variant if self.variant is not None else ''}")
        return "/".join(parts)


def _yy_to_year(yy: int) -> int:
    # CIE papers only go back to the 1990s, so a simple pivot is safe.
    return 2000 + yy if yy < 80 else 1900 + yy


def parse_filename(name: str) -> PaperName | None:
    """Return a :class:`PaperName`, or ``None`` if ``name`` is not a CIE paper."""
    stem = name.strip()
    if stem.lower().endswith(".pdf"):
        stem = stem[:-4]
    stem = stem.lower()

    match = _PATTERN.match(stem)
    if match is None:
        return None

    code = match.group("code")
    paper = match.group("paper")
    variant = match.group("variant")
    session = match.group("session")

    return PaperName(
        filename=f"{stem}.pdf",
        subject_code=code,
        subject_name=SUBJECTS.get(code),
        year=_yy_to_year(int(match.group("yy"))),
        session=session,
        session_name=SESSIONS[session],
        paper_type=match.group("type"),
        paper=int(paper) if paper is not None else None,
        variant=int(variant) if variant is not None else None,
    )
