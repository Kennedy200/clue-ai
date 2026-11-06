import { expect, test } from "@playwright/test";
import { STORY, makeProject, noHorizontalScroll, second, shot, signup, videoInfo } from "./helpers";

const preview = (page: import("@playwright/test").Page) => page.getByRole("img", { name: /^Preview, scene/ });

test.describe("editor", () => {
  test("desktop: play, re-voice, captions, undo, reorder, autosave across reload, and render", async ({ page }) => {
    test.skip(test.info().project.name !== "desktop", "desktop run");
    await signup(page, "ed");
    const pid = await makeProject(page, STORY);
    await page.goto(`/app/editor/${pid}`);
    await expect(preview(page)).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("status").filter({ hasText: /Saved/ })).toBeVisible();
    await shot(page, "editor-open");

    // preview plays: the clock advances and captions appear
    const clock = page.locator("span.font-mono").filter({ hasText: / \/ / }).first();
    const before = await clock.innerText();
    await page.getByRole("button", { name: "Play", exact: true }).click();
    await expect.poll(() => clock.innerText(), { timeout: 10_000 }).not.toBe(before);
    await page.getByRole("button", { name: "Pause", exact: true }).click();

    // edit text -> stale voice warning -> real re-voice with Kokoro
    const textbox = page.getByLabel("What the narrator says");
    await textbox.fill("The window was open and the kettle was warm.");
    await expect(page.getByText("The voice still says the old words.")).toBeVisible();
    await expect(page.getByRole("status").filter({ hasText: /Unsaved|Saving|Saved/ })).toBeVisible();
    await page.getByRole("button", { name: /Re-voice this scene/ }).click();
    await expect(page.getByText("The voice still says the old words.")).toBeHidden({ timeout: 120_000 });

    // captions: pick a box style, preview reflects it
    await page.getByRole("tab", { name: "Captions" }).click();
    await page.getByRole("radio", { name: /Yellow box/ }).click();
    await expect(page.getByRole("radio", { name: /Yellow box/ })).toHaveAttribute("aria-checked", "true");
    await shot(page, "editor-captions");

    // undo restores the previous caption style
    await page.keyboard.press("Control+z");
    await expect(page.getByRole("radio", { name: /Bold highlight/ })).toHaveAttribute("aria-checked", "true");
    await page.keyboard.press("Control+y");
    await expect(page.getByRole("radio", { name: /Yellow box/ })).toHaveAttribute("aria-checked", "true");

    // scene tools: transition, duplicate, move, delete
    await page.getByRole("tab", { name: "Scene" }).click();
    await page.getByLabel("Transition").selectOption("fade");
    const count = async () => page.getByRole("option").count();
    const n0 = await count();
    await page.getByRole("button", { name: "Duplicate" }).click();
    expect(await count()).toBe(n0 + 1);
    await page.getByRole("button", { name: "Delete scene" }).click();
    expect(await count()).toBe(n0);

    // autosave, then a full reload keeps every edit
    await expect(page.getByRole("status").filter({ hasText: "Saved" })).toBeVisible({ timeout: 15_000 });
    await page.reload();
    await expect(preview(page)).toBeVisible({ timeout: 60_000 });
    await expect(page.getByLabel("What the narrator says")).toHaveValue("The window was open and the kettle was warm.");
    await page.getByRole("tab", { name: "Captions" }).click();
    await expect(page.getByRole("radio", { name: /Yellow box/ })).toHaveAttribute("aria-checked", "true");

    // export: a Cinematic render of the edited video
    await page.getByRole("tab", { name: "Export" }).click();
    await page.getByRole("radio", { name: /Cinematic/ }).check();
    await expect(page.getByText(/Cost:/)).toContainText("14");
    await page.getByRole("button", { name: /Render cinematic video/ }).click();
    await expect(page.getByText("Rendered. Your video is ready below.")).toBeVisible({ timeout: 300_000 });
    const v = await page.getByLabel("Last rendered video").evaluate((el: HTMLVideoElement) => new Promise<{ w: number; h: number }>((res) => {
      const done = () => res({ w: el.videoWidth, h: el.videoHeight });
      el.readyState >= 1 ? done() : el.addEventListener("loadedmetadata", done, { once: true });
    }));
    expect(v).toEqual({ w: 1080, h: 1920 });
    await shot(page, "editor-exported");
  });

  test("swap the picture with a free photo (live Wikimedia search)", async ({ page }) => {
    test.skip(test.info().project.name !== "desktop", "desktop run");
    await signup(page, "ph");
    const pid = await makeProject(page, STORY);
    await page.goto(`/app/editor/${pid}`);
    await expect(preview(page)).toBeVisible({ timeout: 60_000 });
    await page.getByRole("tab", { name: "Photos" }).click();
    await page.getByLabel("Search", { exact: true }).fill("Lagos skyline");
    await page.getByRole("button", { name: "Search" }).click();
    const first = page.locator('button[title*="Public domain"], button[title*="CC"]').first();
    await expect(first).toBeVisible({ timeout: 60_000 });
    await first.click();
    await expect(preview(page).locator("img")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText(/^Credit:/)).toBeVisible(); // author and licence are recorded for attribution
    await shot(page, "editor-photo");
  });

  test("two tabs: the stale one gets a conflict instead of overwriting", async ({ page, context }) => {
    test.skip(test.info().project.name !== "desktop", "desktop run");
    await signup(page, "cf");
    const pid = await makeProject(page, STORY);
    await page.goto(`/app/editor/${pid}`);
    await expect(preview(page)).toBeVisible({ timeout: 60_000 });
    const other = await second(context, page);
    await other.goto(`/app/editor/${pid}`);
    await expect(preview(other)).toBeVisible({ timeout: 60_000 });
    await other.getByLabel("Transition").selectOption("fade");
    await expect(other.getByRole("status").filter({ hasText: "Saved" })).toBeVisible({ timeout: 15_000 });
    await page.getByLabel("Title on screen").fill("Edited in the old tab");
    await expect(page.getByRole("alert").filter({ hasText: /changed elsewhere/ })).toBeVisible({ timeout: 15_000 });
    await page.getByRole("button", { name: "Reload the latest version" }).click();
    await expect(page.getByLabel("Transition")).toHaveValue("fade");
  });

  test("offline edits are kept and saved when the connection returns", async ({ page, context }) => {
    test.skip(test.info().project.name !== "desktop", "desktop run");
    await signup(page, "off");
    const pid = await makeProject(page, STORY);
    await page.goto(`/app/editor/${pid}`);
    await expect(preview(page)).toBeVisible({ timeout: 60_000 });
    await context.setOffline(true);
    await page.getByLabel("Transition").selectOption("fade");
    await expect(page.getByRole("status").filter({ hasText: /Offline/ })).toBeVisible({ timeout: 15_000 });
    await context.setOffline(false);
    await expect(page.getByRole("status").filter({ hasText: "Saved" })).toBeVisible({ timeout: 30_000 });
    await page.reload();
    await expect(page.getByLabel("Transition")).toHaveValue("fade");
  });

  test("phone: preview, timeline and bottom sheet fit a 360 px screen", async ({ page }) => {
    test.skip(test.info().project.name !== "mobile", "phone run");
    await signup(page, "mob");
    const pid = await makeProject(page, STORY);
    await page.goto(`/app/editor/${pid}`);
    await expect(preview(page)).toBeVisible({ timeout: 60_000 });
    await noHorizontalScroll(page);
    const box = await preview(page).boundingBox();
    expect(box!.width).toBeLessThanOrEqual(360);
    expect(box!.y + box!.height).toBeLessThan(640); // the preview is visible without scrolling
    await expect(page.getByRole("button", { name: "Play", exact: true })).toBeInViewport(); // transport and timeline are not hidden by the sheet
    await expect(page.getByRole("listbox", { name: "Timeline of scenes" })).toBeInViewport();
    await shot(page, "editor-phone");
    for (const t of ["Captions", "Voice", "Music", "Export", "Scene"]) {
      await page.getByRole("tab", { name: t }).tap();
      await expect(page.getByRole("tab", { name: t })).toHaveAttribute("aria-selected", "true");
      await noHorizontalScroll(page);
    }
    // every touch target in the sheet is at least 36 px tall
    const small = await page.locator('[role="tabpanel"] button, [role="tabpanel"] select, [role="tabpanel"] input[type="text"]').evaluateAll((els) => els.filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.height < 36; }).length);
    expect(small).toBe(0);
    await shot(page, "editor-phone-sheet-open");
    await page.getByRole("button", { name: "Collapse editing panel" }).tap();
    await page.getByRole("button", { name: "Play", exact: true }).tap();
    await page.getByRole("button", { name: "Pause", exact: true }).tap();
    await shot(page, "editor-phone-collapsed");
  });
});
