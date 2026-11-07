import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import path from "node:path";

export const SHOTS = path.resolve(__dirname, "..", "..", "..", "storage", "screens");
export const SAMPLE_DIR = path.resolve(__dirname, "..", "..", "..", "storage", "sample");
export const shot = (p: Page, name: string) => p.screenshot({ path: path.join(SHOTS, `${test.info().project.name}-${name}.png`) });

export async function signup(page: Page, tag = "u") {
  const email = `e2e-${tag}-${test.info().project.name}-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.com`;
  await page.goto("/signup");
  await page.getByLabel("Name").fill("E2E Tester");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel(/^Password/).fill("password-e2e-123");
  await page.getByRole("button", { name: "Create account" }).click();
  const hi = page.getByRole("heading", { name: /^Hi, E2E Tester/ });
  // signup is limited to 5 per minute per visitor; every test here is the same visitor, so wait out the limit once
  if (!(await hi.isVisible({ timeout: 15_000 }).catch(() => false)) && (await page.getByText(/Too many attempts/).isVisible().catch(() => false))) {
    await page.waitForTimeout(61_000);
    await page.getByRole("button", { name: "Create account" }).click();
  }
  await expect(hi).toBeVisible({ timeout: 30_000 });
  return email;
}

export async function noHorizontalScroll(page: Page) {
  const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(over, "page must not scroll sideways").toBeLessThanOrEqual(1);
}

export async function videoInfo(page: Page, timeout = 300_000) {
  const video = page.locator("video").first();
  await expect(video).toBeVisible({ timeout });
  await expect.poll(() => video.evaluate((v: HTMLVideoElement) => (v.readyState >= 1 ? v.duration : 0)), { timeout: 90_000 }).toBeGreaterThan(2);
  return video.evaluate((v: HTMLVideoElement) => ({ w: v.videoWidth, h: v.videoHeight, d: v.duration }));
}

/** Create a project through the API (fast) using the signed-in browser session, and wait for the render to finish. */
export async function makeProject(page: Page, body: Record<string, unknown>): Promise<string> {
  const me = await (await page.request.get("/api/auth/me")).json();
  const r = await page.request.post("/api/render/create", { data: body, headers: { "x-csrf-token": me.csrf } });
  expect(r.ok(), await r.text()).toBeTruthy();
  const { job_id, project_id } = await r.json();
  await expect.poll(async () => (await (await page.request.get(`/api/jobs/${job_id}`)).json()).status, { timeout: 240_000, intervals: [2000] }).toBe("done");
  return project_id;
}

export const STORY = {
  style: "text_story", title: "Editor test", voice: "af_heart",
  spec: { text: "The door was already open when I got home. Nothing was missing, but the kettle was still warm. I never found out who made the tea." },
};

export async function second(context: BrowserContext, page: Page): Promise<Page> {
  const p2 = await context.newPage();
  await p2.setViewportSize(page.viewportSize() ?? { width: 1280, height: 800 });
  return p2;
}
