"""Draft questions from a course's own chunks with the LLM, for a human to review.

Output goes to `questions.generated.jsonl` with `verified: false`. Review each line (is the
question clear, is the gold page right, is an "unanswerable" question really not covered?),
set `verified: true`, and move it into `questions.jsonl`. Unverified questions are never
scored.
"""

import json
import random
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.gateway import LLMGateway
from app.llm.providers import LLMRequest
from app.models import Chunk, Document

from .answer_eval import call
from .dataset import Question, set_dir
from .index import CourseIndex

GENERATOR_SYSTEM = """You write exam-revision questions for a student, based only on \
excerpts of their own course notes. Reply with one JSON object and nothing else."""

SINGLE = """Write one question that the excerpt below answers completely, phrased the way a \
student revising for an exam would ask it (don't copy sentences from the excerpt), and a \
short reference answer taken from the excerpt.
{{"question": "...", "answer": "..."}}

<excerpt>{text}</excerpt>"""

MULTI_HOP = """Write one question that needs BOTH excerpts to answer fully (neither alone is \
enough), and a short reference answer using both.
{{"question": "...", "answer": "..."}}

<excerpt id="A">{a}</excerpt>
<excerpt id="B">{b}</excerpt>"""

UNANSWERABLE = """These are the section headings of a student's notes for one course:
{headings}

Write {n} questions a student of this subject might plausibly ask that these notes do NOT \
cover: related topics, not trick questions.
{{"questions": ["...", "..."]}}"""


def _json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object in generator reply")
    return json.loads(match.group())


def generate(
    session: Session,
    gateway: LLMGateway,
    course: str,
    index: CourseIndex,
    *,
    single: int,
    multi_hop: int,
    unanswerable: int,
    seed: int = 7,
) -> list[Question]:
    rng = random.Random(seed)  # noqa: S311  # reproducible sampling, not security
    rows = session.execute(
        select(Chunk.text, Chunk.heading, Chunk.page, Document.filename)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.collection_id == index.collection_id, Chunk.token_count > 40)
    ).all()
    one_per_page = list({(r.filename, r.page): r for r in rows}.values())
    rng.shuffle(one_per_page)
    out: list[Question] = []

    def add(kind, question, answer, gold):
        out.append(
            Question(
                id=f"{course}-gen-{len(out) + 1:03d}",
                course=course,
                type=kind,
                question=question,
                answer=answer,
                gold=gold,
                verified=False,
            )
        )

    for r in one_per_page[:single]:
        reply = _json(
            call(gateway, LLMRequest(GENERATOR_SYSTEM, SINGLE.format(text=r.text), 2000)).text
        )
        add("single", reply["question"], reply["answer"], [(r.filename, r.page)])

    pairs = [
        (a, b)
        for a in one_per_page
        for b in one_per_page
        if (a.filename, a.page) < (b.filename, b.page)
    ]
    for a, b in rng.sample(pairs, min(multi_hop, len(pairs))):
        reply = _json(
            call(
                gateway, LLMRequest(GENERATOR_SYSTEM, MULTI_HOP.format(a=a.text, b=b.text), 2000)
            ).text
        )
        add(
            "multi_hop",
            reply["question"],
            reply["answer"],
            [(a.filename, a.page), (b.filename, b.page)],
        )

    if unanswerable:
        headings = "\n".join(sorted({f"- {r.heading}" for r in rows if r.heading}))
        prompt = UNANSWERABLE.format(headings=headings, n=unanswerable)
        for question in _json(call(gateway, LLMRequest(GENERATOR_SYSTEM, prompt, 2000)).text)[
            "questions"
        ]:
            add("unanswerable", question, "", [])
    return out


def save_generated(set_name: str, questions: list[Question]) -> str:
    path = set_dir(set_name) / "questions.generated.jsonl"
    with path.open("a", encoding="utf-8") as f:
        for q in questions:
            f.write(json.dumps(q.model_dump(), ensure_ascii=False) + "\n")
    return str(path)
