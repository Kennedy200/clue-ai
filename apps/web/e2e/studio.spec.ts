import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

const SHOTS = path.resolve(__dirname, "..", "..", "..", "storage", "screens");
const SAMPLE = path.resolve(__dirname, "..", "..", "..", "storage", "sample", "talk.mp4");
const shot = (p: Page, name: string) => p.screenshot({ path: path.join(SHOTS, `${test.info().project.name}-${name}.png`), fullPage: false });

async function signup(page: Page) {
  const email = `e2e-${test.info().project.name}-${Date.now()}@example.com`;
  await page.goto("/signup");
  await page.getByLabel("Name").fill("E2E Tester");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel(/^Password/).fill("password-e2e-123");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: /^Hi, E2E Tester/ })).toBeVisible({ timeout: 20_000 });
}

async function noHorizontalScroll(page: Page) {
  const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(over, "page must not scroll sideways").toBeLessThanOrEqual(1);
}

async function waitForVideo(page: Page, timeout = 300_000) {
  const video = page.locator("video").first();
  await expect(video).toBeVisible({ timeout });
  await expect.poll(() => video.evaluate((v: HTMLVideoElement) => (v.readyState >= 1 ? v.duration : 0)), { timeout: 60_000 }).toBeGreaterThan(3);
  return video.evaluate((v: HTMLVideoElement) => ({ w: v.videoWidth, h: v.videoHeight, d: v.duration }));
}

test("dashboard and every creation form render without sideways scroll", async ({ page }) => {
  await signup(page);
  await shot(page, "dashboard");
  await expect.poll(() => page.locator("header img").first().evaluate((i: HTMLImageElement) => i.naturalWidth), { message: "logo must load" }).toBeGreaterThan(0);
  await noHorizontalScroll(page);
  for (const s of ["text_story", "video_story", "commentary", "split_screen", "ranking"]) {
    await page.goto(`/app/create/${s}`);
    await expect(page.getByRole("button", { name: "Create video" })).toBeVisible();
    await noHorizontalScroll(page);
  }
  await shot(page, "create-ranking");
  await page.goto("/app/tools");
  await expect(page.getByRole("link", { name: /Auto Clipping/ })).toBeVisible();
  await noHorizontalScroll(page);
  await shot(page, "tools");
});

test("text story: write, create, watch the video", async ({ page }) => {
  test.skip(test.info().project.name !== "desktop", "one real render per style is enough");
  await signup(page);
  await page.goto("/app/create/text_story");
  await page.getByLabel("Title (for your library)").fill("Kettle");
  await page.getByLabel("Script / story").fill("The door was already open when I got home. Nothing was missing, but the kettle was still warm. I never found out who made the tea.");
  await expect(page.getByText(/This costs/)).toBeVisible();
  await page.getByRole("button", { name: "Create video" }).click();
  await expect(page.getByRole("heading", { name: "Making your video" })).toBeVisible();
  await expect(page.getByRole("status")).toBeVisible({ timeout: 30_000 });
  await shot(page, "progress");
  const v = await waitForVideo(page);
  expect(v.w).toBe(1080);
  expect(v.h).toBe(1920);
  await shot(page, "video-done");
  await expect(page.getByRole("link", { name: "Download MP4" })).toBeVisible();
});

test("ranking on a phone: countdown video", async ({ page }) => {
  test.skip(test.info().project.name !== "mobile", "phone viewport run");
  await signup(page);
  await page.goto("/app/create/ranking");
  await page.getByLabel("Opening line (optional)").fill("Top three Nigerian foods");
  await page.getByLabel("Item 1 name").fill("Jollof rice");
  await page.getByLabel("Item 2 name").fill("Suya");
  await page.getByLabel("Item 3 name").fill("Pounded yam");
  await page.getByLabel("Item 3 line").fill("Best with egusi.");
  await noHorizontalScroll(page);
  await page.getByRole("button", { name: "Create video" }).click();
  const v = await waitForVideo(page);
  expect(v.h).toBe(1920);
  await noHorizontalScroll(page);
  await shot(page, "ranking-done");
});

test("thumbnail maker returns four real images", async ({ page }) => {
  test.skip(test.info().project.name !== "desktop", "desktop only");
  await signup(page);
  await page.goto("/app/tools/thumbnails");
  await page.getByLabel("Title text").fill("I posted 20 videos in 30 days");
  await page.getByRole("button", { name: "Make 4 thumbnails" }).click();
  const imgs = page.getByRole("img", { name: /Thumbnail option/ });
  await expect(imgs).toHaveCount(4, { timeout: 60_000 });
  for (let i = 0; i < 4; i++) await expect.poll(() => imgs.nth(i).evaluate((e: HTMLImageElement) => e.naturalWidth)).toBe(1280);
  await shot(page, "thumbnails");
});

test("auto clipping: upload, analyse, export a reframed clip", async ({ page }) => {
  test.skip(test.info().project.name !== "desktop", "desktop only");
  await signup(page);
  await page.goto("/app/tools/clips");
  await page.locator('input[type="file"]').setInputFiles(SAMPLE);
  await expect(page.locator("select").first()).toContainText("talk.mp4", { timeout: 120_000 });
  await page.getByRole("button", { name: /Find the best clips/ }).click();
  await expect(page.getByText(/Why this clip/).first()).toBeVisible({ timeout: 240_000 });
  await expect(page.getByText(/estimated/).first()).toBeVisible(); // no AI key: honestly labelled
  await shot(page, "clips-found");
  await page.getByRole("button", { name: /Export \(2 credits\)/ }).first().click();
  await expect(page.getByRole("link", { name: "Download MP4" })).toBeVisible({ timeout: 240_000 });
  const v = await page.locator("video").first().evaluate((el: HTMLVideoElement) => new Promise<{ w: number; h: number }>((res) => {
    const done = () => res({ w: el.videoWidth, h: el.videoHeight });
    el.readyState >= 1 ? done() : el.addEventListener("loadedmetadata", done, { once: true });
  }));
  expect(v).toEqual({ w: 1080, h: 1920 });
  await shot(page, "clip-exported");
});
