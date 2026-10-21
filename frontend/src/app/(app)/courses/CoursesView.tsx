"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useState } from "react";

import { Alert, Button, HatchTile, Input, Spinner } from "@/components/ui";
import { createCollection, listCollections } from "@/lib/api";
import { useApiErrorHandler } from "@/lib/auth";
import type { Collection } from "@/lib/types";

export function CoursesView() {
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

  const owned = collections?.filter((c) => c.role === "owner").length ?? 0;
  const shared = (collections?.length ?? 0) - owned;

  return (
    <div className="space-y-8">
      <div>
        <p className="eyebrow">Your library</p>
        <h1 className="display mt-2 text-5xl sm:text-6xl">
          Which course are you <em>revising</em>?
        </h1>
        <p className="meta mt-3">
          {collections === null ? "loading…" : `${owned} yours · ${shared} shared with you`}
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
        <p className="meta flex items-center gap-2">
          <Spinner /> loading your courses…
        </p>
      )}

      {collections?.length === 0 && (
        <div className="rounded-2xl border border-dashed border-faint p-8 text-center">
          <p className="display text-3xl">Nothing here yet.</p>
          <p className="mt-2 text-sm text-ink-soft">
            Create a collection above, then upload notes, slides or photos of handwritten pages.
          </p>
        </div>
      )}

      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {collections?.map((collection, i) => (
          <li key={collection.id}>
            <Link
              href={`/c/${collection.id}`}
              className={`card-lift group block overflow-hidden rounded-2xl bg-surface ${
                i === 0 ? "border-[1.5px] border-foreground" : "border border-border"
              }`}
            >
              <HatchTile
                caption={collection.role === "owner" ? "your notes" : "shared · read-only"}
                className="h-28"
              />
              <div className="flex items-end justify-between gap-3 p-4">
                <div className="min-w-0">
                  <p className="display truncate text-2xl">{collection.name}</p>
                  <p className="meta mt-0.5">
                    {collection.role === "owner" ? "owned by you" : "shared with you"} ·{" "}
                    {new Date(collection.created_at).toLocaleDateString()}
                  </p>
                </div>
                <span className="shrink-0 rounded-full bg-accent px-4 py-1.5 text-sm font-medium text-accent-foreground transition group-hover:bg-accent/90">
                  Enter
                </span>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
