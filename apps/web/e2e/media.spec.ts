import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { SAMPLE_DIR, noHorizontalScroll, shot, signup } from "./helpers";

test("Save data: a 1080p video is shrunk to 720p in the browser before it is uploaded", async ({ page }) => {
  test.skip(test.info().project.name !== "desktop", "desktop run");
  await signup(page, "med");
  await page.goto("/app/media");
  const original = path.join(SAMPLE_DIR, "phone_1080p.mp4"); // 1920x1080, about 12 Mbps like a phone recording, 10 s
  await page.getByLabel(/Save data/).check();
  await page.locator('input[type="file"]').setInputFiles(original);
  await expect(page.getByRole("button", { name: /Shrinking to 720p/ })).toBeVisible({ timeout: 20_000 });
  await shot(page, "media-shrinking");
  await expect(page.getByText(/phone_1080p-720p\.webm/)).toBeVisible({ timeout: 180_000 });
  const me = await page.request.get("/api/media");
  const [a] = await me.json();
  expect(a.name).toBe("phone_1080p-720p.webm");
  expect(Math.min(a.width, a.height)).toBe(720);
  expect(a.size).toBeLessThan(fs.statSync(original).size / 2); // the point of Save data: far fewer bytes to upload
  expect(a.has_audio).toBe(true);
  expect(a.duration).toBeGreaterThan(8);
  await noHorizontalScroll(page);
});

test("Without Save data the original file is uploaded untouched", async ({ page }) => {
  test.skip(test.info().project.name !== "desktop", "desktop run");
  await signup(page, "med2");
  await page.goto("/app/media");
  await page.getByLabel(/Save data/).uncheck();
  await page.locator('input[type="file"]').setInputFiles(path.join(SAMPLE_DIR, "clip_face.mp4"));
  await expect(page.getByText(/clip_face\.mp4/)).toBeVisible({ timeout: 120_000 });
  const [a] = await (await page.request.get("/api/media")).json();
  expect([a.width, a.height]).toEqual([1080, 1920]);
});
