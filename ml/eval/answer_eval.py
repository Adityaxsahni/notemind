"""End-to-end answer evaluation: the app's retrieval, prompt, citation filter and LLM gateway,
then an LLM judge. Costs money: the CLI prints an estimate and needs `--yes`."""

import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import fakeredis
from sqlalchemy.orm import Session

from app.embeddings import Embedder
from app.llm.gateway import BudgetExceeded, LLMGateway
from app.llm.providers import Completion, LLMEvent, LLMProvider, LLMRequest, TextDelta
from app.rag.answer import (
    NOT_FOUND,
    SYSTEM_PROMPT,
    CitationFilter,
    build_user_prompt,
    render_sources,
)
from app.rag.reranker import Reranker
from app.rag.retriever import RetrievalOptions, retrieve

from .dataset import Question
from .index import CourseIndex
from .judge import judge_request, parse_judgement
from .metrics import mean, percentile

# USD per million tokens (input, output), Anthropic list prices, Oct 2026. Models missing here
# (e.g. Gemini on its free tier) report cost as unknown.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}
UNANSWERABLE_REFERENCE = (
    "The notes don't cover this; the assistant should say so instead of answering."
)
EVAL_USER = uuid.UUID(int=0)


@dataclass
class Call:
    text: str
    completion: Completion
    ttft_s: float | None
    total_s: float


def cost_usd(model: str, completion: Completion) -> float:
    input_price, output_price = PRICES.get(model, (float("nan"), float("nan")))
    return (completion.input_tokens * input_price + completion.output_tokens * output_price) / 1e6


class Pacer:
    """Spaces calls to stay under a requests-per-minute quota, such as a free API tier's.
    Share one per model: the quota counts the answer and judge calls together."""

    def __init__(self, rpm: float) -> None:
        self._interval = 60.0 / rpm
        self._next = 0.0

    def wait(self) -> None:
        delay = self._next - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        self._next = time.monotonic() + self._interval


class PacedProvider:
    def __init__(self, provider: LLMProvider, pacer: Pacer) -> None:
        self._provider, self._pacer = provider, pacer

    def stream(self, request: LLMRequest) -> Iterator[LLMEvent]:
        self._pacer.wait()
        yield from self._provider.stream(request)


def eval_gateway(provider: LLMProvider, token_cap: int) -> LLMGateway:
    """The app's gateway with an in-memory counter: `token_cap` bounds the whole run."""
    return LLMGateway(
        provider, fakeredis.FakeRedis(), user_daily_budget=token_cap, global_daily_budget=token_cap
    )


def call(
    gateway: LLMGateway, request: LLMRequest, citation_filter: CitationFilter | None = None
) -> Call:
    started = time.perf_counter()
    reservation = gateway.reserve(EVAL_USER, request)
    parts, completion, ttft = [], None, None
    for event in gateway.stream(reservation, request):
        if isinstance(event, TextDelta):
            ttft = ttft or time.perf_counter() - started
            parts.append(citation_filter.feed(event.text) if citation_filter else event.text)
        else:
            completion = event
    if citation_filter:
        parts.append(citation_filter.flush())
    return Call("".join(parts).strip(), completion, ttft, time.perf_counter() - started)


def evaluate_answers(
    session: Session,
    embedder: Embedder,
    reranker: Reranker,
    answer_gateway: LLMGateway,
    judge_gateway: LLMGateway,
    questions: list[Question],
    indexes: dict[str, CourseIndex],
    *,
    answer_model: str,
    judge_model: str,
    max_tokens: int,
) -> dict:
    rows = []
    for q in questions:
        try:
            rows.append(
                _evaluate_one(
                    session,
                    embedder,
                    reranker,
                    answer_gateway,
                    judge_gateway,
                    q,
                    indexes[q.course],
                    answer_model=answer_model,
                    judge_model=judge_model,
                    max_tokens=max_tokens,
                )
            )
        except BudgetExceeded:
            rows.append({"id": q.id, "type": q.type, "skipped": "token cap reached"})
            break
    return {"metrics": summarize_answers(rows), "questions": rows}


def _evaluate_one(
    session,
    embedder,
    reranker,
    answer_gateway,
    judge_gateway,
    q,
    index,
    *,
    answer_model,
    judge_model,
    max_tokens,
) -> dict:
    started = time.perf_counter()
    result = retrieve(
        session,
        embedder,
        reranker,
        owner_id=index.owner_id,
        collection_id=index.collection_id,
        question=q.question,
        options=RetrievalOptions.from_settings(),
    )
    session.rollback()
    retrieval_s = time.perf_counter() - started
    row: dict = {"id": q.id, "type": q.type, "retrieval_s": retrieval_s, "llm_called": False}

    if result.low_confidence:
        row |= {"answer": NOT_FOUND, "cited_pages": [], "cost_usd": 0.0, "e2e_s": retrieval_s}
    else:
        sources = {f"S{i}": c for i, c in enumerate(result.chunks, start=1)}
        citation_filter = CitationFilter(set(sources))
        answer = call(
            answer_gateway,
            LLMRequest(SYSTEM_PROMPT, build_user_prompt(q.question, sources), max_tokens),
            citation_filter,
        )
        row |= {
            "llm_called": True,
            "answer": answer.text,
            "stop_reason": answer.completion.stop_reason,
            "cited_pages": [
                (sources[s].document_title, sources[s].page) for s in citation_filter.cited
            ],
            "ttft_s": answer.ttft_s,
            "e2e_s": retrieval_s + answer.total_s,
            "input_tokens": answer.completion.input_tokens,
            "output_tokens": answer.completion.output_tokens,
            "cost_usd": cost_usd(answer_model, answer.completion),
        }
        row["sources"] = render_sources(sources)

    row["refused"] = row["answer"].startswith(NOT_FOUND)
    if q.gold:
        cited = set(map(tuple, row["cited_pages"]))
        row["citation_precision"] = len(cited & q.gold_pages) / len(cited) if cited else None

    if not row["refused"]:
        verdict = call(
            judge_gateway,
            judge_request(
                q.question, q.answer or UNANSWERABLE_REFERENCE, row["answer"], row["sources"]
            ),
        )
        row["judge_cost_usd"] = cost_usd(judge_model, verdict.completion)
        try:
            judgement = parse_judgement(verdict.text)
            row |= {
                "judge": judgement.model_dump(),
                "faithfulness": judgement.faithfulness,
                "correctness": judgement.correctness_score if q.gold else None,
            }
        except ValueError as exc:
            row["judge_error"] = str(exc)
    elif q.gold:
        row["correctness"] = 0.0  # refused although the notes cover it
    row.pop("sources", None)  # chunk text stays out of result files
    return row


class DryRunLLM:
    """Free stand-in for `--dry-run`: answers by quoting source S1 and approves itself as
    judge. Exercises the whole pipeline; its numbers mean nothing and are never reported."""

    def stream(self, request: LLMRequest):
        if request.system == SYSTEM_PROMPT:
            start = request.user.find(">\n") + 2
            first = request.user[start : request.user.find("\n</source>")].split(". ")[0]
            text = f"{first} [S1]."
        else:
            text = (
                '{"claims": [{"claim": "quoted", "supported": true}], '
                '"correctness": "partial", "reason": "dry run"}'
            )
        yield TextDelta(text)
        yield Completion("dry-run", "end_turn", len(request.user) // 4, 40)


def summarize_answers(rows: list[dict]) -> dict:
    done = [r for r in rows if "skipped" not in r]
    answerable = [r for r in done if r["type"] != "unanswerable"]
    unanswerable = [r for r in done if r["type"] == "unanswerable"]
    answered = [r for r in done if not r["refused"]]
    faithful = [r["faithfulness"] for r in answered if r.get("faithfulness") is not None]
    ttfts = [r["ttft_s"] for r in done if r.get("ttft_s")]
    return {
        "questions": len(done),
        "skipped": len(rows) - len(done),
        "correctness": mean(
            [r["correctness"] for r in answerable if r.get("correctness") is not None]
        ),
        "faithfulness": mean(faithful),
        "fully_faithful_rate": mean([float(f == 1.0) for f in faithful]),
        "citation_precision": mean(
            [r["citation_precision"] for r in answerable if r.get("citation_precision") is not None]
        ),
        "grounded_rate": mean([float(bool(r["cited_pages"])) for r in answered]),
        "refusal_recall": mean([float(r["refused"]) for r in unanswerable]),
        "false_refusal": mean([float(r["refused"]) for r in answerable]),
        "llm_skipped_rate": mean([float(not r["llm_called"]) for r in done]),
        "ttft_p50_s": percentile(ttfts, 50) if ttfts else None,
        "e2e_p95_s": percentile([r["e2e_s"] for r in done], 95) if done else None,
        "cost_per_question_usd": mean([r["cost_usd"] for r in done]),
        "judge_cost_usd": sum(r.get("judge_cost_usd", 0.0) for r in done),
        "judge_errors": sum("judge_error" in r for r in done),
    }
