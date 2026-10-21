"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useState } from "react";

import { Alert, Button, Card, Input, Spinner } from "@/components/ui";
import { createCollection, listCollections } from "@/lib/api";
import { useApiErrorHandler } from "@/lib/auth";
import type { Collection } from "@/lib/types";

export default function CollectionsPage() {
  const handleError = useApiErrorHandler();
  const [collections, setCollections] = useState<Collection[] | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    listCollections()
      .then(setCollections)
      .catch((err) => setError(handleError(err)));
  }, [handleError]);

  async function create(event: FormEvent) {
    event.preventDefault();
    setCreating(true);
    setError(null);
    try {
      const collection = await createCollection(name.trim());
      setCollections((current) => [collection, ...(current ?? [])]);
      setName("");
    } catch (err) {
      setError(handleError(err));
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Your courses</h1>
        <p className="text-sm text-muted">
          One collection per course. Upload notes and slides, then ask questions about them.
        </p>
      </div>

      <form onSubmit={create} className="flex gap-2">
        <Input
          aria-label="New collection name"
          placeholder="e.g. DBMS — Semester 5"
          maxLength={120}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Button type="submit" disabled={creating || !name.trim()} className="shrink-0">
          {creating && <Spinner />}
          New collection
        </Button>
      </form>

      {error && <Alert>{error}</Alert>}

      {collections === null && !error && (
        <p className="flex items-center gap-2 text-sm text-muted">
          <Spinner /> Loading…
        </p>
      )}

      {collections?.length === 0 && (
        <Card className="text-center text-sm text-muted">
          No collections yet. Create one above to upload your first notes.
        </Card>
      )}

      <ul className="grid gap-3 sm:grid-cols-2">
        {collections?.map((collection) => (
          <li key={collection.id}>
            <Link
              href={`/c/${collection.id}`}
              className="block rounded-xl border border-border bg-surface p-4 transition hover:border-accent"
            >
              <div className="font-medium">{collection.name}</div>
              <div className="mt-1 text-xs text-muted">
                {collection.role === "owner" ? "Owned by you" : "Shared with you · read-only"} ·{" "}
                {new Date(collection.created_at).toLocaleDateString()}
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
