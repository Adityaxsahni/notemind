"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";

import { Alert, Button, Card, Input, Label, Spinner } from "@/components/ui";
import { deleteAccount, exportData, getMe } from "@/lib/api";
import { useApiErrorHandler } from "@/lib/auth";
import type { User } from "@/lib/types";

export function AccountView() {
  const router = useRouter();
  const handleError = useApiErrorHandler();
  const [user, setUser] = useState<User | null>(null);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getMe()
      .then(setUser)
      .catch((err) => setError(handleError(err)));
  }, [handleError]);

  async function download() {
    try {
      const data = await exportData();
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = "notemind-export.json";
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(handleError(err));
    }
  }

  async function remove(event: FormEvent) {
    event.preventDefault();
    if (!window.confirm("Delete your account, all collections and all uploaded files? This can't be undone.")) return;
    setBusy(true);
    setError(null);
    try {
      await deleteAccount(password);
      router.replace("/signup");
    } catch (err) {
      setError(handleError(err));
      setBusy(false);
    }
  }

  if (!user) {
    return error ? <Alert>{error}</Alert> : <Spinner />;
  }

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div>
        <h1 className="display text-5xl">Account</h1>
        <p className="text-sm text-muted">
          {user.email} · member since {new Date(user.created_at).toLocaleDateString()}
        </p>
      </div>
      {error && <Alert>{error}</Alert>}
      <Card className="space-y-3">
        <h2 className="display text-3xl">Your data</h2>
        <p className="text-sm text-muted">Download everything NoteMind stores about you as JSON.</p>
        <Button variant="secondary" onClick={download}>
          Export my data
        </Button>
      </Card>
      <Card className="space-y-3">
        <h2 className="display text-3xl text-danger">Delete account</h2>
        <p className="text-sm text-muted">
          Permanently deletes your account, collections, uploaded files and search index.
        </p>
        <form onSubmit={remove} className="space-y-3">
          <div>
            <Label htmlFor="confirm-password">Confirm with your password</Label>
            <Input
              id="confirm-password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <Button type="submit" variant="danger" disabled={busy || !password}>
            {busy && <Spinner />}
            Delete my account
          </Button>
        </form>
      </Card>
    </div>
  );
}
