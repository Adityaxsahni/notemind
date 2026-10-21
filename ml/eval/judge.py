"""LLM-as-judge with a fixed rubric. Its labels are only trusted after checking agreement
with human labels on a sample (`run.py label` + `run.py agreement`)."""

import html
import json
import re
from typing import Literal

from pydantic import BaseModel, ValidationError

from app.llm.providers import LLMRequest

JUDGE_SYSTEM = """You grade answers produced by a study assistant that must answer only \
from the course-note excerpts it was given. Follow the rubric exactly and reply with one \
JSON object and nothing else.

Rubric
1. claims: split the answer into short, atomic factual claims. Ignore citation markers \
like [S1], greetings and hedging. An answer that only says the notes don't cover the \
question has no claims.
2. supported: for each claim, true if the sources state it or directly imply it, false \
otherwise, even if the claim is true in general. Judge only against the sources.
3. correctness, comparing the answer with the reference answer:
   - "correct": conveys the key facts of the reference and contradicts nothing in it
   - "partial": some key facts missing, or a minor inaccuracy
   - "incorrect": wrong, contradicts the reference, or refuses although a reference exists
4. reason: one sentence explaining the correctness grade.

Reply format:
{"claims": [{"claim": "...", "supported": true}], "correctness": "correct", "reason": "..."}"""


class Claim(BaseModel):
    claim: str
    supported: bool


class Judgement(BaseModel):
    claims: list[Claim]
    correctness: Literal["correct", "partial", "incorrect"]
    reason: str

    @property
    def faithfulness(self) -> float | None:
        """Share of claims supported by the sources; None when the answer makes no claims."""
        if not self.claims:
            return None
        return sum(c.supported for c in self.claims) / len(self.claims)

    @property
    def correctness_score(self) -> float:
        return {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}[self.correctness]


def judge_request(question: str, reference: str, answer: str, sources: str) -> LLMRequest:
    user = (
        f"{sources}\n\n<question>{html.escape(question, quote=False)}</question>\n\n"
        f"<reference_answer>{html.escape(reference, quote=False)}</reference_answer>\n\n"
        f"<answer>{html.escape(answer, quote=False)}</answer>"
    )
    return LLMRequest(system=JUDGE_SYSTEM, user=user, max_tokens=4000)


def parse_judgement(text: str) -> Judgement:
    """Accepts the JSON object alone or wrapped in prose/code fences."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("judge reply contains no JSON object")
    try:
        return Judgement.model_validate(json.loads(match.group()))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"judge reply doesn't match the rubric format: {exc}") from None
