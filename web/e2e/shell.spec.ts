import { expect, test } from "@playwright/test";
import { expectAccessible, loginAs, setTheme, watchErrors } from "./helpers";

const HOME: Record<string, RegExp> = { rm1: /\/console$/, co1: /\/console$/, risk1: /\/cockpit$/, sharma: /\/msme$/ };

for (const theme of ["light", "dark"] as const) {
  test.describe(`shell (${theme})`, () => {
    for (const [user, home] of Object.entries(HOME)) {
      test(`${user} lands on their home screen with no console errors`, async ({ page }) => {
        const errors = watchErrors(page);
        await page.goto("/login");
        await setTheme(page, theme);
        await loginAs(page, user);
        await expect(page).toHaveURL(home);
        await page.waitForLoadState("networkidle");
        await page.screenshot({ path: `test-results/shots/${user}-${theme}.png`, fullPage: true });
        expect(errors).toEqual([]);
      });
    }

    test("header and sidebar pass accessibility checks", async ({ page }) => {
      await page.goto("/login");
      await setTheme(page, theme);
      await loginAs(page, "rm1");
      await expectAccessible(page, "header");
      await expectAccessible(page, "aside");
    });
  });
}

test("theme toggle switches and persists", async ({ page }) => {
  await page.goto("/login");
  await setTheme(page, "light");
  await loginAs(page, "rm1");
  await page.getByRole("button", { name: "Switch to dark theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.keyboard.press("t");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});

test("command palette jumps to the hero application", async ({ page }) => {
  await loginAs(page, "rm1");
  await page.keyboard.press("ControlOrMeta+k");
  const input = page.getByPlaceholder(/Search factories/);
  await expect(input).toBeVisible();
  await input.fill("sharma");
  await page
    .getByRole("option", { name: /Sharma Auto Components/ })
    .first()
    .click();
  await expect(page).toHaveURL(/\/console\/\d+$/);
  await expect(page.getByRole("navigation", { name: "Breadcrumb" })).toContainText("Application #");
});

test("keyboard shortcuts navigate and open the shortcut sheet", async ({ page }) => {
  await loginAs(page, "rm1");
  await page.keyboard.press("g");
  await page.keyboard.press("p");
  await expect(page).toHaveURL(/\/cockpit$/);
  await page.keyboard.press("g");
  await page.keyboard.press("c");
  await expect(page).toHaveURL(/\/console$/);
  await page.keyboard.press("?");
  await expect(page.getByRole("dialog", { name: "Keyboard shortcuts" })).toBeVisible();
});

test("role switcher changes persona", async ({ page }) => {
  await loginAs(page, "rm1");
  await page.getByRole("button", { name: /Account menu/ }).click();
  await page.getByRole("menuitem", { name: /Risk Head/ }).click();
  await expect(page).toHaveURL(/\/cockpit$/);
  await expect(page.getByRole("banner")).toContainText("Risk Head");
});

test("an expired session returns to login", async ({ page }) => {
  await loginAs(page, "rm1");
  await page.evaluate(() => localStorage.setItem("up_token", "not-a-valid-token"));
  await page.reload();
  await expect(page).toHaveURL(/\/login$/);
});

test("sidebar collapses and stays usable", async ({ page }) => {
  await loginAs(page, "rm1");
  await page.getByRole("button", { name: "Collapse sidebar" }).click();
  await expect(page.getByRole("button", { name: "Expand sidebar" })).toBeVisible();
  await page.getByRole("link", { name: "Risk cockpit" }).click();
  await expect(page).toHaveURL(/\/cockpit$/);
});
