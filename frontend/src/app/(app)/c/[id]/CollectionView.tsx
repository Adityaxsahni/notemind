"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { AskPanel } from "@/components/AskPanel";
import { DocumentsPanel } from "@/components/DocumentsPanel";
import { QuizPanel } from "@/components/QuizPanel";
import { SharePanel } from "@/components/SharePanel";
import { Alert, Button, Spinner } from "@/components/ui";
import { ApiError, deleteCollection, getCollection, listDocuments } from "@/lib/api";
import { useApiErrorHandler } from "@/lib/auth";
import type { Collection, NoteDocument } from "@/lib/types";

export function CollectionView() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const handleError = useApiErrorHandler();
  const [collection, setCollection] = useState<Collection | null>(null);
  const [documents, setDocuments] = useState<NoteDocument[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refreshDocuments = useCallback(async () => {
    try {
      setDocuments(await listDocuments(id));
    } catch (err) {
      setError(handleError(err));
    }
  }, [id, handleError]);

  useEffect(() => {
    getCollection(id)
      .then((c) => {
        setCollection(c);
        return refreshDocuments();
      })
      .catch((err) => {
        // The API answers 404 for collections that don't exist *and* ones you can't see.
        setError(err instanceof ApiError && err.status === 404 ? "This collection doesn't exist or isn't shared with you." : handleError(err));
      });
  }, [id, refreshDocuments, handleError]);

  async function remove() {
    if (!collection || !window.confirm(`Delete "${collection.name}" and all its notes? This can't be undone.`)) return;
    try {
      await deleteCollection(collection.id);
      router.replace("/courses");
    } catch (err) {
      setError(handleError(err));
    }
  }

  if (error && !collection) {
    return (
      <div className="space-y-4">
        <Alert>{error}</Alert>
        <Link href="/courses" className="text-sm text-accent hover:underline">
          ← Back to your courses
        </Link>
      </div>
    );
  }
  if (!collection) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted">
        <Spinner /> Loading…
      </p>
    );
  }

  const isOwner = collection.role === "owner";
  const hasReadyDocuments = documents.some((d) => d.status === "ready");

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link
            href="/courses"
            aria-label="Back to your courses"
            className="grid size-9 place-items-center rounded-full border border-foreground/25 bg-surface text-sm hover:border-foreground"
          >
            ‹
          </Link>
          <p className="eyebrow mt-4">{isOwner ? "Your course" : "Shared with you · read-only"}</p>
          <h1 className="display mt-1 text-5xl">{collection.name}</h1>
          <p className="meta mt-2">
            {documents.length} {documents.length === 1 ? "file" : "files"} ·{" "}
            {documents.reduce((n, d) => n + (d.page_count ?? 0), 0)} pages
            {documents.some((d) => d.transcribed_pages > 0) &&
              ` · ${documents.reduce((n, d) => n + d.transcribed_pages, 0)} handwritten`}
          </p>
        </div>
        {isOwner && (
          <Button variant="danger" onClick={remove}>
            Delete collection
          </Button>
        )}
      </div>
      {error && <Alert>{error}</Alert>}
      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <div className="space-y-6">
          <AskPanel collectionId={collection.id} hasReadyDocuments={hasReadyDocuments} />
          <QuizPanel collectionId={collection.id} hasReadyDocuments={hasReadyDocuments} />
        </div>
        <div className="space-y-6">
          <DocumentsPanel
            collectionId={collection.id}
            canEdit={isOwner}
            documents={documents}
            onChange={refreshDocuments}
          />
          {isOwner && <SharePanel collectionId={collection.id} />}
        </div>
      </div>
    </div>
  );
}
