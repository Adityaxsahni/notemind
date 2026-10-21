"""Renders result tables into ml/eval/REPORT.md between generated-section markers, so the
hand-written analysis around them survives regeneration."""

import math
import re
from pathlib import Path

REPORT = Path(__file__).parent / "REPORT.md"


def fmt(value, digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "–"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def retrieval_table(results: list[dict]) -> str:
    header = (
        "| Variant | Chunks | Pool | R@1 | R@3 | R@6 | MRR | nDCG@6 | Multi-hop R@6 "
        "| Refusal recall | False refusal | p50 / p95 latency |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    rows = []
    for r in results:
        v, m = r["variant"], r["metrics"]
        method = "+".join(
            x for x, on in (("vector", v["use_vector"]), ("keyword", v["use_keyword"])) if on
        )
        rows.append(
            f"| {v['name']} | {v['chunks']} | {v['candidates']} {method}"
            f"{' → ' + v['reranker'] if v['rerank'] else ''} "
            f"| {fmt(m['recall@1'])} | {fmt(m['recall@3'])} | **{fmt(m['recall@6'])}** "
            f"| {fmt(m['mrr'])} | {fmt(m['ndcg@6'])} | {fmt(m['multi_hop_recall@6'])} "
            f"| {fmt(m.get('refusal_recall'))} | {fmt(m.get('false_refusal'))} "
            f"| {fmt(m['latency_p50_s'])} / {fmt(m['latency_p95_s'])} s |"
        )
    return header + "\n".join(rows) + "\n"


def answers_table(runs: list[dict]) -> str:
    columns = [
        ("Correctness", "correctness"),
        ("Faithfulness", "faithfulness"),
        ("Fully faithful", "fully_faithful_rate"),
        ("Citation precision", "citation_precision"),
        ("Grounded", "grounded_rate"),
        ("Refusal recall", "refusal_recall"),
        ("False refusal", "false_refusal"),
        ("LLM skipped", "llm_skipped_rate"),
        ("TTFT p50 (s)", "ttft_p50_s"),
        ("E2E p95 (s)", "e2e_p95_s"),
    ]
    header = (
        "| Answer model | " + " | ".join(title for title, _ in columns) + " | $/question |\n"
        "|---|" + "---|" * (len(columns) + 1) + "\n"
    )
    rows = []
    for run in runs:
        m = run["metrics"]
        cells = " | ".join(fmt(m[key]) for _, key in columns)
        rows.append(
            f"| {run['config']['answer_model']} | {cells} | {fmt(m['cost_per_question_usd'], 4)} |"
        )
    return header + "\n".join(rows) + f"\n\nJudge: {runs[0]['config']['judge_model']}.\n"


def threshold_table(results: list[dict]) -> str:
    rows = [
        f"| {r['variant']['name']} | {fmt(r['metrics']['best_threshold'], 1)} "
        f"| {fmt(r['metrics']['best_threshold_balanced_accuracy'])} |"
        for r in results
        if "best_threshold" in r["metrics"]
    ]
    return (
        "| Variant | Best cutoff (logit) | Balanced accuracy at best cutoff |\n|---|---|---|\n"
        + "\n".join(rows)
        + "\n"
    )


def write_section(name: str, body: str, report: Path = REPORT) -> None:
    begin, end = f"<!-- BEGIN:{name} -->", f"<!-- END:{name} -->"
    text = report.read_text(encoding="utf-8") if report.exists() else ""
    block = f"{begin}\n{body.rstrip()}\n{end}"
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.DOTALL)
    text = (
        pattern.sub(lambda _: block, text)
        if pattern.search(text)
        else f"{text.rstrip()}\n\n{block}\n"
    )
    report.write_text(text.lstrip(), encoding="utf-8")
