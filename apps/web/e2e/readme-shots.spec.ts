import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { signup } from "./helpers";

/** Regenerates the pictures used in README.md:  README_SHOTS=1 npx playwright test e2e/readme-shots.spec.ts --project=desktop */
const OUT = path.resolve(__dirname, "..", "..", "..", "docs", "images");
test.skip(!process.env.README_SHOTS, "only when regenerating README pictures");

const hideDevBadge = (p: Page) => p.addStyleTag({ content: "nextjs-portal, [data-nextjs-toast], #__next-route-announcer__ { display: none !important; }" });
async function snap(p: Page, name: string, full = false) {
  await hideDevBadge(p);
  await p.waitForTimeout(400);
  await p.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: full });
}

test("capture", async ({ browser }) => {
  test.setTimeout(600_000);
  fs.mkdirSync(OUT, { recursive: true });
  const desk = await browser.newContext({ viewport: { width: 1280, height: 800 }, baseURL: "http://localhost:3000" });
  const phone = await browser.newContext({ viewport: { width: 390, height: 780 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, baseURL: "http://localhost:3000" });
  const p = await desk.newPage();

  await p.goto("/");
  await p.waitForTimeout(3500); // let the hero demo finish its count-up
  await snap(p, "home");
  await p.goto("/pricing");
  await snap(p, "pricing");

  await signup(p, "shots");
  await p.goto("/app");
  await p.getByRole("link", { name: "dev inbox" }).waitFor();
  await p.evaluate(() => document.querySelectorAll('[class*="bg-coral/10"]').forEach((e) => e.remove())); // hide the "verify your email" banner
  await snap(p, "dashboard");
  await p.goto("/app/create/text_story");
  await snap(p, "create");

  // a real video, so the editor and the result are real
  const me = await (await p.request.get("/api/auth/me")).json();
  const r = await (await p.request.post("/api/render/text-story", { headers: { "x-csrf-token": me.csrf }, data: { title: "Save data on your phone", text: "Your phone is eating your data. Turn off background refresh and watch your bundle last twice as long. Try it today and tell me what happens." } })).json();
  await expect.poll(async () => (await (await p.request.get(`/api/jobs/${r.job_id}`)).json()).status, { timeout: 240_000 }).toBe("done");
  await p.goto(`/app/editor/${r.project_id}`);
  await p.getByRole("tab", { name: "Captions" }).click();
  await p.waitForTimeout(800);
  await snap(p, "editor");
  const dl = await (await p.request.get(`/api/projects/${r.project_id}/download-url`)).json();
  fs.writeFileSync(path.join(OUT, "_video.mp4"), await (await p.request.get(dl.url)).body());

  await p.goto("/app/score");
  await p.getByLabel("Your script").fill("Stop wasting 3 hours a day on email. Here is the exact rule I use. Check it once at noon. Reply in two lines. Your inbox stays clean. Follow for more habits.");
  await p.getByRole("button", { name: "Score my script" }).click();
  await p.getByTestId("score").waitFor({ state: "attached" });
  await p.waitForTimeout(2200);
  await snap(p, "score");
  await p.goto("/app/billing");
  await p.getByRole("button", { name: "Choose Creator" }).click();
  await p.getByRole("status").waitFor();
  await p.evaluate(() => window.scrollTo(0, 0));
  await snap(p, "billing");
  await p.goto("/app/tools");
  await snap(p, "tools");
  await p.goto("/app/brand");
  await snap(p, "brand");

  const m = await phone.newPage();
  await m.goto("/login");
  // sign in as the account created above
  await m.getByLabel("Email").fill(me.email);
  await m.getByLabel("Password").fill("password-e2e-123");
  await m.getByRole("button", { name: "Sign in" }).click();
  await m.getByRole("heading", { name: /^Hi/ }).waitFor({ timeout: 30_000 });
  await m.evaluate(() => document.querySelectorAll('[class*="bg-coral/10"]').forEach((e) => e.remove()));
  await snap(m, "phone-dashboard");
  await m.goto(`/app/editor/${r.project_id}`);
  await m.getByRole("tab", { name: "Captions" }).click();
  await m.waitForTimeout(900);
  await snap(m, "phone-editor");
  await m.goto("/app/score");
  await m.getByLabel("Your script").fill("Stop wasting 3 hours a day on email. Here is the exact rule I use. Check it once at noon. Follow for more habits.");
  await m.getByRole("button", { name: "Score my script" }).click();
  await m.waitForTimeout(2200);
  await snap(m, "phone-score");
  await desk.close();
  await phone.close();
});
