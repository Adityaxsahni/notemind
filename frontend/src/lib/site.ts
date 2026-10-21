// Public site settings. NEXT_PUBLIC_* values are inlined into the browser bundle at build
// time, so only non-secret configuration may live here (see docs/SECURITY.md).

export const SITE_NAME = "NoteMind";
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000").replace(/\/$/, "");
export const SITE_DESCRIPTION =
  "Upload your course notes and ask questions. NoteMind answers only from your own material, with a page citation for every claim, and turns your notes into quizzes.";
export const CONTACT_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL ?? "privacy@notemind.example";
export const REPO_URL = "https://github.com/Adityaxsahni/notemind";
// Cloudflare Turnstile site key: public by design (the secret stays on the backend).
export const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? "";
export const LEGAL_UPDATED = "21 October 2026";
