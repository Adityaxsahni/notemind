"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useRef, useState, useSyncExternalStore } from "react";

import { ApiError, getFormToken, login, needsOtp, type OtpChallenge, signup } from "@/lib/api";
import { safeNext } from "@/lib/auth";
import { TURNSTILE_SITE_KEY } from "@/lib/site";
import { emailProblem, passwordProblem, passwordStrength } from "@/lib/validation";

import { Logo } from "./icons";
import { OtpStep } from "./OtpStep";
import { Alert, Button, Card, Input, Label, Spinner } from "./ui";

type Turnstile = {
  render: (el: HTMLElement, options: Record<string, unknown>) => string;
  reset: (id?: string) => void;
};

/** Cloudflare Turnstile, loaded only when a site key is configured. */
function useTurnstile(container: React.RefObject<HTMLDivElement | null>) {
  const [token, setToken] = useState<string | null>(null);
  const widget = useRef<string | null>(null);

  useEffect(() => {
    if (!TURNSTILE_SITE_KEY || !container.current) return;
    const el = container.current;
    const render = () => {
      const turnstile = (window as Window & { turnstile?: Turnstile }).turnstile;
      if (!turnstile || widget.current) return;
      widget.current = turnstile.render(el, {
        sitekey: TURNSTILE_SITE_KEY,
        callback: (t: string) => setToken(t),
        "expired-callback": () => setToken(null),
      });
    };
    if ((window as Window & { turnstile?: Turnstile }).turnstile) return render();
    const script = document.createElement("script");
    script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
    script.async = true;
    script.onload = render;
    document.head.appendChild(script);
  }, [container]);

  const reset = () => {
    setToken(null);
    (window as Window & { turnstile?: Turnstile }).turnstile?.reset(widget.current ?? undefined);
  };
  return { token, reset, required: Boolean(TURNSTILE_SITE_KEY) };
}

const STRENGTH = ["Too short", "Weak", "Fair", "Good", "Strong"];
// The backend refuses forms submitted faster than this after the token was issued (a bot
// signal). A password manager can fill and submit sooner, so wait out the rest instead.
const MIN_FILL_MS = 2200;
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const noSubscription = () => () => {};

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  // Read from the URL without useSearchParams, so the form is part of the static HTML (no
  // client-only render that would shift the page as it appears).
  const search = useSyncExternalStore(noSubscription, () => window.location.search, () => "");
  const next = safeNext(new URLSearchParams(search).get("next"));
  const isSignup = mode === "signup";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const [honeypot, setHoneypot] = useState("");
  const [touched, setTouched] = useState({ email: false, password: false });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const formToken = useRef<Promise<string | null> | null>(null);
  const tokenIssuedAt = useRef(0);
  const [challenge, setChallenge] = useState<OtpChallenge | null>(null);
  const captchaBox = useRef<HTMLDivElement>(null);
  const captcha = useTurnstile(captchaBox);

  useEffect(() => {
    // Fetched when the form appears: the backend checks how long ago that was.
    refreshFormToken();
  }, []);

  function refreshFormToken() {
    tokenIssuedAt.current = Date.now();
    formToken.current = getFormToken().catch(() => null);
  }

  const emailError = emailProblem(email);
  const passwordError = passwordProblem(password, email, isSignup);
  const strength = passwordStrength(password);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setTouched({ email: true, password: true });
    if (emailError || passwordError || (isSignup && !agreed)) return;
    if (captcha.required && !captcha.token) {
      setError("Please complete the check above.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const human = {
        form_token: await (formToken.current ?? Promise.resolve(null)),
        website: honeypot,
        captcha_token: captcha.token,
      };
      await sleep(Math.max(0, tokenIssuedAt.current + MIN_FILL_MS - Date.now()));
      const result = await (isSignup
        ? signup(email.trim(), password, human)
        : login(email.trim(), password, human));
      if (needsOtp(result)) {
        setChallenge(result);
        setBusy(false);
        return;
      }
      router.replace(next);
    } catch (err) {
      refreshFormToken(); // fresh token for the retry
      captcha.reset();
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

  if (challenge) {
    return (
      <OtpStep
        challenge={challenge}
        onVerified={() => router.replace(next)}
        onRestart={() => {
          setChallenge(null);
          setPassword("");
          refreshFormToken();
        }}
      />
    );
  }

  const otherHref = `${isSignup ? "/login" : "/signup"}${next !== "/courses" ? `?next=${encodeURIComponent(next)}` : ""}`;
  const showEmailError = touched.email && emailError;
  const showPasswordError = touched.password && passwordError;

  return (
    <div className="relative mx-auto max-w-md pt-6">
      <div className="relative">
        <div className="mb-6">
          <Logo className="mb-4 size-10" />
          <p className="eyebrow">{isSignup ? "New here" : "NoteMind"}</p>
          <h1 className="display mt-2 text-5xl">
            {isSignup ? (
              <>
                Start revising <em>smarter</em>.
              </>
            ) : (
              <>
                Welcome <em>back</em>.
              </>
            )}
          </h1>
          <p className="mt-2 text-sm text-ink-soft">
            {isSignup ? "Free account. Your notes stay private." : "Log in to your notes."}
          </p>
        </div>
        <Card className="border-[1.5px] border-foreground shadow-card">
          <form onSubmit={submit} noValidate className="space-y-4">
            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                inputMode="email"
                autoComplete="email"
                required
                maxLength={320}
                value={email}
                aria-invalid={Boolean(showEmailError)}
                aria-describedby={showEmailError ? "email-error" : undefined}
                onBlur={() => setTouched((t) => ({ ...t, email: true }))}
                onChange={(e) => setEmail(e.target.value)}
              />
              {showEmailError && (
                <p id="email-error" className="mt-1 text-xs text-danger">
                  {emailError}
                </p>
              )}
            </div>
            <div>
              <div className="flex items-center justify-between">
                <Label htmlFor="password">Password</Label>
                <button
                  type="button"
                  className="mb-1 text-xs font-medium text-accent hover:underline"
                  onClick={() => setShowPassword((s) => !s)}
                  aria-controls="password"
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete={isSignup ? "new-password" : "current-password"}
                required
                minLength={isSignup ? 10 : undefined}
                maxLength={128}
                value={password}
                aria-invalid={Boolean(showPasswordError)}
                aria-describedby={isSignup ? "password-help" : showPasswordError ? "password-error" : undefined}
                onBlur={() => setTouched((t) => ({ ...t, password: true }))}
                onChange={(e) => setPassword(e.target.value)}
              />
              {isSignup && (
                <div id="password-help" className="mt-2 space-y-1">
                  <div className="flex gap-1" aria-hidden>
                    {[0, 1, 2, 3].map((i) => (
                      <span
                        key={i}
                        className={`h-1 flex-1 rounded-full ${i < strength ? "bg-accent" : "bg-border"}`}
                      />
                    ))}
                  </div>
                  <p className="text-xs text-muted">
                    {password ? `${STRENGTH[strength]}. ` : ""}At least 10 characters; not a common password.
                  </p>
                </div>
              )}
              {showPasswordError && (
                <p id="password-error" className="mt-1 text-xs text-danger">
                  {passwordError}
                </p>
              )}
            </div>

            {/* Honeypot: hidden from people and screen readers; bots fill it in. */}
            <div aria-hidden className="absolute -left-[9999px] h-0 w-0 overflow-hidden">
              <label htmlFor="website">Website</label>
              <input
                id="website"
                name="website"
                tabIndex={-1}
                autoComplete="off"
                value={honeypot}
                onChange={(e) => setHoneypot(e.target.value)}
              />
            </div>

            {isSignup && (
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  required
                  checked={agreed}
                  onChange={(e) => setAgreed(e.target.checked)}
                  className="mt-0.5 size-4 accent-[var(--accent)]"
                  aria-invalid={touched.password && !agreed}
                />
                <span className="text-muted">
                  I agree to the{" "}
                  <Link href="/terms" className="font-medium text-accent hover:underline">
                    terms
                  </Link>{" "}
                  and the{" "}
                  <Link href="/privacy" className="font-medium text-accent hover:underline">
                    privacy policy
                  </Link>
                  .
                </span>
              </label>
            )}

            {captcha.required && <div ref={captchaBox} className="min-h-16" />}
            {error && <Alert>{error}</Alert>}
            <Button type="submit" disabled={busy || (isSignup && !agreed)} className="w-full rounded-full py-2.5">
              {busy && <Spinner />}
              {isSignup ? "Create free account" : "Log in"}
            </Button>
          </form>
        </Card>
        <p className="mt-4 text-center text-sm text-muted">
          {isSignup ? "Already have an account? " : "New here? "}
          <Link href={otherHref} className="font-medium text-accent hover:underline">
            {isSignup ? "Log in" : "Create a free account"}
          </Link>
        </p>
      </div>
    </div>
  );
}
