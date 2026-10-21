import { type Page, type Request, test as base } from "@playwright/test";

const API = /\/(auth|me|collections|invites|analytics|telemetry|admin)(\/|\?|$)/;

/** Mocks the backend API and records what the browser sent, so tests can assert on it. */
export class Api {
  readonly requests: Request[] = [];
  constructor(private page: Page) {}

  async install() {
    await this.page.route(API, async (route) => {
      const request = route.request();
      this.requests.push(request);
      const path = new URL(request.url()).pathname;
      const reply = (status: number, body?: unknown) =>
        route.fulfill({
          status,
          contentType: "application/json",
          body: body === undefined ? "" : JSON.stringify(body),
        });

      if (path === "/auth/form-token") return reply(200, { token: "1700000000000.test" });
      if (path === "/auth/signup" || path === "/auth/login") {
        const body = request.postDataJSON();
        // pragma: allowlist nextline secret
        if (body.password === "wrong-password") return reply(401, { detail: "Invalid email or password" });
        // Accounts with "otp" in the address get the two-step flow: a code by email.
        if (body.email.includes("otp")) {
          return reply(202, {
            otp_required: true,
            challenge_id: "challenge-0123456789",
            email_hint: "o***@college.edu",
            expires_in: 600,
            dev_code: null,
          });
        }
        return route.fulfill({
          status: path.endsWith("signup") ? 201 : 200,
          contentType: "application/json",
          headers: { "Set-Cookie": "signed_in=1; Path=/; SameSite=Strict" },
          body: JSON.stringify({ id: "u1", email: body.email, created_at: "2026-10-21T00:00:00Z" }),
        });
      }
      if (path === "/auth/otp/verify") {
        if (request.postDataJSON().code !== "424242") return reply(400, { detail: "That code is wrong or has expired." });
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          headers: { "Set-Cookie": "signed_in=1; Path=/; SameSite=Strict" },
          body: JSON.stringify({ id: "u1", email: "otp@college.edu", created_at: "2026-10-21T00:00:00Z" }),
        });
      }
      if (path === "/me") return reply(200, { id: "u1", email: "alice@college.edu", created_at: "2026-10-21T00:00:00Z" });
      if (path === "/collections") return reply(200, []);
      if (path === "/analytics/event" || path === "/telemetry/errors") return reply(204);
      if (path.startsWith("/auth/")) return reply(204);
      return reply(404, { detail: "Not found" });
    });
  }

  sent(path: string) {
    return this.requests.filter((r) => new URL(r.url()).pathname === path);
  }
}

export const test = base.extend<{ api: Api }>({
  // auto: every test gets the mocks, so no test can ever reach a real backend by accident.
  api: [
    async ({ page }, provide) => {
      const api = new Api(page);
      await api.install();
      await provide(api);
    },
    { auto: true },
  ],
});

export const expect = test.expect;

/** Pre-answer the cookie banner so it doesn't cover what a test is checking. */
export async function chooseEssentialCookies(page: Page) {
  await page.addInitScript(() => window.localStorage.setItem("notemind-consent-v1", "essential"));
}
