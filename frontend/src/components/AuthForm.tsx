"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, useState } from "react";

import { ApiError, login, signup } from "@/lib/api";
import { safeNext } from "@/lib/auth";

import { Alert, Button, Card, Input, Label, Spinner } from "./ui";

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const isSignup = mode === "signup";

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await (isSignup ? signup(email, password) : login(email, password));
      router.replace(next);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 429
            ? "Too many attempts. Wait a minute and try again."
            : err.message
          : "Couldn't reach NoteMind. Check your connection.",
      );
      setBusy(false);
    }
  }

  const otherHref = `${isSignup ? "/login" : "/signup"}${next !== "/" ? `?next=${encodeURIComponent(next)}` : ""}`;

  return (
    <div className="mx-auto max-w-sm pt-8">
      <h1 className="mb-1 text-2xl font-semibold">{isSignup ? "Create your account" : "Welcome back"}</h1>
      <p className="mb-6 text-sm text-muted">
        {isSignup
          ? "Upload your notes and ask questions with page-level citations."
          : "Sign in to your notes."}
      </p>
      <Card>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete={isSignup ? "new-password" : "current-password"}
              required
              minLength={isSignup ? 10 : undefined}
              maxLength={128}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            {isSignup && (
              <p className="mt-1 text-xs text-muted">At least 10 characters, not a common password.</p>
            )}
          </div>
          {error && <Alert>{error}</Alert>}
          <Button type="submit" disabled={busy} className="w-full">
            {busy && <Spinner />}
            {isSignup ? "Create account" : "Sign in"}
          </Button>
        </form>
      </Card>
      <p className="mt-4 text-center text-sm text-muted">
        {isSignup ? "Already have an account? " : "New here? "}
        <Link href={otherHref} className="font-medium text-accent hover:underline">
          {isSignup ? "Sign in" : "Create an account"}
        </Link>
      </p>
    </div>
  );
}
