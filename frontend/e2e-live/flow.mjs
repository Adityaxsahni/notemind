// One-off check against the running Docker stack (not part of CI): sign up, enter the
// emailed code (shown on screen in local development), land on the courses page, log out,
// log back in with password + code, and screenshot each step.
import { chromium, devices } from "@playwright/test";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const OUT = process.argv[2] ?? ".";
const email = `demo-${Date.now()}@example.com`;
const password = "Revision-season-2026"; // pragma: allowlist secret

const browser = await chromium.launch();
for (const [name, options] of [
  ["desktop", { viewport: { width: 1366, height: 900 } }],
  ["mobile", devices["Pixel 7"]],
]) {
  const page = await (await browser.newContext(options)).newPage();
  const shot = (step) => page.screenshot({ path: `${OUT}/${name}-${step}.png`, fullPage: step === "home" });

  await page.goto(`${BASE}/`);
  await page.getByRole("button", { name: "Essential only" }).click();
  await shot("home");

  const user = name === "desktop" ? email : `m-${email}`;
  await page.goto(`${BASE}/signup`);
  await page.getByLabel("Email").fill(user);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("checkbox").check();
  await shot("signup");
  await page.getByRole("button", { name: "Create free account" }).click();
  await page.getByText("Check your").waitFor();
  await shot("otp");
  const code = (await page.locator("#otp ~ *, [role=status] button").first().textContent())?.trim();
  await page.getByLabel("Sign-in code").fill(code);
  await page.waitForURL("**/courses");
  await page.getByLabel("New collection name").fill("Cell Biology 101");
  await page.getByRole("button", { name: "New collection" }).click();
  await page.getByText("Cell Biology 101").first().waitFor();
  await shot("courses");
  console.log(`${name}: signed up and verified with code ${code}`);

  await page.getByRole("link", { name: /Enter|Cell Biology/ }).first().click();
  await page.waitForURL("**/c/**");
  await page.getByText("Ask your notes").waitFor();
  await shot("course");

  // Log out, then log in again: password, then a new code.
  await page.context().clearCookies();
  await page.goto(`${BASE}/login`);
  await page.getByLabel("Email").fill(user);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Log in" }).click();
  await page.getByText("Check your").waitFor();
  const again = (await page.locator("[role=status] button").first().textContent())?.trim();
  await page.getByLabel("Sign-in code").fill(again);
  await page.waitForURL("**/courses");
  console.log(`${name}: logged in again with password + code ${again}`);
}
await browser.close();
