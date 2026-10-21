"use client";

import { type FormEvent, useEffect, useRef, useState } from "react";

import { ApiError, ask, documentFileUrl } from "@/lib/api";
import { useApiErrorHandler } from "@/lib/auth";
import type { AnswerDone, SourceRef } from "@/lib/types";

import { AnswerText } from "./AnswerText";
import { Alert, Button, Card, Spinner } from "./ui";

type State =
  | { phase: "idle" }
  | { phase: "streaming"; text: string; sources: SourceRef[] | null; startedAt: number }
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
    const startedAt = Date.now();
    setState({ phase: "streaming", text: "", sources: null, startedAt });

    let text = "";
    let sources: SourceRef[] | null = null;
    try {
      await ask(
        collectionId,
        q,
        (event) => {
          if (event.type === "sources") {
            sources = event.sources;
            setState({ phase: "streaming", text, sources, startedAt });
          } else if (event.type === "token") {
            text += event.text;
            setState({ phase: "streaming", text, sources, startedAt });
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
          {state.phase === "streaming" && !state.text && (
            <AnswerProgress sources={state.sources} startedAt={state.startedAt} />
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

/** What's happening while the model writes: search results first, then a live timer. */
function AnswerProgress({ sources, startedAt }: { sources: SourceRef[] | null; startedAt: number }) {
  const [now, setNow] = useState(startedAt);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const seconds = Math.max(0, Math.round((now - startedAt) / 1000));
  const pages = sources ? [...new Set(sources.map((s) => s.page))].sort((a, b) => a - b) : [];
  const documents = sources ? new Set(sources.map((s) => s.document_title)).size : 0;

  return (
    <div className="space-y-2 rounded-xl bg-surface-2 p-3.5 text-sm" role="status">
      <p className="flex items-center gap-2">
        {sources ? (
          <span aria-hidden className="grid size-4 place-items-center rounded-full bg-success text-[0.6rem] text-white">
            ✓
          </span>
        ) : (
          <Spinner label="Searching" />
        )}
        {sources ? (
          <span>
            Found {sources.length} {sources.length === 1 ? "passage" : "passages"}
            {documents > 1 ? ` in ${documents} files` : ""}
            <span className="meta"> · page{pages.length === 1 ? "" : "s"} {pages.join(", ")}</span>
          </span>
        ) : (
          <span>Searching your notes…</span>
        )}
      </p>
      {sources && (
        <p className="flex items-center gap-2">
          <Spinner label="Writing" />
          <span>
            Writing your answer… <span className="meta">{seconds}s</span>
          </span>
        </p>
      )}
      {sources && seconds >= 15 && (
        <p className="text-xs text-ink-soft">
          The AI model is busy right now, so answers can take up to a minute. Yours is on its way: no
          need to ask again.
        </p>
      )}
    </div>
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
