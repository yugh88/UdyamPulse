import { expect, test, type Page } from "@playwright/test";
import { expectAccessible, loginAs, setTheme, watchErrors } from "./helpers";

async function reset(page: Page) {
  const r = await page.request.post("/api/demo/reset");
  expect(r.ok()).toBeTruthy();
}
const shot = (page: Page, name: string) => page.screenshot({ path: `test-results/shots/${name}.png`, fullPage: true });

for (const theme of ["light", "dark"] as const) {
  test(`loan journey: consent → score → memo → what-if → approve → disburse (${theme})`, async ({ page }) => {
    const errors = watchErrors(page);
    await reset(page);
    await page.goto("/login");
    await setTheme(page, theme);
    await expectAccessible(page);
    await shot(page, `login-${theme}`);

    // Relationship manager: consent, score, memo.
    await loginAs(page, "rm1");
    await expect(page.getByRole("heading", { name: "Applications" })).toBeVisible();
    await expect(page.getByRole("row", { name: /Sharma Auto Components/ })).toBeVisible();
    await expectAccessible(page);
    await shot(page, `console-${theme}`);
    await page.getByRole("row", { name: /Sharma Auto Components/ }).click();
    await expect(page.getByRole("heading", { name: "Sharma Auto Components" })).toBeVisible();

    await page.getByRole("button", { name: "Request consent and pull data" }).click();
    await expect(page.getByText("Consent received")).toBeVisible();
    await page.getByRole("button", { name: "Run scoring" }).click();
    await expect(page.getByRole("img", { name: /Factory Health Score 723 out of 900, band Approve/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Top 5 reasons" })).toBeVisible();
    await page.getByRole("tab", { name: "Receivables" }).click();
    await page.getByRole("tab", { name: "Orders and dispatch" }).click();
    await expectAccessible(page);
    await shot(page, `detail-assessment-${theme}`);

    // The RM cannot decide.
    await page.getByRole("button", { name: "Generate memo" }).click();
    await expect(page.getByRole("heading", { name: /Credit memo/ })).toBeVisible();
    await expect(page.getByText("Only a credit officer can approve or reject").first()).toBeVisible();
    await page.getByRole("button", { name: "Open policy clause 4.1" }).first().click();
    await expect(page.getByRole("dialog", { name: /§4\.1/ })).toBeVisible();
    await page.getByRole("button", { name: "Close", exact: true }).click();
    await expectAccessible(page);
    await shot(page, `detail-memo-${theme}`);

    // What-if simulator: labelled, and it does not change the real score.
    await page.getByRole("tab", { name: "What-if simulator" }).click();
    await expect(page.getByTestId("sim-score")).toHaveText("723");
    await page.getByLabel("Cheque/NACH bounces per month").fill("2");
    await expect(page.getByTestId("sim-score")).not.toHaveText("723");
    await expect(page.getByText(/Simulation only/)).toBeVisible();
    await expectAccessible(page);
    await shot(page, `detail-whatif-${theme}`);

    // Credit officer: review the KFS, approve, disburse.
    await page.getByRole("button", { name: /Account menu/ }).click();
    await page.getByRole("menuitem", { name: /Credit Officer/ }).click();
    await page.getByRole("row", { name: /Sharma Auto Components/ }).click();
    await page.getByRole("button", { name: "Review memo and decide" }).click();
    await page.getByRole("button", { name: "Review Key Fact Statement" }).click();
    await expect(page.getByText("A justification is mandatory")).toBeVisible();
    await page.getByLabel(/Comment/).fill("Approve per memo; strong order book and clean banking.");
    await page.getByRole("button", { name: "Review Key Fact Statement" }).click();
    const confirm = page.getByRole("dialog", { name: "Confirm approval" });
    await expect(confirm).toContainText("₹3,00,00,000");
    await confirm.getByRole("button", { name: "Confirm approval" }).click();
    await expect(page.getByText("Key Fact Statement issued")).toBeVisible();
    await page.getByRole("button", { name: "Disburse via LOS" }).first().click();
    await expect(page.getByText(/Disbursed \(ref LOS-/)).toBeVisible();
    await expect(page.getByText("under continuous early-warning monitoring")).toBeVisible();
    await shot(page, `detail-decided-${theme}`);

    expect(errors).toEqual([]);
  });
}
