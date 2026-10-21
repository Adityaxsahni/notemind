// Fire-and-forget reports to our own backend: no third-party scripts, no cookies.

let errorsSent = 0;

export function reportError(error: { message?: string; stack?: string; digest?: string }): void {
  if (errorsSent >= 5) return; // a render loop must not flood the endpoint
  errorsSent += 1;
  void fetch("/telemetry/errors", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    keepalive: true,
    body: JSON.stringify({
      message: String(error.message ?? "Unknown error").slice(0, 2000),
      stack: error.stack?.slice(0, 8000),
      digest: error.digest,
      path: window.location.pathname,
    }),
  }).catch(() => undefined);
}

export function trackPageView(path: string): void {
  void fetch("/analytics/event", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    keepalive: true,
    body: JSON.stringify({ path, referrer: document.referrer || null }),
  }).catch(() => undefined);
}
