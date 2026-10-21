"""Evaluation question sets.

A set lives in ml/eval/data/<name>/: `questions.jsonl` plus a `corpus/` folder with the
course files (PDF/DOCX/PPTX), or `<file>.<ext>.txt` sources that corpus.py renders.

Gold labels are (document filename, page) pairs, not chunk ids, so the same labels work
for every chunking configuration, and pages are what users see in citations.
"""

import json
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

DATA_DIR = Path(__file__).parent / "data"

QuestionType = Literal["single", "multi_hop", "unanswerable"]


class Question(BaseModel):
    id: str
    course: str
    type: QuestionType
    question: str = Field(min_length=3)
    # single: any listed page answers it; multi_hop: all listed pages are needed;
    # unanswerable: the notes don't cover it, so the system should say so.
    gold: list[tuple[str, int]] = []
    answer: str = ""  # reference answer for the correctness judge
    verified: bool = True  # False for LLM-generated questions awaiting human review

    @model_validator(mode="after")
    def _gold_matches_type(self) -> "Question":
        if self.type == "unanswerable" and self.gold:
            raise ValueError(f"{self.id}: unanswerable questions have no gold pages")
        if self.type == "single" and not self.gold:
            raise ValueError(f"{self.id}: needs at least one gold page")
        if self.type == "multi_hop" and len(set(self.gold)) < 2:
            raise ValueError(f"{self.id}: multi-hop questions need two or more gold pages")
        if self.type != "unanswerable" and not self.answer:
            raise ValueError(f"{self.id}: needs a reference answer")
        return self

    @property
    def gold_pages(self) -> set[tuple[str, int]]:
        return set(self.gold)


def set_dir(name: str) -> Path:
    return DATA_DIR / name


def load_questions(name: str, *, verified_only: bool = True) -> list[Question]:
    path = set_dir(name) / "questions.jsonl"
    questions = [
        Question.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    duplicates = [qid for qid, n in Counter(q.id for q in questions).items() if n > 1]
    if duplicates:
        raise ValueError(f"duplicate question ids: {duplicates}")
    return [q for q in questions if q.verified or not verified_only]


def save_questions(name: str, questions: list[Question]) -> None:
    path = set_dir(name) / "questions.jsonl"
    path.write_text(
        "".join(json.dumps(q.model_dump(), ensure_ascii=False) + "\n" for q in questions),
        encoding="utf-8",
    )


def describe(questions: list[Question]) -> dict[str, int]:
    counts = Counter(q.type for q in questions)
    return {"total": len(questions), **{t: counts.get(t, 0) for t in QuestionType.__args__}}
