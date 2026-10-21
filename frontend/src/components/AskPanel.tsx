"use client";

import { type FormEvent, useRef, useState } from "react";

import { ApiError, ask, documentFileUrl } from "@/lib/api";
import { useApiErrorHandler } from "@/lib/auth";
import type { AnswerDone } from "@/lib/types";

import { AnswerText } from "./AnswerText";
import { Alert, Button, Card, Spinner } from "./ui";

type State =
  | { phase: "idle" }
  | { phase: "streaming"; text: string }
  | { phase: "done"; text: string; done: AnswerDone }
  | { phase: "error"; message: string };

export function AskPanel({ collectionId, hasReadyDocuments }: { collectionId: string; hasReadyDocuments: boolean }) {
  const handleError = useApiErrorHandler();
  const [question, setQuestion] = useState("");
  const [asked, setAsked] = useState("");
  const [state, setState] = useState<State>({ phase: "idle" });
  const abortRef = useRef<AbortController | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const q = question.trim();
    if (!q) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setAsked(q);
    setState({ phase: "streaming", text: "" });

    let text = "";
    try {
      await ask(
        collectionId,
        q,
        (event) => {
          if (event.type === "token") {
            text += event.text;
            setState({ phase: "streaming", text });
          } else if (event.type === "done") {
            setState({ phase: "done", text: event.data.answer, done: event.data });
          } else {
            setState({ phase: "error", message: event.message }); // discard partial text
          }
        },
        controller.signal,
      );
    } catch (err) {
      if (controller.signal.aborted) return;
      if (err instanceof ApiError && err.status === 429) {
        setState({ phase: "error", message: err.message });
        return;
      }
      const message = handleError(err);
      if (message) setState({ phase: "error", message });
    }
  }

  function stop() {
    abortRef.current?.abort();
    setState({ phase: "idle" });
  }

  const streaming = state.phase === "streaming";

  return (
    <Card className="space-y-4">
      <h2 className="display text-3xl">Ask your notes</h2>
      <form onSubmit={submit} className="space-y-2">
        <textarea
          aria-label="Your question"
          rows={3}
          maxLength={500}
          placeholder={hasReadyDocuments ? "e.g. What does third normal form eliminate?" : "Upload notes first, then ask about them."}
          disabled={!hasReadyDocuments}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              e.currentTarget.form?.requestSubmit();
            }
          }}
          className="w-full resize-none rounded-xl border border-border bg-surface px-3 py-2 text-sm outline-none placeholder:text-muted focus:border-accent focus:ring-2 focus:ring-accent/20 disabled:opacity-60"
        />
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted">Answers come only from your notes, with page citations.</span>
          {streaming ? (
            <Button type="button" variant="secondary" onClick={stop}>
              Stop
            </Button>
          ) : (
            <Button type="submit" disabled={!question.trim() || !hasReadyDocuments}>
              Ask
            </Button>
          )}
        </div>
      </form>

      {state.phase !== "idle" && (
        <div className="space-y-3 border-t border-border pt-4" aria-live="polite">
          <p className="text-sm font-medium text-muted">{asked}</p>
          {state.phase === "error" && <Alert>{state.message}</Alert>}
          {streaming && !state.text && (
            <p className="flex items-center gap-2 text-sm text-muted">
              <Spinner /> Searching your notes…
            </p>
          )}
          {(state.phase === "streaming" || state.phase === "done") && state.text && (
            <AnswerText text={state.text} citations={state.phase === "done" ? state.done.citations : []} />
          )}
          {state.phase === "done" && <AnswerFooter collectionId={collectionId} done={state.done} />}
        </div>
      )}
    </Card>
  );
}

function AnswerFooter({ collectionId, done }: { collectionId: string; done: AnswerDone }) {
  return (
    <div className="space-y-3">
      {done.truncated && <Alert tone="warning">This answer was cut short. Try a narrower question.</Alert>}
      {!done.grounded && done.citations.length === 0 && done.answer && !done.answer.startsWith("I couldn't find") && (
        <Alert tone="warning">This answer has no citations, so check it against your notes.</Alert>
      )}
      {done.citations.length > 0 && (
        <div>
          <h3 className="label-mono mb-2">Sources</h3>
          <ol className="space-y-1 text-sm">
            {done.citations.map((c) => (
              <li key={c.id} id={`cite-${c.id}`} className="flex flex-wrap items-baseline gap-x-2">
                <span className="font-mono text-xs text-accent">{c.id}</span>
                <a
                  href={documentFileUrl(collectionId, c.document_id)}
                  className="font-medium hover:underline"
                  title="Download this document"
                >
                  {c.document_title}
                </a>
                <span className="text-muted">
                  page {c.page}
                  {c.heading ? ` · ${c.heading}` : ""}
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}
      {done.cached && <p className="text-xs text-muted">Answered from cache. Your notes haven&apos;t changed since.</p>}
    </div>
  );
}
