import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

/** Collects console errors and failed requests so a test can assert the page is clean. */
export function watchErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  page.on("pageerror", (e) => errors.push(String(e)));
  return errors;
}

export async function loginAs(page: Page, username: string) {
  await page.goto("/login");
  await page.getByRole("button", { name: new RegExp(username) }).click();
  await expect(page.getByRole("banner")).toBeVisible();
}

export async function setTheme(page: Page, theme: "light" | "dark") {
  await page.evaluate((t) => {
    localStorage.setItem("up_theme", t);
    document.documentElement.dataset.theme = t;
  }, theme);
}

/** Fails on serious or critical WCAG 2.2 AA violations. */
export async function expectAccessible(page: Page, scope?: string) {
  let axe = new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]);
  if (scope) axe = axe.include(scope);
  const results = await axe.analyze();
  const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${v.id}: ${v.help} (${v.nodes.length}) e.g. ${v.nodes[0]?.html.slice(0, 120)}`)).toEqual([]);
}
