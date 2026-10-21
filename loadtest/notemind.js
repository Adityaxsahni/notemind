// Load test: a realistic mix of anonymous visitors and signed-in students, ramping up to
// PEAK_USERS concurrent users (default 10,000). Every request goes through the public entry
// point (the nginx edge), as a browser's would, and each virtual user has its own client IP,
// so per-IP rate limits behave as they would with real visitors. See docs/PERFORMANCE.md.
//
//   docker compose -f docker-compose.yml -f docker-compose.loadtest.yml run --rm k6
//
// Environment:
//   PEAK_USERS      concurrent users at the plateau (default 10000)
//   STUDENT_SHARE   fraction of them signed in (default 0.3); the rest browse public pages
//   PROFILE         "full" (~11 min ramp and hold) or "quick" (~2 min, used by CD)
//   SEARCH_SHARE    chance that a student's visit to a course includes a search (default 0.1)

import { check, sleep } from "k6";
import exec from "k6/execution";
import http from "k6/http";
import { Counter } from "k6/metrics";

const BASE = __ENV.BASE_URL || "http://edge:8080";
const PEAK = Number(__ENV.PEAK_USERS || 10000);
const STUDENT_SHARE = Number(__ENV.STUDENT_SHARE || 0.3);
const SEARCH_SHARE = Number(__ENV.SEARCH_SHARE || 0.1);
const PROFILE = __ENV.PROFILE || "full";
const PASSWORD = __ENV.LOADTEST_PASSWORD || "Load-test-password-2026"; // pragma: allowlist secret
const STUDENTS = Math.max(1, Math.round(PEAK * STUDENT_SHARE));

const rateLimited = new Counter("rate_limited");

// Ramp to 10%, 50%, then 100% of the target, hold, and ramp down.
function stages(target) {
  if (PROFILE === "quick") {
    return [
      { duration: "30s", target },
      { duration: "1m", target },
      { duration: "15s", target: 0 },
    ];
  }
  return [
    { duration: "1m", target: Math.round(target * 0.1) },
    { duration: "2m", target: Math.round(target * 0.5) },
    { duration: "2m", target },
    { duration: "5m", target },
    { duration: "1m", target: 0 },
  ];
}

export const options = {
  discardResponseBodies: true, // bodies we need are requested with responseType: "text"
  scenarios: {
    visitors: {
      executor: "ramping-vus",
      exec: "visitor",
      stages: stages(PEAK - STUDENTS),
      gracefulRampDown: "10s",
    },
    students: {
      executor: "ramping-vus",
      exec: "student",
      stages: stages(STUDENTS),
      gracefulRampDown: "10s",
    },
  },
  // Service-level objectives. The run "passes" only if all of them hold at peak traffic.
  thresholds: {
    http_req_failed: ["rate<0.01"],
    checks: ["rate>0.99"],
    "http_req_duration{kind:page}": ["p(95)<800"],
    "http_req_duration{kind:api}": ["p(95)<800"],
    "http_req_duration{kind:login}": ["p(95)<3000"],
    "http_req_duration{kind:search}": ["p(95)<3000"],
  },
  summaryTrendStats: ["avg", "med", "p(90)", "p(95)", "p(99)", "max"],
};

const PAGES = ["/", "/", "/", "/features", "/features", "/privacy", "/terms", "/signup", "/login"];
const QUESTIONS = [
  "How do mitochondria make ATP?",
  "What is the difference between mitosis and meiosis?",
  "What does the Golgi apparatus do?",
  "Explain osmosis",
  "How does the sodium potassium pump work?",
  "What happens in the Calvin cycle?",
  "How do competitive inhibitors affect enzymes?",
  "What are cell cycle checkpoints?",
];

const pick = (items) => items[Math.floor(Math.random() * items.length)];
const think = (min, max) => sleep(min + Math.random() * (max - min));

// A distinct private address per virtual user (10.0.0.1 … 10.0.39.16 for 10,000 users).
function clientIp() {
  const id = exec.vu.idInTest;
  return `10.${(id >> 16) & 255}.${(id >> 8) & 255}.${id & 255}`;
}

function params(kind, name, extra = {}) {
  const headers = { "X-Forwarded-For": clientIp(), ...(extra.headers || {}) };
  return { ...extra, headers, tags: { kind, name } };
}

function record(res, label, expected = 200) {
  if (res.status === 429) rateLimited.add(1);
  return check(res, { [`${label} ${expected}`]: (r) => r.status === expected });
}

// First visit per user: also fetch the page's JS and CSS, as a browser with a cold cache
// does. Later views hit the browser cache, so they fetch the HTML only.
const loadedAssets = {};
function view(path) {
  const cold = !loadedAssets[path];
  const res = http.get(
    `${BASE}${path}`,
    params("page", path, cold ? { responseType: "text" } : {}),
  );
  record(res, `page ${path}`);
  if (cold && res.body) {
    loadedAssets[path] = true;
    const assets = [...new Set(res.body.match(/\/_next\/static\/[^"'\s)\\]+/g) || [])];
    if (assets.length) {
      // One after another on the user's one connection: a browser would open up to six, but
      // here that would multiply the generator's memory by six at 10,000 users.
      for (const asset of assets) {
        record(http.get(`${BASE}${asset}`, params("asset", "static asset")), "static asset");
      }
    }
  }
  return res;
}

export function visitor() {
  const path = pick(PAGES);
  view(path);
  if (Math.random() < 0.4) {
    // Consented visitors send one cookieless page-view event.
    const res = http.post(
      `${BASE}/analytics/event`,
      JSON.stringify({ path, referrer: "" }),
      params("api", "analytics event", { headers: { "Content-Type": "application/json" } }),
    );
    record(res, "analytics event", 204);
  }
  if (path === "/signup" || path === "/login") {
    record(http.get(`${BASE}/auth/form-token`, params("api", "form token")), "form token");
  }
  think(3, 8);
}

// Per-VU session: the access cookie, re-obtained when it expires (15 minutes).
let session = null;

function signIn() {
  view("/login");
  const token = http.get(
    `${BASE}/auth/form-token`,
    params("api", "form token", { responseType: "text" }),
  );
  if (!record(token, "form token")) return null;
  think(2.5, 4); // typing; also the minimum fill time the bot check enforces
  const email = `student${(exec.vu.idInTest - 1) % STUDENTS}@loadtest.example.com`;
  const res = http.post(
    `${BASE}/auth/login`,
    JSON.stringify({ email, password: PASSWORD, form_token: token.json("token"), website: "" }),
    params("login", "login", { headers: { "Content-Type": "application/json" } }),
  );
  if (!record(res, "login")) return null;
  // The auth cookies are Secure; browsers send them to http://localhost but k6 doesn't, so
  // pass the access cookie explicitly.
  const access = res.cookies.access_token && res.cookies.access_token[0];
  return access ? { cookie: `access_token=${access.value}`, course: null } : null;
}

function api(method, path, name, body = null, kind = "api", extra = {}) {
  const headers = { Cookie: session.cookie };
  if (body !== null) headers["Content-Type"] = "application/json";
  const res = http.request(
    method,
    `${BASE}${path}`,
    body === null ? null : JSON.stringify(body),
    params(kind, name, { ...extra, headers }),
  );
  if (res.status === 401) session = null; // expired: sign in again next iteration
  record(res, name);
  return res;
}

export function student() {
  if (session === null) {
    session = signIn();
    if (session === null) {
      think(5, 10);
      return;
    }
  }

  view("/courses");
  api("GET", "/me", "me");
  const list = api("GET", "/collections", "list courses", null, "api", { responseType: "text" });
  if (session === null) return;
  if (!session.course && list.status === 200) {
    const courses = list.json();
    session.course = courses.length ? courses[0].id : null;
  }
  think(2, 6);

  if (session.course) {
    const id = session.course;
    view(`/c/${id}`);
    api("GET", `/collections/${id}`, "get course");
    api("GET", `/collections/${id}/documents`, "list documents");
    if (session && Math.random() < SEARCH_SHARE) {
      think(3, 6); // typing the question
      api("POST", `/collections/${id}/search`, "search", { query: pick(QUESTIONS) }, "search");
    }
  }
  think(5, 15);
}
