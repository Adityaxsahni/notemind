import { type NextRequest, NextResponse } from "next/server";

// On Vercel, API requests reach the backend from Vercel's servers, whose addresses change. The
// backend can't trust X-Forwarded-For by address, so this proxy sends a shared secret with
// each API request; the backend then believes Vercel's x-real-ip header for rate limiting
// (backend/app/trusted_proxy.py). PROXY_SECRET is server-only, never sent to browsers.
// Unset (Docker), this does nothing: there the proxies have fixed addresses instead.
const secret = process.env.PROXY_SECRET;

export function proxy(request: NextRequest) {
  if (!secret) return NextResponse.next();
  const headers = new Headers(request.headers);
  headers.set("x-notemind-proxy", secret);
  return NextResponse.next({ request: { headers } });
}

export const config = {
  matcher: [
    "/(auth|me|collections|invites|health|analytics|telemetry|admin)",
    "/(auth|me|collections|invites|health|analytics|telemetry|admin)/:path*",
  ],
};
