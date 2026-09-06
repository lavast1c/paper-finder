"""Measure search quality against a hand-written validation set.

``eval/validation.tsv`` holds ``phrase <TAB> filename <TAB> question_number``
rows. For each, we run the search and check where the expected question lands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from paper_finder import config
from paper_finder.search import search

DEFAULT_VALIDATION = config.PROJECT_ROOT / "eval" / "validation.tsv"


@dataclass(frozen=True)
class Case:
    phrase: str
    filename: str
    question_number: int


@dataclass
class EvalResult:
    total: int = 0
    top1: int = 0
    top5: int = 0
    # cases that were not the #1 hit; rank is the 1-based position, or -1 if the
    # expected question was outside the top 5
    misses: list[tuple[Case, int]] = field(default_factory=list)

    @property
    def top1_accuracy(self) -> float:
        return self.top1 / self.total if self.total else 0.0

    @property
    def top5_accuracy(self) -> float:
        return self.top5 / self.total if self.total else 0.0


def load_validation(path: Path = DEFAULT_VALIDATION) -> list[Case]:
    cases: list[Case] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        phrase, filename, number = line.split("\t")
        cases.append(Case(phrase, filename, int(number)))
    return cases


def _rank_of(hits, filename: str, number: int) -> int:
    for rank, hit in enumerate(hits, start=1):
        if hit.filename == filename and hit.question_number == number:
            return rank
    return -1


def evaluate(cases: list[Case], db_path: Path | None = None) -> EvalResult:
    result = EvalResult(total=len(cases))
    for case in cases:
        hits = search(case.phrase, limit=5, db_path=db_path)
        rank = _rank_of(hits, case.filename, case.question_number)
        if rank == 1:
            result.top1 += 1
        if rank != -1:
            result.top5 += 1
        if rank != 1:
            result.misses.append((case, rank))
    return result
