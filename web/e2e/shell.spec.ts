import { expect, test } from "@playwright/test";
import { expectAccessible, loginAs, setTheme, watchErrors } from "./helpers";

// Start from the seeded state whatever ran before.
test.beforeAll(async ({ request }) => {
  expect((await request.post("/api/v1/demo/reset")).ok()).toBeTruthy();
});

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

test("a reload keeps the session through the refresh cookie, without storing a token", async ({ page }) => {
  await loginAs(page, "rm1");
  expect(await page.evaluate(() => Object.keys(localStorage).filter((k) => k.includes("token")))).toEqual([]);
  const cookies = await page.context().cookies();
  const refresh = cookies.find((c) => c.name === "up_refresh");
  expect(refresh?.httpOnly).toBe(true);
  expect(refresh?.sameSite).toBe("Strict");
  await page.reload();
  await expect(page).toHaveURL(/\/console$/);
  await expect(page.getByRole("banner")).toContainText("Relationship Manager");
});

test("an ended session returns to login", async ({ page }) => {
  await loginAs(page, "rm1");
  await page.context().clearCookies(); // refresh token gone: the next reload cannot renew the session
  await page.reload();
  await expect(page).toHaveURL(/\/login$/);
});

test("sign out revokes the refresh token", async ({ page }) => {
  await loginAs(page, "rm1");
  const before = (await page.context().cookies()).find((c) => c.name === "up_refresh")!.value;
  await page.getByRole("button", { name: /Account menu/ }).click();
  await page.getByRole("menuitem", { name: /Sign out/ }).click();
  await expect(page).toHaveURL(/\/login$/);
  const res = await page.request.post("/api/v1/auth/refresh", { headers: { Cookie: `up_refresh=${before}` } });
  expect(res.status()).toBe(401);
});

test("sidebar collapses and stays usable", async ({ page }) => {
  await loginAs(page, "rm1");
  await page.getByRole("button", { name: "Collapse sidebar" }).click();
  await expect(page.getByRole("button", { name: "Expand sidebar" })).toBeVisible();
  await page.getByRole("link", { name: "Risk cockpit" }).click();
  await expect(page).toHaveURL(/\/cockpit$/);
});

test("guided demo signs in the right persona and opens the right screen", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Guided demo" }).click();
  const panel = page.getByRole("complementary", { name: "Guided demo" });
  await expect(panel).toContainText("step 1 of 7");
  await panel.getByRole("button", { name: "Sign in as rm1 and open" }).click();
  await expect(page).toHaveURL(/\/console\/\d+$/);
  await expect(page.getByRole("heading", { name: "Sharma Auto Components" })).toBeVisible();
  for (let i = 0; i < 4; i++) await panel.getByRole("button", { name: "Next step" }).click();
  await expect(panel).toContainText("Early warning");
  await panel.getByRole("button", { name: "Sign in as risk1 and open" }).click();
  await expect(page).toHaveURL(/\/cockpit$/);
  await expect(page.getByRole("banner")).toContainText("Risk Head");
  await expectAccessible(page);
  await panel.getByRole("button", { name: "Close the guided demo" }).click();
  await expect(panel).toBeHidden();
});
