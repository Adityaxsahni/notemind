"use client";

import { type FormEvent, useEffect, useRef, useState } from "react";

import { ApiError, type OtpChallenge, resendOtp, verifyOtp } from "@/lib/api";

import { Alert, Button, Card, Spinner } from "./ui";

const RESEND_AFTER_SECONDS = 30;

/** Step two of signing in: the 6-digit code from the email. */
export function OtpStep({
  challenge: initial,
  onVerified,
  onRestart,
}: {
  challenge: OtpChallenge;
  onVerified: () => void;
  onRestart: () => void;
}) {
  const [challenge, setChallenge] = useState(initial);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [wait, setWait] = useState(RESEND_AFTER_SECONDS);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => input.current?.focus(), []);
  useEffect(() => {
    if (wait <= 0) return;
    const timer = setTimeout(() => setWait((w) => w - 1), 1000);
    return () => clearTimeout(timer);
  }, [wait]);

  async function submit(value: string, event?: FormEvent) {
    event?.preventDefault();
    if (!/^\d{6}$/.test(value)) {
      setError("Enter the 6 digits from the email.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await verifyOtp(challenge.challenge_id, value);
      onVerified();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't reach NoteMind. Check your connection.");
      setCode("");
      setBusy(false);
      input.current?.focus();
    }
  }

  async function resend() {
    setError(null);
    try {
      setChallenge(await resendOtp(challenge.challenge_id));
      setNotice("A new code is on its way. The previous one no longer works.");
      setWait(RESEND_AFTER_SECONDS);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't reach NoteMind. Check your connection.");
    }
  }

  return (
    <div className="mx-auto max-w-md pt-6">
      <p className="eyebrow">Step 2 of 2 · one-time code</p>
      <h1 className="display mt-2 text-5xl">
        Check your <em>inbox</em>.
      </h1>
      <p className="mt-2 text-sm text-ink-soft">
        We sent a 6-digit code to <span className="font-mono text-foreground">{challenge.email_hint}</span>. It
        expires in {Math.round(challenge.expires_in / 60)} minutes.
      </p>

      <Card className="mt-6 border-[1.5px] border-foreground shadow-card">
        <form onSubmit={(e) => submit(code, e)} noValidate className="space-y-4">
          <div>
            <label htmlFor="otp" className="label-mono mb-1.5 block">
              Sign-in code
            </label>
            <input
              ref={input}
              id="otp"
              name="otp"
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="\d{6}"
              maxLength={6}
              value={code}
              aria-invalid={Boolean(error)}
              aria-describedby={error ? "otp-error" : undefined}
              onChange={(e) => {
                const digits = e.target.value.replace(/\D/g, "").slice(0, 6);
                setCode(digits);
                if (digits.length === 6) void submit(digits); // pasted or typed in full
              }}
              className="w-full rounded-xl border border-border bg-surface px-4 py-3 text-center font-mono text-3xl tracking-[0.5em] outline-none focus:border-foreground focus:ring-2 focus:ring-foreground/10"
            />
          </div>

          {challenge.dev_code && (
            <Alert tone="info">
              Development mode: no mail server is configured, so the code is shown here instead:{" "}
              <button
                type="button"
                className="font-mono font-semibold underline underline-offset-2"
                onClick={() => {
                  setCode(challenge.dev_code!);
                  void submit(challenge.dev_code!);
                }}
              >
                {challenge.dev_code}
              </button>
            </Alert>
          )}
          {notice && !error && <Alert tone="info">{notice}</Alert>}
          {error && (
            <div id="otp-error">
              <Alert>{error}</Alert>
            </div>
          )}

          <Button type="submit" disabled={busy || code.length !== 6} className="w-full py-2.5">
            {busy && <Spinner />}
            Verify and continue
          </Button>
        </form>
      </Card>

      <div className="mt-4 flex items-center justify-between text-sm">
        <button type="button" onClick={onRestart} className="text-muted hover:text-foreground">
          ‹ Use a different account
        </button>
        <button
          type="button"
          onClick={resend}
          disabled={wait > 0}
          className="font-medium text-accent hover:underline disabled:cursor-not-allowed disabled:text-muted disabled:no-underline"
        >
          {wait > 0 ? `Resend code in ${wait}s` : "Resend code"}
        </button>
      </div>
    </div>
  );
}
