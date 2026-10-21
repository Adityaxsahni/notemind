"use client";

import { useState } from "react";

import { createInvite } from "@/lib/api";
import { useApiErrorHandler } from "@/lib/auth";

import { Alert, Button, Card, Input } from "./ui";

export function SharePanel({ collectionId }: { collectionId: string }) {
  const handleError = useApiErrorHandler();
  const [link, setLink] = useState<string | null>(null);
  const [expires, setExpires] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function create() {
    setError(null);
    try {
      const invite = await createInvite(collectionId);
      // The token is shown once (only its hash is stored), so this is the only chance to copy it.
      setLink(`${window.location.origin}/join?token=${encodeURIComponent(invite.token)}`);
      setExpires(new Date(invite.expires_at).toLocaleDateString());
      setCopied(false);
    } catch (err) {
      setError(handleError(err));
    }
  }

  async function copy() {
    if (!link) return;
    await navigator.clipboard.writeText(link);
    setCopied(true);
  }

  return (
    <Card className="space-y-3">
      <h2 className="display text-3xl">Share with classmates</h2>
      <p className="text-sm text-muted">
        Anyone with the link can read these notes and ask questions. They can&apos;t upload or delete.
      </p>
      {error && <Alert>{error}</Alert>}
      {link ? (
        <div className="space-y-2">
          <div className="flex gap-2">
            <Input readOnly value={link} aria-label="Invite link" onFocus={(e) => e.target.select()} />
            <Button variant="secondary" onClick={copy} className="shrink-0">
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
          <p className="text-xs text-muted">Expires {expires}. Copy it now; it won&apos;t be shown again.</p>
        </div>
      ) : (
        <Button variant="secondary" onClick={create}>
          Create invite link
        </Button>
      )}
    </Card>
  );
}
