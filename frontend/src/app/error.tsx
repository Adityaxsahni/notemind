"use client";

import Link from "next/link";
import { useEffect } from "react";

import { reportError } from "@/lib/telemetry";

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => reportError(error), [error]);

  return (
    <div className="mx-auto flex max-w-xl flex-col items-center px-4 py-24 text-center">
      <h1 className="display text-5xl">Something went <em>wrong</em>.</h1>
      <p className="mt-3 text-muted">
        We&apos;ve been notified. Try again, and if it keeps happening, come back in a few minutes.
      </p>
      {error.digest && <p className="mt-2 text-xs text-muted">Reference: {error.digest}</p>}
      <div className="mt-8 flex gap-3">
        <button onClick={reset} className="rounded-full bg-foreground px-6 py-3 font-medium text-background hover:bg-foreground/85">
          Try again
        </button>
        <Link href="/" className="rounded-full border border-foreground/25 px-6 py-3 font-medium hover:border-foreground">
          Home
        </Link>
      </div>
    </div>
  );
}
