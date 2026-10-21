// Fails if anything secret-looking reached the JavaScript sent to browsers.
// Run after `next build` (CI does). Only NEXT_PUBLIC_* values may be inlined into the bundle,
// and none of those are secrets; this catches mistakes like importing a server env var.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const ROOT = ".next/static";
const FORBIDDEN = [
  // Server-only configuration names (backend/.env.example).
  /\b(SECRET_KEY|LLM_API_KEY|POSTGRES_PASSWORD|DATABASE_URL|REDIS_URL|TURNSTILE_SECRET_KEY|BACKEND_URL)\b/,
  // Key formats: Anthropic, Google, AWS, private keys, generic bearer tokens.
  /sk-ant-[A-Za-z0-9_-]{10,}/,
  /AIza[0-9A-Za-z_-]{30,}/,
  /\bAQ\.[A-Za-z0-9_-]{30,}/,
  /AKIA[0-9A-Z]{16}/,
  /-----BEGIN [A-Z ]*PRIVATE KEY-----/,
  /postgres(ql)?(\+\w+)?:\/\/[^\s"']+:[^\s"']+@/,
];

function* files(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) yield* files(path);
    else if (/\.(js|css|json|html|txt)$/.test(name)) yield path;
  }
}

const problems = [];
let scanned = 0;
for (const file of files(ROOT)) {
  scanned++;
  const text = readFileSync(file, "utf8");
  for (const pattern of FORBIDDEN) {
    const match = text.match(pattern);
    if (match) problems.push(`${file}: ${match[0].slice(0, 40)}…`);
  }
}

if (scanned === 0) {
  console.error(`No files under ${ROOT}: run \`next build\` first.`);
  process.exit(2);
}
if (problems.length) {
  console.error("Possible secrets in the browser bundle:\n" + problems.join("\n"));
  process.exit(1);
}
console.log(`Client bundle clean: ${scanned} files scanned, no secrets found.`);
