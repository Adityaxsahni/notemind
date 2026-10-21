"""Validating the LLM judge against human labels.

`export_sample` writes a CSV of judged answers with empty `human_*` columns. Fill them in
(correctness: correct/partial/incorrect; all_supported: yes/no) without looking at the
judge's columns first, then `agreement` reports how often the judge matches you.
"""

import csv
import json
import random
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from .dataset import load_questions

FIELDS = [
    "id",
    "type",
    "question",
    "reference",
    "answer",
    "human_correctness",
    "human_all_supported",
    "notes",
    "judge_correctness",
    "judge_all_supported",
    "judge_reason",
]


def export_sample(results_path: Path, set_name: str, out: Path, n: int = 40, seed: int = 7) -> int:
    results = json.loads(results_path.read_text(encoding="utf-8"))
    questions = {q.id: q for q in load_questions(set_name)}
    judged = [r for r in results["questions"] if "judge" in r]
    # Stratify by question type so multi-hop and unanswerable cases are represented.
    rng = random.Random(seed)  # noqa: S311  # reproducible sampling, not security
    by_type: dict[str, list[dict]] = {}
    for row in judged:
        by_type.setdefault(row["type"], []).append(row)
    sample: list[dict] = []
    while len(sample) < min(n, len(judged)):
        for rows in by_type.values():
            if rows and len(sample) < n:
                sample.append(rows.pop(rng.randrange(len(rows))))
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for row in sample:
            q = questions[row["id"]]
            supported = all(c["supported"] for c in row["judge"]["claims"])
            writer.writerow(
                {
                    "id": row["id"],
                    "type": row["type"],
                    "question": q.question,
                    "reference": q.answer,
                    "answer": row["answer"],
                    "human_correctness": "",
                    "human_all_supported": "",
                    "notes": "",
                    "judge_correctness": row["judge"]["correctness"],
                    "judge_all_supported": "yes" if supported else "no",
                    "judge_reason": row["judge"]["reason"],
                }
            )
    return len(sample)


def cohen_kappa(a: Sequence[str], b: Sequence[str]) -> float:
    """Agreement corrected for chance: 1 is perfect, 0 is what random labels would give."""
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[label] * cb[label] for label in set(a) | set(b)) / (n * n)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def agreement(labels_csv: Path) -> dict[str, float]:
    with labels_csv.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["human_correctness"].strip()]
    if not rows:
        raise ValueError("no human labels filled in yet")
    result: dict[str, float] = {"labelled": len(rows)}
    for field in ("correctness", "all_supported"):
        human = [r[f"human_{field}"].strip().lower() for r in rows]
        judge = [r[f"judge_{field}"].strip().lower() for r in rows]
        result[f"{field}_agreement"] = sum(h == j for h, j in zip(human, judge, strict=True)) / len(
            rows
        )
        result[f"{field}_kappa"] = cohen_kappa(human, judge)
    return result
