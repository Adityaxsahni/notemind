import csv

import pytest

from app.llm.providers import Completion
from ml.eval import answer_eval
from ml.eval.answer_eval import Pacer, cost_usd, summarize_answers
from ml.eval.dataset import Question
from ml.eval.judge import parse_judgement
from ml.eval.labels import agreement, cohen_kappa
from ml.eval.report import write_section

VALID = '{"claims": [{"claim": "3NF removes transitive dependencies", "supported": true}, {"claim": "BCNF is weaker", "supported": false}], "correctness": "partial", "reason": "Second claim is wrong."}'


def test_parse_judgement_from_bare_and_wrapped_json():
    for text in (VALID, f"Here is my grading:\n```json\n{VALID}\n```"):
        judgement = parse_judgement(text)
        assert judgement.faithfulness == 0.5
        assert judgement.correctness_score == 0.5


@pytest.mark.parametrize(
    "text",
    ["no json here", '{"claims": [], "correctness": "great", "reason": "x"}', "{not json}"],
)
def test_parse_judgement_rejects_off_rubric_replies(text):
    with pytest.raises(ValueError):
        parse_judgement(text)


def test_answer_without_claims_has_no_faithfulness_score():
    assert (
        parse_judgement(
            '{"claims": [], "correctness": "incorrect", "reason": "refused"}'
        ).faithfulness
        is None
    )


def test_cohen_kappa():
    assert cohen_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    assert cohen_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"]) == 0.0  # chance level
    assert cohen_kappa(["a", "a"], ["a", "a"]) == 1.0  # one label everywhere


def test_agreement_reads_only_labelled_rows(tmp_path):
    path = tmp_path / "labels.csv"
    rows = [
        ("correct", "yes", "correct", "yes"),
        ("partial", "no", "correct", "yes"),
        ("", "", "incorrect", "no"),  # not labelled yet
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["human_correctness", "human_all_supported", "judge_correctness", "judge_all_supported"]
        )
        writer.writerows(rows)
    result = agreement(path)
    assert result["labelled"] == 2
    assert result["correctness_agreement"] == 0.5


def test_cost_uses_list_prices():
    completion = Completion("m", "end_turn", input_tokens=1_000_000, output_tokens=100_000)
    assert cost_usd("claude-opus-5-5", completion) == pytest.approx(4.0 + 2.0)
    assert cost_usd("claude-haiku-5-5", completion) == pytest.approx(0.10 + 0.05)


def test_summarize_answers():
    rows = [
        {
            "id": "a",
            "type": "single",
            "refused": False,
            "llm_called": True,
            "cited_pages": [("d", 1)],
            "correctness": 1.0,
            "faithfulness": 1.0,
            "citation_precision": 1.0,
            "cost_usd": 0.02,
            "e2e_s": 2.0,
            "ttft_s": 1.0,
        },
        {
            "id": "b",
            "type": "single",
            "refused": True,
            "llm_called": False,
            "cited_pages": [],
            "correctness": 0.0,
            "cost_usd": 0.0,
            "e2e_s": 0.3,
        },
        {
            "id": "c",
            "type": "unanswerable",
            "refused": True,
            "llm_called": False,
            "cited_pages": [],
            "cost_usd": 0.0,
            "e2e_s": 0.3,
        },
        {"id": "d", "type": "single", "skipped": "token cap reached"},
    ]
    m = summarize_answers(rows)
    assert m["questions"] == 3 and m["skipped"] == 1
    assert m["correctness"] == 0.5
    assert m["false_refusal"] == 0.5
    assert m["refusal_recall"] == 1.0
    assert m["grounded_rate"] == 1.0
    assert m["cost_per_question_usd"] == pytest.approx(0.02 / 3)


def test_question_validation():
    with pytest.raises(ValueError):
        Question(id="x", course="c", type="unanswerable", question="Why?", gold=[("d.pdf", 1)])
    with pytest.raises(ValueError):
        Question(
            id="x", course="c", type="multi_hop", question="Why?", gold=[("d.pdf", 1)], answer="a"
        )


def test_report_sections_preserve_hand_written_text(tmp_path):
    report = tmp_path / "REPORT.md"
    report.write_text("# Report\n\nMy analysis.\n", encoding="utf-8")
    write_section("t", "| a |", report)
    write_section("t", "| b |", report)
    text = report.read_text(encoding="utf-8")
    assert "My analysis." in text
    assert "| b |" in text and "| a |" not in text
    assert text.count("BEGIN:t") == 1


def test_pacer_spaces_calls_to_the_quota(monkeypatch):
    clock, slept = [100.0], []

    def sleep(seconds):
        slept.append(seconds)
        clock[0] += seconds

    monkeypatch.setattr(answer_eval.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(answer_eval.time, "sleep", sleep)
    pacer = Pacer(rpm=4)  # one call per 15 s
    pacer.wait()  # first call goes straight through
    clock[0] += 5  # the call took 5 s
    pacer.wait()
    clock[0] += 20  # slower than the interval: no wait needed
    pacer.wait()
    assert slept == [10.0]
