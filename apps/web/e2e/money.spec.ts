import { expect, test } from "@playwright/test";
import { noHorizontalScroll, shot, signup } from "./helpers";

test("billing: upgrade, top up, invoice, cancel, and the referral link prefills signup", async ({ page, context }) => {
  await signup(page, "bill");
  await page.goto("/app/billing");
  await expect(page.getByRole("heading", { name: "Billing and credits" })).toBeVisible();
  await expect(page.getByLabel("Current plan")).toContainText("Free");
  await noHorizontalScroll(page);

  await page.getByRole("button", { name: "Choose Creator" }).click();
  await expect(page.getByRole("status")).toContainText("You're on Creator");
  await expect(page.getByLabel("Current plan")).toContainText("Creator");
  await expect(page.getByText(/^CLUE-\d{4}-\d{6}$/).first()).toBeVisible();
  await shot(page, "billing");

  const before = await (await page.request.get("/api/billing")).json();
  await page.getByRole("button", { name: /^100 credits/ }).click();
  await expect(page.getByRole("status")).toContainText("100 credits added");
  const after = await (await page.request.get("/api/billing")).json();
  expect(after.credits).toBe(before.credits + 100);

  const [inv] = await Promise.all([context.waitForEvent("page"), page.getByRole("link", { name: "View" }).first().click()]);
  await expect(inv.getByRole("heading", { name: /^Invoice CLUE-/ })).toBeVisible();
  await inv.close();

  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Cancel plan" }).click();
  await expect(page.getByLabel("Current plan")).toContainText("Ends on");

  const link = await page.getByLabel("Your invite link").inputValue();
  expect(link).toContain("/signup?ref=");
  const code = new URL(link).searchParams.get("ref")!;
  await context.clearCookies();
  await page.goto(`/signup?ref=${code}`);
  await expect(page.getByLabel("Referral code (optional)")).toHaveValue(code);
});

test("Clue Score: score, fix my hook without a key, and download the Clue Card", async ({ page }) => {
  await signup(page, "score");
  await page.goto("/app/score");
  await page.getByLabel("Your script").fill("Hello everyone, today I will explain how to save money on data bundles every month in Nigeria.");
  await page.getByRole("button", { name: "Score my script" }).click();
  const score = page.getByTestId("score");
  await expect(score).toBeVisible();
  expect(Number(await score.textContent())).toBeLessThan(60);
  await expect(page.getByText("How to improve it")).toBeVisible();
  await page.getByRole("button", { name: "Fix my hook" }).click();
  await expect(page.getByLabel("Hook options")).toContainText("templates");
  await page.getByRole("button", { name: "Use this" }).first().click();
  await page.getByRole("button", { name: "Score my script" }).click();
  await page.getByRole("button", { name: "Make my Clue Card" }).click();
  const img = page.getByRole("img", { name: /Clue Card showing a score/ });
  await expect(img).toBeVisible();
  await expect.poll(() => img.evaluate((i: HTMLImageElement) => i.naturalWidth)).toBe(1080);
  await shot(page, "score");
  await noHorizontalScroll(page);
});
