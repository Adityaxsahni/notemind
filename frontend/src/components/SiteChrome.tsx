"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";

import {
  type Consent,
  OPEN_SETTINGS_EVENT,
  readConsent,
  saveConsent,
  subscribeConsent,
  trackingBlocked,
} from "@/lib/consent";
import { reportError, trackPageView } from "@/lib/telemetry";

/** Page-view analytics, only after the visitor opted in (and never with Do Not Track). */
export function Analytics() {
  const pathname = usePathname();
  const consent = useSyncExternalStore(subscribeConsent, readConsent, () => null);

  useEffect(() => {
    if (consent === "accepted" && !trackingBlocked()) trackPageView(pathname);
  }, [consent, pathname]);

  return null;
}

/** Sends uncaught browser errors to /telemetry/errors (render errors go via error.tsx). */
export function ErrorReporter() {
  useEffect(() => {
    const onError = (event: ErrorEvent) => reportError(event.error ?? { message: event.message });
    const onRejection = (event: PromiseRejectionEvent) =>
      reportError(event.reason instanceof Error ? event.reason : { message: String(event.reason) });
    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onRejection);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onRejection);
    };
  }, []);
  return null;
}

export function CookieBanner() {
  // "unset" on the server and before hydration, so the banner never flashes for people who
  // already chose.
  const consent = useSyncExternalStore(subscribeConsent, readConsent, () => "unset" as const);
  const [reopened, setReopened] = useState(false);

  useEffect(() => {
    const reopen = () => setReopened(true);
    window.addEventListener(OPEN_SETTINGS_EVENT, reopen);
    return () => window.removeEventListener(OPEN_SETTINGS_EVENT, reopen);
  }, []);

  if (consent !== null && !reopened) return null;

  function choose(value: Consent) {
    saveConsent(value);
    setReopened(false);
  }

  return (
    <div
      role="dialog"
      aria-modal="false"
      aria-labelledby="cookie-title"
      className="animate-rise fixed inset-x-3 bottom-3 z-50 mx-auto max-w-2xl rounded-2xl border border-border bg-surface p-4 shadow-card-lg sm:inset-x-6 sm:p-5"
    >
      <h2 id="cookie-title" className="display text-2xl">
        Cookies and privacy
      </h2>
      <p className="mt-1 text-xs leading-relaxed text-muted sm:text-sm">
        We use a few essential cookies to keep you signed in. With your permission we also count
        anonymous page views (no cookies, no personal data) to see which pages help. Read the{" "}
        <Link href="/privacy#cookies" className="font-medium text-accent underline-offset-2 hover:underline">
          privacy policy
        </Link>
        .
      </p>
      <div className="mt-3 grid grid-cols-2 gap-2 sm:flex sm:justify-end">
        <button
          type="button"
          onClick={() => choose("essential")}
          className="rounded-full border border-border px-5 py-2 text-sm font-medium hover:bg-background"
        >
          Essential only
        </button>
        <button
          type="button"
          onClick={() => choose("accepted")}
          className="rounded-full bg-foreground px-5 py-2 text-sm font-medium text-background hover:bg-foreground/85"
        >
          Accept analytics
        </button>
      </div>
    </div>
  );
}

export function CookieSettingsButton({ className = "" }: { className?: string }) {
  return (
    <button
      type="button"
      className={className}
      onClick={() => window.dispatchEvent(new Event(OPEN_SETTINGS_EVENT))}
    >
      Cookie settings
    </button>
  );
}
