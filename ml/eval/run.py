"""NoteMind evaluation CLI. From the repo root:

    uv run --project backend --group eval python -m ml.eval.run retrieval --set seed
    uv run --project backend python -m ml.eval.run retrieval --set seed --only baseline \\
        --min recall@6=0.95 --max false_refusal=0.05      # CI regression gate
    uv run --project backend python -m ml.eval.run answers --set seed --dry-run   # free
    uv run --project backend python -m ml.eval.run answers --set seed --yes       # costs money
    uv run --project backend python -m ml.eval.run label --results <answers.json>
    uv run --project backend python -m ml.eval.run agreement --labels <labels.csv>
    uv run --project backend python -m ml.eval.run generate --set mine --course dbms --yes
"""

import argparse
import json
import logging
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.embeddings import get_embedder
from app.llm.providers import AnthropicProvider
from app.rag.reranker import CrossEncoderReranker, get_reranker

from .answer_eval import PRICES, DryRunLLM, eval_gateway, evaluate_answers
from .dataset import describe, load_questions
from .generate import generate, save_generated
from .index import ChunkConfig, build_indexes, eval_engine
from .labels import agreement, export_sample
from .report import answers_table, retrieval_table, threshold_table, write_section
from .retrieval_eval import RERANKERS, Variant, run_variant
from .tracking import log_run

RESULTS_DIR = Path(__file__).parent / "results"

BASELINE = Variant("baseline: hybrid → rerank")
ABLATIONS = [
    BASELINE,
    # First stage alone: what the reranker gets to work with.
    Variant("vector only, no rerank", use_keyword=False, rerank=False),
    Variant("keyword only, no rerank", use_vector=False, rerank=False),
    Variant("hybrid (RRF), no rerank", rerank=False),
    Variant("vector → rerank", use_keyword=False),
    # Chunking.
    Variant("chunks 200/30", chunks=ChunkConfig(200, 30)),
    Variant("chunks 400/0 (no overlap)", chunks=ChunkConfig(400, 0)),
    Variant("chunks 800/120 (> model's 512)", chunks=ChunkConfig(800, 120)),
    # Rerank pool size: latency vs recall.
    Variant("rerank pool 10", candidates=10),
    Variant("rerank pool 20", candidates=20),
    Variant("reranker bge-base", reranker="bge-base"),
]
# Every course in one collection: three times the distractors per question.
COMBINED = [
    replace(v, name=f"combined: {v.name}", combined=True)
    for v in (ABLATIONS[0], ABLATIONS[1], ABLATIONS[3], ABLATIONS[8])
]

# Rough per-call size at default settings, for the cost estimate shown before spending.
TOKENS_PER_ANSWER = (2600, 700)  # input (prompt + 6 sources), output (incl. thinking)
TOKENS_PER_JUDGEMENT = (3000, 500)


def _default_chunks() -> ChunkConfig:
    settings = get_settings()
    return ChunkConfig(settings.chunk_target_tokens, settings.chunk_overlap_tokens)


def _save(name: str, data) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{name}.json"
    out.write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")
    return out


def cmd_retrieval(args: argparse.Namespace) -> int:
    questions = load_questions(args.set)
    variants = [BASELINE] if args.only == "baseline" else ABLATIONS + COMBINED
    print(f"set {args.set!r}: {describe(questions)}; {len(variants)} variant(s)")

    embedder = get_embedder()
    rerankers: dict = {}
    min_score = get_settings().retrieval_min_score
    results = []
    with Session(eval_engine()) as session:
        for variant in variants:
            indexes = build_indexes(
                session, embedder, args.set, variant.chunks, combined=variant.combined
            )
            if variant.reranker not in rerankers:
                rerankers[variant.reranker] = CrossEncoderReranker(*RERANKERS[variant.reranker])
            result = run_variant(
                session,
                embedder,
                rerankers[variant.reranker],
                variant,
                questions,
                indexes,
                min_score=min_score,
            )
            result["index"] = {
                course: {
                    "chunks": ix.chunks,
                    "mean_tokens": ix.mean_tokens,
                    "truncated": ix.truncated,
                }
                for course, ix in indexes.items()
            }
            results.append(result)
            m = result["metrics"]
            print(
                f"  {variant.name:40s} R@6={m['recall@6']:.3f} MRR={m['mrr']:.3f} "
                f"p50={m['latency_p50_s']:.2f}s"
            )

    out = _save(f"{args.set}-retrieval", results)
    if not args.no_tracking:
        for result in results:
            log_run(f"retrieval-{args.set}", result, out)
    if args.only != "baseline":
        write_section(f"retrieval-{args.set}", retrieval_table(results))
        write_section(f"thresholds-{args.set}", threshold_table(results))
    print(f"results: {out}")
    return check_limits(results[0]["metrics"], args.min, args.max)


def _estimate_usd(model: str, calls: int, tokens: tuple[int, int]) -> float:
    input_price, output_price = PRICES[model]
    return calls * (tokens[0] * input_price + tokens[1] * output_price) / 1e6


def _provider(model: str, effort: str) -> AnthropicProvider:
    settings = get_settings()
    if settings.llm_api_key is None or not settings.llm_api_key.get_secret_value():
        raise SystemExit("LLM_API_KEY is not set in .env (or use --dry-run)")
    return AnthropicProvider(
        api_key=settings.llm_api_key.get_secret_value(),
        model=model,
        effort=effort,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )


def cmd_answers(args: argparse.Namespace) -> int:
    settings = get_settings()
    questions = load_questions(args.set)[: args.limit or None]
    if args.dry_run:
        answer_llm = judge_llm = DryRunLLM()
    else:
        estimate = _estimate_usd(
            args.answer_model, len(questions), TOKENS_PER_ANSWER
        ) + _estimate_usd(args.judge_model, len(questions), TOKENS_PER_JUDGEMENT)
        print(
            f"{len(questions)} questions: answers by {args.answer_model}, judged by "
            f"{args.judge_model}. Estimated cost ~${estimate:.2f} "
            f"(hard cap {args.max_tokens:,} tokens)."
        )
        if not args.yes:
            print("Nothing spent. Re-run with --yes to proceed.")
            return 2
        answer_llm = _provider(args.answer_model, settings.llm_answer_effort)
        judge_llm = _provider(args.judge_model, "medium")

    with Session(eval_engine()) as session:
        indexes = build_indexes(session, get_embedder(), args.set, _default_chunks())
        result = evaluate_answers(
            session,
            get_embedder(),
            get_reranker(),
            eval_gateway(answer_llm, args.max_tokens),
            eval_gateway(judge_llm, args.max_tokens),
            questions,
            indexes,
            answer_model=args.answer_model,
            judge_model=args.judge_model,
            max_tokens=settings.llm_answer_max_tokens,
        )
    result["config"] = {
        "answer_model": "dry-run" if args.dry_run else args.answer_model,
        "judge_model": "dry-run" if args.dry_run else args.judge_model,
        "effort": settings.llm_answer_effort,
        "top_k": settings.retrieval_top_k,
        "min_score": settings.retrieval_min_score,
    }
    out = _save(f"{args.set}-answers-{'dryrun' if args.dry_run else args.answer_model}", result)
    for name, value in result["metrics"].items():
        print(f"  {name:24s} {value}")
    if not args.dry_run:
        latest = {}  # newest run per answer model
        for path in sorted(RESULTS_DIR.glob(f"*-{args.set}-answers-claude-*.json")):
            run = json.loads(path.read_text(encoding="utf-8"))
            latest[run["config"]["answer_model"]] = run
        write_section(f"answers-{args.set}", answers_table(list(latest.values())))
    print(f"results: {out}")
    return 0


def cmd_label(args: argparse.Namespace) -> int:
    out = args.results.with_suffix(".labels.csv")
    n = export_sample(args.results, args.set, out, n=args.n)
    print(f"wrote {n} rows to {out}: fill in the human_* columns, then run `agreement`")
    return 0


def cmd_agreement(args: argparse.Namespace) -> int:
    for name, value in agreement(args.labels).items():
        print(f"  {name:24s} {value:.3f}")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    if not args.yes:
        print("Generating questions calls the LLM (cents per course). Re-run with --yes.")
        return 2
    with Session(eval_engine()) as session:
        indexes = build_indexes(session, get_embedder(), args.set, _default_chunks())
        drafted = generate(
            session,
            eval_gateway(_provider(args.model, "low"), 500_000),
            args.course,
            indexes[args.course],
            single=args.single,
            multi_hop=args.multi_hop,
            unanswerable=args.unanswerable,
        )
    print(f"drafted {len(drafted)} questions into {save_generated(args.set, drafted)} for review")
    return 0


def check_limits(metrics: dict, minimums: list[str], maximums: list[str]) -> int:
    failed = []
    for specs, too_low in ((minimums, True), (maximums, False)):
        for spec in specs:
            name, _, value = spec.partition("=")
            if (metrics[name] < float(value)) if too_low else (metrics[name] > float(value)):
                failed.append(f"{name}={metrics[name]:.3f} {'<' if too_low else '>'} {value}")
    for line in failed:
        print(f"REGRESSION: {line}", file=sys.stderr)
    return 1 if failed else 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for noisy in (
        "sentence_transformers",
        "httpx",
        "httpx2",
        "huggingface_hub",
        "app.rag.retriever",
        "app.llm.gateway",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    models = sorted(PRICES)

    parser = argparse.ArgumentParser(prog="python -m ml.eval.run")
    sub = parser.add_subparsers(dest="command", required=True)

    retrieval = sub.add_parser("retrieval", help="retrieval metrics and ablations (free)")
    retrieval.add_argument("--set", default="seed")
    retrieval.add_argument("--only", choices=["baseline", "all"], default="all")
    retrieval.add_argument(
        "--min",
        action="append",
        default=[],
        metavar="METRIC=VALUE",
        help="exit 1 if the baseline scores below this",
    )
    retrieval.add_argument(
        "--max",
        action="append",
        default=[],
        metavar="METRIC=VALUE",
        help="exit 1 if the baseline scores above this",
    )
    retrieval.add_argument("--no-tracking", action="store_true", help="skip MLflow logging")
    retrieval.set_defaults(func=cmd_retrieval)

    answers = sub.add_parser("answers", help="end-to-end answer quality with an LLM judge")
    answers.add_argument("--set", default="seed")
    answers.add_argument("--answer-model", default=get_settings().llm_answer_model, choices=models)
    answers.add_argument("--judge-model", default="claude-opus-5-5", choices=models)
    answers.add_argument("--max-tokens", type=int, default=1_000_000, help="hard cap for the run")
    answers.add_argument("--limit", type=int, help="only the first N questions")
    answers.add_argument("--dry-run", action="store_true", help="scripted fake LLM: free")
    answers.add_argument("--yes", action="store_true", help="confirm spending")
    answers.set_defaults(func=cmd_answers)

    label = sub.add_parser("label", help="export judged answers for human labelling")
    label.add_argument("--results", type=Path, required=True)
    label.add_argument("--set", default="seed")
    label.add_argument("--n", type=int, default=40)
    label.set_defaults(func=cmd_label)

    agree = sub.add_parser("agreement", help="judge vs human agreement")
    agree.add_argument("--labels", type=Path, required=True)
    agree.set_defaults(func=cmd_agreement)

    gen = sub.add_parser("generate", help="draft questions from notes for human review")
    gen.add_argument("--set", required=True)
    gen.add_argument("--course", required=True)
    gen.add_argument("--model", default=get_settings().llm_answer_model, choices=models)
    gen.add_argument("--single", type=int, default=30)
    gen.add_argument("--multi-hop", type=int, default=5)
    gen.add_argument("--unanswerable", type=int, default=10)
    gen.add_argument("--yes", action="store_true", help="confirm spending")
    gen.set_defaults(func=cmd_generate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
