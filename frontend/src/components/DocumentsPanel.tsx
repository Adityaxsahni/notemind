"use client";

import { type ChangeEvent, useEffect, useRef, useState } from "react";

import { deleteDocument, documentFileUrl, uploadDocument } from "@/lib/api";
import { useApiErrorHandler } from "@/lib/auth";
import type { NoteDocument } from "@/lib/types";

import { Alert, Button, Card, Chip, HatchTile, ProgressBar, Spinner } from "./ui";

// Mirrors the backend limits for instant feedback; the server still enforces them.
// Photos (and scanned PDFs) of handwritten notes are transcribed by the server.
const ACCEPTED = [".pdf", ".docx", ".pptx", ".jpg", ".jpeg", ".png", ".webp"];
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
        problems.push(`${file.name}: upload a PDF, DOCX, PPTX, or a photo (JPG, PNG, WebP).`);
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
        <div>
          <p className="label-mono">In this course</p>
          <h2 className="display text-3xl">Notes</h2>
        </div>
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
        <div className="rounded-xl border border-dashed border-faint p-4 text-sm text-ink-soft">
          {canEdit
            ? "PDF, Word or PowerPoint files, or photos of handwritten notes, up to 200 MB each."
            : "No notes in this collection yet."}
        </div>
      ) : (
        <ul className="divide-y divide-border">
          {documents.map((document) => (
            <li key={document.id} className="flex gap-3 py-3">
              <HatchTile className="size-12 shrink-0 rounded-lg" />
              <div className="min-w-0 flex-1 space-y-1.5">
                <div className="flex items-center justify-between gap-3">
                  <a
                    href={documentFileUrl(collectionId, document.id)}
                    className="display truncate text-xl hover:underline"
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
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="meta">
                      {document.kind === "image" ? "photo" : document.kind} · {document.page_count}{" "}
                      {document.kind === "pptx" ? "slides" : document.page_count === 1 ? "page" : "pages"} ·{" "}
                      {formatSize(document.size_bytes)}
                    </p>
                    {document.transcribed_pages > 0 && (
                      <Chip tone="tag" className="!py-0.5">
                        ✎ {document.transcribed_pages} transcribed
                      </Chip>
                    )}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function StatusBadge({ document }: { document: NoteDocument }) {
  const dots = { queued: "bg-faint", processing: "bg-amber", ready: "bg-success", failed: "bg-danger" };
  const labels = { queued: "queued", processing: "reading", ready: "ready", failed: "failed" };
  return (
    <span className="label-mono inline-flex items-center gap-1.5 !text-foreground">
      <span aria-hidden className={`size-1.5 rounded-full ${dots[document.status]}`} />
      {labels[document.status]}
    </span>
  );
}

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
