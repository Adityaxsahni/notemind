import AxeBuilder from "@axe-core/playwright";

import { chooseEssentialCookies, expect, test } from "./fixtures";

const PUBLIC_PAGES = ["/", "/features", "/privacy", "/terms", "/login", "/signup"];

test.describe("public pages", () => {
  test("landing page has a clear call to action and full metadata", async ({ page }) => {
    await chooseEssentialCookies(page);
    await page.goto("/");
    await expect(page).toHaveTitle(/NoteMind/);
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Your notes.");
    const cta = page.getByRole("link", { name: /get started free/i });
    await expect(cta).toBeVisible();
    await expect(cta).toHaveAttribute("href", "/signup");
    const meta = (name: string) => page.locator(`meta[name="${name}"], meta[property="${name}"]`).first();
    await expect(meta("description")).toHaveAttribute("content", /notes/);
    await expect(meta("og:image")).toHaveAttribute("content", /opengraph-image/);
    await expect(meta("twitter:card")).toHaveAttribute("content", "summary_large_image");
    await expect(page.locator('link[rel="icon"]').first()).toHaveAttribute("href", /icon|favicon/);
  });

  test("every public page has its own title and description", async ({ page }) => {
    const seen = new Set<string>();
    for (const path of PUBLIC_PAGES) {
      await page.goto(path);
      const title = await page.title();
      const description = await page.locator('meta[name="description"]').getAttribute("content");
      expect(description?.length, path).toBeGreaterThan(40);
      expect(seen.has(title), `duplicate title on ${path}`).toBe(false);
      seen.add(title);
    }
  });

  test("no accessibility violations, including colour contrast", async ({ page }) => {
    await chooseEssentialCookies(page);
    await page.emulateMedia({ reducedMotion: "reduce" }); // judge final colours, not fade-ins
    for (const path of PUBLIC_PAGES) {
      await page.goto(path);
      const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
      const serious = results.violations.filter((v) => ["serious", "critical"].includes(v.impact ?? ""));
      expect(
        serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`),
        path,
      ).toEqual([]);
    }
  });

  test("no broken internal links", async ({ page, request }) => {
    const links = new Set<string>();
    for (const path of PUBLIC_PAGES) {
      await page.goto(path);
      const hrefs = await page.locator("a[href^='/']").evaluateAll((as) => as.map((a) => a.getAttribute("href") ?? ""));
      for (const href of hrefs) links.add(href.split("#")[0]);
    }
    for (const href of links) {
      const response = await request.get(href);
      expect(response.status(), href).toBeLessThan(400);
    }
    expect(links.size).toBeGreaterThanOrEqual(7); // sanity: the crawl actually found links
  });

  test("unknown pages get the custom 404", async ({ page }) => {
    const response = await page.goto("/no-such-page");
    expect(response?.status()).toBe(404);
    await expect(page.getByRole("heading", { level: 1 })).toContainText("isn't in");
    await expect(page.getByRole("link", { name: /home page/i })).toBeVisible();
  });

  test("robots.txt and sitemap list only public pages", async ({ request }) => {
    const robots = await (await request.get("/robots.txt")).text();
    expect(robots).toContain("Disallow: /courses");
    expect(robots).toContain("Sitemap:");
    const sitemap = await (await request.get("/sitemap.xml")).text();
    expect(sitemap).toContain("/features");
    expect(sitemap).not.toContain("/courses");
  });

  test("pages send security headers", async ({ request }) => {
    const headers = (await request.get("/")).headers();
    expect(headers["content-security-policy"]).toContain("frame-ancestors 'none'");
    expect(headers["x-frame-options"]).toBe("DENY");
    expect(headers["x-content-type-options"]).toBe("nosniff");
    expect(headers["x-powered-by"]).toBeUndefined();
  });

  test("social preview image is generated", async ({ request }) => {
    const response = await request.get("/opengraph-image");
    expect(response.status()).toBe(200);
    expect(response.headers()["content-type"]).toBe("image/png");
  });
});

test.describe("cookie consent and analytics", () => {
  test("nothing is tracked until the visitor accepts", async ({ page, api }) => {
    await page.goto("/");
    const banner = page.getByRole("dialog", { name: "Cookies and privacy" });
    await expect(banner).toBeVisible();
    await page.waitForTimeout(300);
    expect(api.sent("/analytics/event")).toHaveLength(0);

    await banner.getByRole("button", { name: "Essential only" }).click();
    await expect(banner).toBeHidden();
    await page.goto("/features");
    await expect(page.getByRole("dialog")).toBeHidden(); // the choice is remembered
    expect(api.sent("/analytics/event")).toHaveLength(0);
  });

  test("accepting sends anonymous page views; settings can be reopened", async ({ page, api }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Accept analytics" }).click();
    await expect.poll(() => api.sent("/analytics/event").length).toBeGreaterThan(0);
    expect(api.sent("/analytics/event")[0].postDataJSON().path).toBe("/");

    await page.getByRole("button", { name: "Cookie settings" }).click();
    await expect(page.getByRole("dialog", { name: "Cookies and privacy" })).toBeVisible();
  });
});

test.describe("sign-up and log-in forms", () => {
  test.beforeEach(async ({ page }) => chooseEssentialCookies(page));

  test("validates fields before sending anything", async ({ page, api }) => {
    await page.goto("/signup");
    await page.getByLabel("Email").fill("not-an-email");
    await page.getByLabel("Password", { exact: true }).fill("short");
    await page.getByLabel("Password", { exact: true }).blur();
    await expect(page.getByText("doesn't look like an email")).toBeVisible();
    await expect(page.getByText("Use at least 10 characters.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Create free account" })).toBeDisabled(); // terms unticked
    expect(api.sent("/auth/signup")).toHaveLength(0);
  });

  test("submits with the bot-check fields and lands on the courses page", async ({ page, api }) => {
    await page.goto("/signup");
    await page.getByLabel("Email").fill("alice@college.edu");
    await page.getByLabel("Password", { exact: true }).fill("correct-horse-battery");
    await page.getByRole("checkbox").check();
    await page.getByRole("button", { name: "Create free account" }).click();
    await expect(page).toHaveURL(/\/courses$/);
    const body = api.sent("/auth/signup")[0].postDataJSON();
    expect(body).toMatchObject({ email: "alice@college.edu", form_token: "1700000000000.test", website: "" });
  });

  test("the honeypot field is hidden from people and screen readers", async ({ page }) => {
    await page.goto("/signup");
    await expect(page.locator("#website")).not.toBeInViewport();
    await expect(page.getByRole("textbox", { name: "Website" })).toHaveCount(0);
  });

  test("login shows the server's error message", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("alice@college.edu");
    await page.getByLabel("Password", { exact: true }).fill("wrong-password");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "Invalid" })).toContainText("Invalid email or password");
  });
});

test.describe("mobile", () => {
  test("menu button opens the navigation, which closes after navigating", async ({ page, isMobile }) => {
    test.skip(!isMobile, "desktop shows the full navigation");
    await chooseEssentialCookies(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Open menu" }).click();
    const menu = page.getByRole("navigation", { name: "Mobile" });
    await menu.getByRole("link", { name: "Features" }).click();
    await expect(page).toHaveURL(/\/features$/);
    await expect(menu).toBeHidden();
  });

  test("no horizontal scrolling on small screens", async ({ page, isMobile }) => {
    test.skip(!isMobile, "mobile only");
    await chooseEssentialCookies(page);
    for (const path of ["/", "/features", "/privacy", "/signup"]) {
      await page.goto(path);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow, path).toBeLessThanOrEqual(0);
    }
  });
});
