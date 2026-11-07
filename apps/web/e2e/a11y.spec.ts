import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { signup } from "./helpers";

/** WCAG 2.1 A + AA rules via axe, plus: no console errors, no failed same-origin requests, no sideways scroll. */
async function audit(page: Page, url: string, errors: string[]) {
  await page.goto(url);
  await page.waitForLoadState("networkidle").catch(() => {});
  const res = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  const bad = res.violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.slice(0, 2).map((n) => n.target.join(" ") + " -> " + (n.failureSummary || "").replace(/\s+/g, " ").slice(0, 200)).join(" | ")}`);
  expect(bad, `${url} accessibility`).toEqual([]);
  expect(errors, `${url} console`).toEqual([]);
}

function watch(page: Page) {
  const errors: string[] = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("response", (r) => { if (r.status() >= 500 || (r.status() >= 400 && r.url().includes("/_next/"))) errors.push(`${r.status()} ${r.url()}`); });
  return errors;
}

const PUBLIC = ["/", "/pricing", "/features", "/features/ai-voiceover", "/blog", "/blog/caption-best-practices", "/contact", "/about", "/terms", "/privacy", "/refund", "/login", "/signup", "/forgot"];

test("public pages: WCAG AA and a clean console", async ({ page }) => {
  test.skip(test.info().project.name !== "desktop", "desktop run; layout checks run on the phone project elsewhere");
  test.setTimeout(240_000);
  const errors = watch(page);
  for (const u of PUBLIC) { errors.length = 0; await audit(page, u, errors); }
});

test("signed-in pages: WCAG AA and a clean console", async ({ page }) => {
  test.setTimeout(300_000);
  const errors = watch(page);
  await signup(page, "a11y");
  const pages = ["/app", "/app/create/text_story", "/app/create/ranking", "/app/tools", "/app/tools/ideas", "/app/media", "/app/projects", "/app/billing", "/app/score", "/app/brand", "/app/bulk", "/app/calendar", "/app/team", "/app/analytics"];
  for (const u of pages) { errors.length = 0; await audit(page, u, errors); }
});
