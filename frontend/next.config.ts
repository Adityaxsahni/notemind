import type { NextConfig } from "next";

// The browser only ever talks to this origin. API paths are forwarded to FastAPI, so the
// backend's httpOnly, SameSite=Strict auth cookies stay first-party, no CORS is involved,
// and the refresh cookie's Path=/auth still matches. Rewrites are resolved at build time.
const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
const API_PREFIXES = ["auth", "me", "collections", "invites", "health", "analytics", "telemetry", "admin"];

const isDev = process.env.NODE_ENV === "development";
// Set FORCE_HTTPS=true when building for a deployment behind TLS. Not tied to NODE_ENV:
// `next build` is always "production", and local Docker serves plain http://localhost.
const forceHttps = process.env.FORCE_HTTPS === "true";
// Cloudflare Turnstile (CAPTCHA) needs its script and iframe, only when it's configured.
const captcha = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ? " https://challenges.cloudflare.com" : "";

// Answers and filenames are rendered as React text (never raw HTML); CSP is the backstop.
// TODO(T7): move to nonce-based script-src. Nonces need proxy.ts, which buffers request
// bodies (10 MB default), so raise proxyClientMaxBodySize above the upload limit first.
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}${captcha}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' blob: data:",
  "font-src 'self'",
  `connect-src 'self'${captcha}`,
  `frame-src${captcha || " 'none'"}`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  ...(forceHttps ? ["upgrade-insecure-requests"] : []),
].join("; ");

const httpsHeaders = forceHttps
  ? [{ key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" }]
  : [];

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  poweredByHeader: false,
  output: "standalone",
  compress: true, // gzip for pages and assets (the answer stream opts out with no-transform)
  images: { formats: ["image/avif", "image/webp"] },
  experimental: {
    // The rewrite proxy cuts request bodies at 10 MB by default. Let uploads through to the
    // backend, which enforces the real 200 MB limit while streaming.
    proxyClientMaxBodySize: "201mb",
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async redirects() {
    // Behind a TLS-terminating proxy, a request that arrived over plain HTTP is sent to HTTPS.
    if (!forceHttps) return [];
    return [
      {
        source: "/:path*",
        has: [{ type: "header", key: "x-forwarded-proto", value: "http" }],
        destination: `${process.env.NEXT_PUBLIC_SITE_URL ?? ""}/:path*`,
        permanent: true,
      },
    ];
  },
  async rewrites() {
    return API_PREFIXES.flatMap((prefix) => [
      { source: `/${prefix}`, destination: `${backendUrl}/${prefix}` },
      { source: `/${prefix}/:path*`, destination: `${backendUrl}/${prefix}/:path*` },
    ]);
  },
  async headers() {
    return [
      {
        // Pages only: proxied API responses keep the backend's own headers (e.g. the
        // `CSP: sandbox` on file downloads).
        source: `/((?!${API_PREFIXES.join("|")}).*)`,
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          ...httpsHeaders,
        ],
      },
    ];
  },
};

export default nextConfig;
