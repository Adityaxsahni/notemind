"use client";

import { type FormEvent, useState } from "react";

import { ApiError, createQuiz, documentFileUrl } from "@/lib/api";
import { useApiErrorHandler } from "@/lib/auth";
import type { Quiz, QuizQuestion } from "@/lib/types";

import { Alert, Button, Card, Input, Spinner } from "./ui";

type State =
  | { phase: "idle" }
  | { phase: "loading" }
  | { phase: "ready"; quiz: Quiz; picked: (number | null)[] }
  | { phase: "error"; message: string };

const SIZES = [3, 5, 10];

export function QuizPanel({ collectionId, hasReadyDocuments }: { collectionId: string; hasReadyDocuments: boolean }) {
  const handleError = useApiErrorHandler();
  const [topic, setTopic] = useState("");
  const [size, setSize] = useState(5);
  const [state, setState] = useState<State>({ phase: "idle" });

  async function submit(event: FormEvent) {
    event.preventDefault();
    setState({ phase: "loading" });
    try {
      const quiz = await createQuiz(collectionId, size, topic.trim() || undefined);
      setState({ phase: "ready", quiz, picked: quiz.questions.map(() => null) });
    } catch (err) {
      if (err instanceof ApiError && [429, 502, 503].includes(err.status)) {
        setState({ phase: "error", message: err.message });
        return;
      }
      const message = handleError(err);
      setState(message ? { phase: "error", message } : { phase: "idle" });
    }
  }

  function pick(question: number, option: number) {
    if (state.phase !== "ready" || state.picked[question] !== null) return;
    const picked = [...state.picked];
    picked[question] = option;
    setState({ ...state, picked });
  }

  const answered = state.phase === "ready" ? state.picked.filter((p) => p !== null).length : 0;
  const score =
    state.phase === "ready" ? state.picked.filter((p, i) => p === state.quiz.questions[i].answer).length : 0;

  return (
    <Card className="space-y-4">
      <h2 className="display text-3xl">Quiz yourself</h2>
      <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
        <div className="min-w-48 flex-1">
          <Input
            aria-label="Quiz topic (optional)"
            maxLength={200}
            placeholder="Topic (optional), e.g. transactions"
            disabled={!hasReadyDocuments}
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
          />
        </div>
        <select
          aria-label="Number of questions"
          value={size}
          onChange={(e) => setSize(Number(e.target.value))}
          disabled={!hasReadyDocuments}
          className="rounded-xl border border-border bg-surface px-3 py-2 text-sm"
        >
          {SIZES.map((n) => (
            <option key={n} value={n}>
              {n} questions
            </option>
          ))}
        </select>
        <Button type="submit" disabled={!hasReadyDocuments || state.phase === "loading"}>
          {state.phase === "loading" ? <Spinner label="Writing quiz" /> : null}
          {state.phase === "ready" ? "New quiz" : "Start quiz"}
        </Button>
      </form>

      {state.phase === "loading" && <p className="text-sm text-muted">Writing questions from your notes…</p>}
      {state.phase === "error" && <Alert>{state.message}</Alert>}
      {state.phase === "ready" && !state.quiz.found && (
        <Alert tone="info">Your notes don&apos;t seem to cover that topic. Try another, or leave it empty.</Alert>
      )}
      {state.phase === "ready" && state.quiz.found && (
        <div className="space-y-5 border-t border-border pt-4">
          {state.quiz.questions.map((q, i) => (
            <QuestionCard
              key={i}
              number={i + 1}
              question={q}
              picked={state.picked[i]}
              onPick={(option) => pick(i, option)}
              collectionId={collectionId}
            />
          ))}
          <p className="text-sm font-medium" aria-live="polite">
            {answered === state.quiz.questions.length
              ? `Score: ${score} / ${state.quiz.questions.length}`
              : `${answered} of ${state.quiz.questions.length} answered`}
          </p>
        </div>
      )}
    </Card>
  );
}

function QuestionCard({
  number,
  question,
  picked,
  onPick,
  collectionId,
}: {
  number: number;
  question: QuizQuestion;
  picked: number | null;
  onPick: (option: number) => void;
  collectionId: string;
}) {
  const done = picked !== null;
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium">
        {number}. {question.question}
      </legend>
      <div className="grid gap-2">
        {question.options.map((option, i) => {
          const isAnswer = i === question.answer;
          const tone = !done
            ? "border-border hover:border-foreground"
            : isAnswer
              ? "border-success text-success"
              : i === picked
                ? "border-danger text-danger"
                : "border-border opacity-60";
          return (
            <button
              key={i}
              type="button"
              disabled={done}
              onClick={() => onPick(i)}
              aria-pressed={i === picked}
              className={`rounded-xl border bg-surface px-3.5 py-2.5 text-left text-sm transition ${tone}`}
            >
              {option}
              {done && isAnswer && <span className="sr-only"> (correct answer)</span>}
            </button>
          );
        })}
      </div>
      {done && (
        <p className="text-sm text-muted">
          {picked === question.answer ? "Correct. " : "Not quite. "}
          {question.explanation}{" "}
          <a href={documentFileUrl(collectionId, question.citation.document_id)} className="text-accent hover:underline">
            {question.citation.document_title}, page {question.citation.page}
          </a>
        </p>
      )}
    </fieldset>
  );
}
