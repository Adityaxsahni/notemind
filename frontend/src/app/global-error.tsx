"use client";

import { useEffect } from "react";

import { reportError } from "@/lib/telemetry";

// Last resort when the root layout itself fails: no app styles are available here.
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => reportError(error), [error]);
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", textAlign: "center", padding: "4rem 1rem" }}>
        <h1>Something went wrong</h1>
        <p>We&apos;ve been notified. Please try again.</p>
        <button onClick={reset} style={{ padding: "0.6rem 1.4rem", marginTop: "1rem" }}>
          Try again
        </button>
      </body>
    </html>
  );
}
