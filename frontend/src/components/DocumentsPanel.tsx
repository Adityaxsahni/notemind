"use client";

import { type ChangeEvent, useEffect, useRef, useState } from "react";

import { deleteDocument, documentFileUrl, uploadDocument } from "@/lib/api";
import { useApiErrorHandler } from "@/lib/auth";
import type { NoteDocument } from "@/lib/types";

import { Alert, Button, Card, ProgressBar, Spinner } from "./ui";

// Mirrors the backend limits for instant feedback; the server still enforces them.
const ACCEPTED = [".pdf", ".docx", ".pptx"];
const MAX_BYTES = 200 * 1024 * 1024;

export function DocumentsPanel({
  collectionId,
  canEdit,
  documents,
  onChange,
}: {
  collectionId: string;
  canEdit: boolean;
  documents: NoteDocument[];
  onChange: () => Promise<void>;
}) {
  const handleError = useApiErrorHandler();
  const fileInput = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState<string | null>(null);
  const [errors, setErrors] = useState<string[]>([]);

  // Poll while anything is still being processed by the workers.
  const pending = documents.some((d) => d.status === "queued" || d.status === "processing");
  useEffect(() => {
    if (!pending) return;
    const timer = setInterval(() => void onChange(), 1500);
    return () => clearInterval(timer);
  }, [pending, onChange]);

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    const problems: string[] = [];
    for (const file of files) {
      const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
      if (!ACCEPTED.includes(extension)) {
        problems.push(`${file.name}: only PDF, DOCX and PPTX files are supported.`);
        continue;
      }
      if (file.size > MAX_BYTES) {
        problems.push(`${file.name}: files can be at most 200 MB.`);
        continue;
      }
      setUploading(file.name);
      try {
        await uploadDocument(collectionId, file);
        await onChange();
      } catch (err) {
        const message = handleError(err);
        if (message) problems.push(`${file.name}: ${message}`);
      }
    }
    setUploading(null);
    setErrors(problems);
  }

  async function remove(document: NoteDocument) {
    if (!window.confirm(`Delete "${document.filename}"? Its pages are removed from search too.`)) return;
    try {
      await deleteDocument(collectionId, document.id);
      await onChange();
    } catch (err) {
      const message = handleError(err);
      if (message) setErrors([message]);
    }
  }

  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">Notes</h2>
        {canEdit && (
          <>
            <input
              ref={fileInput}
              type="file"
              accept={ACCEPTED.join(",")}
              multiple
              hidden
              onChange={upload}
            />
            <Button variant="secondary" onClick={() => fileInput.current?.click()} disabled={uploading !== null}>
              {uploading ? <Spinner label="Uploading" /> : null}
              {uploading ? "Uploading…" : "Upload"}
            </Button>
          </>
        )}
      </div>

      {errors.map((message) => (
        <Alert key={message}>{message}</Alert>
      ))}

      {documents.length === 0 ? (
        <p className="text-sm text-muted">
          {canEdit ? "PDF, Word or PowerPoint files, up to 200 MB each." : "No notes in this collection yet."}
        </p>
      ) : (
        <ul className="divide-y divide-border">
          {documents.map((document) => (
            <li key={document.id} className="space-y-1.5 py-3">
              <div className="flex items-center justify-between gap-3">
                <a
                  href={documentFileUrl(collectionId, document.id)}
                  className="truncate text-sm font-medium hover:underline"
                  title={`Download ${document.filename}`}
                >
                  {document.filename}
                </a>
                <div className="flex shrink-0 items-center gap-3">
                  <StatusBadge document={document} />
                  {canEdit && (
                    <button
                      onClick={() => remove(document)}
                      className="text-xs text-muted hover:text-danger"
                      aria-label={`Delete ${document.filename}`}
                    >
                      Delete
                    </button>
                  )}
                </div>
              </div>
              {(document.status === "queued" || document.status === "processing") && (
                <ProgressBar value={document.progress} />
              )}
              {document.status === "failed" && document.error && (
                <p className="text-xs text-danger">{document.error}</p>
              )}
              {document.status === "ready" && (
                <p className="text-xs text-muted">
                  {document.kind.toUpperCase()} · {document.page_count} {document.kind === "pptx" ? "slides" : "pages"} ·{" "}
                  {formatSize(document.size_bytes)}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function StatusBadge({ document }: { document: NoteDocument }) {
  const styles = {
    queued: "text-muted",
    processing: "text-accent",
    ready: "text-success",
    failed: "text-danger",
  };
  const labels = { queued: "Queued", processing: "Processing", ready: "Ready", failed: "Failed" };
  return <span className={`text-xs font-medium ${styles[document.status]}`}>{labels[document.status]}</span>;
}

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
