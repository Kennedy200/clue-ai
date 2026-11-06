import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const CREDS = path.resolve(__dirname, "..", "..", "..", "storage", "demo-credentials.json");

test("admin switches the Piper plugin on and its voices appear in the picker, then off again", async ({ page }) => {
  test.skip(test.info().project.name !== "desktop" || !fs.existsSync(CREDS), "needs the seeded admin on desktop");
  const pw = JSON.parse(fs.readFileSync(CREDS, "utf8"))["admin@clue.local"];
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@clue.local");
  await page.getByLabel("Password").fill(pw);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /^Hi/ })).toBeVisible({ timeout: 30_000 });

  await page.goto("/admin");
  const sw = page.getByRole("switch", { name: /Piper/ });
  await expect(sw).toBeVisible({ timeout: 30_000 });
  const saved = () => page.waitForResponse((r) => r.url().includes("/api/admin/plugins/") && r.request().method() === "POST");
  if (await sw.isChecked()) await Promise.all([saved(), sw.uncheck()]);
  await expect(sw).not.toBeChecked();
  await expect(page.getByText(/licen[cs]e/i).first()).toBeVisible(); // the licensing warning is shown to the admin

  await Promise.all([saved(), sw.check()]);
  await expect(sw).toBeChecked();
  await page.reload();
  await expect(page.getByRole("switch", { name: /Piper/ })).toBeChecked(); // persisted

  await page.goto("/app/create/text_story");
  const picker = page.getByLabel("Voice", { exact: true });
  await expect(picker.locator('optgroup[label^="Swahili"]')).toHaveCount(1, { timeout: 30_000 });
  await expect(picker.locator("option", { hasText: "Lanfrica" })).toHaveCount(1);

  await page.goto("/admin");
  await Promise.all([saved(), page.getByRole("switch", { name: /Piper/ }).uncheck()]);
  await page.goto("/app/create/text_story");
  await expect(page.getByLabel("Voice", { exact: true }).locator("option", { hasText: "Lanfrica" })).toHaveCount(0, { timeout: 30_000 });
});
