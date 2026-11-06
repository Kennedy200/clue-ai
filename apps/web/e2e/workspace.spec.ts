import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { noHorizontalScroll, shot, signup } from "./helpers";

const CREDS = path.resolve(__dirname, "..", "..", "..", "storage", "demo-credentials.json");

test("team: invite by email, the invitee joins as viewer and cannot manage people", async ({ page, browser }) => {
  test.skip(test.info().project.name !== "desktop", "desktop run");
  await signup(page, "own");
  await page.goto("/app/team");
  await page.getByLabel("New team name").fill("Lagos Studio");
  await page.getByRole("button", { name: "Create team" }).click();
  await expect(page.getByRole("tab", { name: /Lagos Studio/ })).toBeVisible();

  const second = await browser.newContext({ baseURL: "http://localhost:3000" });
  const p2 = await second.newPage();
  const email2 = await signup(p2, "mate");
  await page.getByLabel("Invite by email").fill(email2);
  await page.getByRole("button", { name: "Invite", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Invite sent");
  await expect(page.getByText(`Invited: ${email2}`)).toBeVisible();

  const mails: { to: string; subject: string; body: string }[] = await (await page.request.get("/api/dev-mail")).json();
  const mail = mails.find((m) => m.to === email2 && /invited you/.test(m.subject))!;
  const link = mail.body.match(/http\S*invite=\S+/)![0];
  await p2.goto(new URL(link).pathname + new URL(link).search);
  await expect(p2.getByRole("status")).toContainText("You joined the team");
  await expect(p2.getByRole("tab", { name: /Lagos Studio · viewer/ })).toBeVisible();
  await expect(p2.getByLabel("Invite by email")).toHaveCount(0); // viewers get no invite form
  await shot(page, "team");
  await second.close();
});

test("brand kit, bulk CSV, calendar with publish pack, and your numbers", async ({ page }) => {
  await signup(page, "ws");
  await page.goto("/app/brand");
  await page.getByLabel("Kit name").fill("Lagos Gold");
  await page.getByLabel("Highlight colour").fill("#ffd700");
  await page.getByRole("button", { name: "Save brand kit" }).click();
  await expect(page.getByRole("status")).toContainText("Brand kit saved");
  await expect(page.getByText("Lagos Gold").first()).toBeVisible();
  await noHorizontalScroll(page);

  await page.goto("/app/bulk");
  await page.getByLabel("Brand kit").selectOption({ label: "Lagos Gold" });
  await page.locator("#csv").fill("title,text\nOne,Stop scrolling and listen to this one tip.\nTwo,Here is another short story to try.\nBad,hi\n");
  await page.getByRole("button", { name: "Create all videos" }).click();
  await expect(page.locator("p[role=alert]")).toContainText("row 4"); // the bad row blocks the whole batch, nothing charged
  await page.locator("#csv").fill("title,text\nOne,Stop scrolling and listen to this one tip.\nTwo,Here is another short story to try.\n");
  await page.getByRole("button", { name: "Create all videos" }).click();
  await expect(page.getByRole("status")).toContainText("2 of 2 started");
  await shot(page, "bulk");

  await page.goto("/app/calendar");
  await page.getByLabel("Title").fill("Monday tip");
  await page.getByLabel("When").fill("2026-12-07T09:00");
  await page.getByRole("button", { name: "Add to calendar" }).click();
  await expect(page.getByText("Monday tip")).toBeVisible();
  await expect(page.getByText(/Mon.*(7 Dec|Dec 7)/)).toBeVisible(); // local time round-trips
  await page.getByRole("button", { name: "Mark posted" }).click();
  await expect(page.getByText("published").first()).toBeVisible();
  await noHorizontalScroll(page);

  await page.goto("/app/analytics");
  await expect(page.getByRole("heading", { name: "Your numbers" })).toBeVisible();
  await expect(page.getByLabel("Credits spent per day")).toBeVisible();
  await shot(page, "analytics");
});

test("admin: dashboard, find a user and add credits, plans, excel export, audit log", async ({ page }) => {
  test.skip(test.info().project.name !== "desktop" || !fs.existsSync(CREDS), "needs the seeded admin on desktop");
  const email = await signup(page, "tgt");
  await page.context().clearCookies();
  const pw = JSON.parse(fs.readFileSync(CREDS, "utf8"))["admin@clue.local"];
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@clue.local");
  await page.getByLabel("Password").fill(pw);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /^Hi/ })).toBeVisible({ timeout: 30_000 });
  await page.goto("/admin");
  await expect(page.getByLabel("Overview").getByText("AI cost, 30 days")).toBeVisible({ timeout: 30_000 });

  await page.getByRole("tab", { name: "Users" }).click();
  await page.getByLabel("Search users").fill(email);
  await page.getByRole("button", { name: "Search" }).click();
  const row = page.getByRole("listitem").filter({ hasText: email });
  await expect(row).toBeVisible();
  const answers = ["25", "e2e goodwill"];
  page.on("dialog", (d) => d.accept(answers.shift() ?? ""));
  await row.getByRole("button", { name: "Credits" }).click();
  await expect(page.getByRole("status")).toContainText("Credits updated");

  await page.getByRole("tab", { name: "Plans" }).click();
  await expect(page.getByRole("button", { name: "Save starter" })).toBeVisible();

  await page.getByRole("tab", { name: "Excel" }).click();
  const res = await page.request.get("/api/admin/export.xlsx");
  expect(res.status()).toBe(200);
  expect((await res.body()).subarray(0, 2).toString()).toBe("PK"); // a real zip/xlsx

  await page.getByRole("tab", { name: "Audit" }).click();
  await expect(page.getByText("credits.adjust").first()).toBeVisible();
  await shot(page, "admin-audit");
});
