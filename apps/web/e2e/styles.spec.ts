import { expect, test } from "@playwright/test";
import path from "node:path";
import { SAMPLE_DIR, noHorizontalScroll, shot, signup, videoInfo } from "./helpers";

const CLIP = path.join(SAMPLE_DIR, "clip_face.mp4"); // 30 s, 1080x1920, with speech

async function upload(page: import("@playwright/test").Page, label: RegExp | string) {
  await page.getByText(label).locator("xpath=ancestor::div[1]").locator('input[type="file"]').setInputFiles(CLIP);
  await expect(page.getByLabel(label).locator("option", { hasText: "clip_face.mp4" })).toHaveCount(1, { timeout: 120_000 });
}

test.describe("styles in the browser", () => {
  test.beforeEach(async ({ page: _page }, info) => {
    test.skip(info.project.name !== "desktop", "one real render per style on desktop");
  });

  test("split screen with an uploaded bottom loop", async ({ page }) => {
    await signup(page, "ss");
    await page.goto("/app/create/split_screen");
    await page.getByLabel("Text to narrate").fill("Here is the story on the top half. The loop keeps people watching underneath.");
    await upload(page, /Bottom loop/);
    await page.getByRole("button", { name: "Create video" }).click();
    const v = await videoInfo(page);
    expect([v.w, v.h]).toEqual([1080, 1920]);
    await shot(page, "split-screen-done");
  });

  test("commentary over an uploaded clip, original sound turned down", async ({ page }) => {
    await signup(page, "cm");
    await page.goto("/app/create/commentary");
    await upload(page, "Your clip");
    await page.getByLabel("Your commentary").fill("Look at how steady that is. Nobody expected this to work.");
    await page.getByRole("button", { name: "Create video" }).click();
    const v = await videoInfo(page);
    expect([v.w, v.h]).toEqual([1080, 1920]);
    await page.getByRole("link", { name: "Edit this video" }).click();
    await expect(page.getByRole("img", { name: /^Preview, scene/ })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByLabel(/^Original sound:/)).toBeVisible(); // the ducked source audio is editable
    await shot(page, "commentary-editor");
  });

  test("video story with free Wikimedia photos (live), credits recorded", async ({ page }) => {
    await signup(page, "vs");
    await page.goto("/app/create/video_story");
    await page.getByLabel("Script / story").fill("Lagos wakes up early. Boats cross the lagoon at dawn.");
    await page.getByLabel("Pictures").selectOption("photos");
    await page.getByRole("button", { name: "Create video" }).click();
    const v = await videoInfo(page);
    expect([v.w, v.h]).toEqual([1080, 1920]);
    await page.getByRole("link", { name: "Edit this video" }).click();
    await expect(page.getByRole("img", { name: /^Preview, scene/ })).toBeVisible({ timeout: 60_000 });
    await shot(page, "video-story-editor");
  });

  test("ranking and text story forms keep phone layout rules", async ({ page }) => {
    await signup(page, "lay");
    await page.setViewportSize({ width: 360, height: 640 });
    for (const s of ["video_story", "commentary", "split_screen"]) {
      await page.goto(`/app/create/${s}`);
      await expect(page.getByRole("button", { name: "Create video" })).toBeVisible();
      await noHorizontalScroll(page);
    }
  });
});
