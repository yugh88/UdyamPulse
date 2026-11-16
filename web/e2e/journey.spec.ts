import { expect, test, type Page } from "@playwright/test";
import { expectAccessible, loginAs, setTheme, watchErrors } from "./helpers";

async function reset(page: Page) {
  const r = await page.request.post("/api/v1/demo/reset");
  expect(r.ok()).toBeTruthy();
}
async function switchTo(page: Page, role: string) {
  await page.getByRole("button", { name: /Account menu/ }).click();
  await page.getByRole("menuitem", { name: new RegExp(role) }).click();
  await expect(page.getByText(new RegExp(`Now signed in as ${role}`))).toBeVisible();
}
const shot = (page: Page, name: string) => page.screenshot({ path: `test-results/shots/${name}.png`, fullPage: true });

for (const theme of ["light", "dark"] as const) {
  test(`full demo story: journey, early warning, MSME in Hindi, governance (${theme})`, async ({ page }) => {
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
    await switchTo(page, "Credit Officer");
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

    // Risk cockpit: play six weeks, the hero's HIGH alert fires, the RM logs an action.
    await switchTo(page, "Relationship Manager");
    await page.getByRole("link", { name: "Risk cockpit" }).click();
    await expect(page.getByRole("heading", { name: "Portfolio risk cockpit" })).toBeVisible();
    await expect(page.getByRole("table", { name: "Monitored accounts" })).toBeVisible();
    await page.getByRole("button", { name: "Play story" }).first().click();
    await expect(page.getByText(/Playing six weeks/)).toBeVisible();
    await expect(page.getByText(/Six weeks later: \d+ new alert/)).toBeVisible({ timeout: 30_000 });
    const heroAlert = page.getByRole("row", { name: "Open high alert for Sharma Auto Components" });
    await expect(heroAlert).toBeVisible();
    await expect(page.getByRole("table", { name: /Accounts by score band/ })).toBeVisible();
    await expectAccessible(page);
    await shot(page, `cockpit-${theme}`);
    await heroAlert.click();
    const drawer = page.getByRole("dialog", { name: "Sharma Auto Components" });
    await expect(drawer).toContainText("Order loss");
    await expect(drawer).toContainText(/visit \+ limit review/i);
    await expectAccessible(page);
    await shot(page, `alert-drawer-${theme}`);
    await drawer.getByLabel("Note").fill("Visited the unit; top buyer has cut orders. Limit review started.");
    await drawer.getByRole("button", { name: "Log action" }).click();
    await expect(page.getByText(/Action logged for Sharma Auto Components/)).toBeVisible();

    // MSME owner, in Hindi: sees the plan, ticks a step, revokes consent.
    await switchTo(page, "MSME Owner");
    await expect(page.getByRole("heading", { name: /Namaste/ })).toBeVisible();
    await page.getByRole("radio", { name: "हिन्दी" }).click();
    await expect(page.getByRole("heading", { name: /नमस्ते/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: "क्या नुकसान कर रहा है" })).toBeVisible();
    await expectAccessible(page);
    await shot(page, `msme-home-hi-${theme}`);
    await page.getByRole("tab", { name: "90 दिन की योजना" }).click();
    // click, not check(): the tick is applied through the query cache on the next frame.
    await page.getByRole("checkbox").first().click();
    await expect(page.getByRole("checkbox").first()).toBeChecked();
    await expect(page.getByText(/में से 1 कदम पूरे/)).toBeVisible();
    await expectAccessible(page);
    await shot(page, `msme-plan-hi-${theme}`);
    await page.getByRole("tab", { name: "मेरा डेटा" }).click();
    await page.getByRole("button", { name: "सहमति वापस लें" }).click();
    await page.getByRole("button", { name: "हाँ, वापस लें" }).click();
    await expect(page.getByText("सहमति वापस ले ली गई है").first()).toBeVisible();
    await page.getByRole("tab", { name: "होम" }).click();
    await expect(page.getByText(/अब कोई नया डेटा नहीं लिया जा रहा/)).toBeVisible();
    await page.getByRole("tab", { name: "संदेश" }).click();
    await expect(page.getByRole("heading", { name: "आपके बैंक के संदेश" })).toBeVisible();
    await page.getByRole("radio", { name: "English" }).click();

    // Risk head: governance.
    await switchTo(page, "Risk Head");
    await page.getByRole("link", { name: "Governance" }).click();
    await expect(page.getByRole("heading", { name: "Governance and compliance" })).toBeVisible();
    await expect(page.getByText("AUC, out-of-time test")).toBeVisible();
    await expectAccessible(page);
    await shot(page, `governance-model-${theme}`);
    for (const [tab, marker] of [
      ["Audit trail", /entries/],
      ["Consent ledger", /Active consents/],
      ["AI usage", /memo\.summary\.v1/],
      ["Compliance", /RBI Digital Lending Directions, 2025/],
    ] as const) {
      await page.getByRole("tab", { name: tab }).click();
      await expect(page.getByText(marker).first()).toBeVisible();
      await expectAccessible(page);
    }
    // The audit trail is filterable: the officer's decision is on record.
    await page.getByRole("tab", { name: "Audit trail" }).click();
    await page.getByLabel("Agent").selectOption("orchestrator");
    await expect(page.getByText(/orchestrator · credit_decision/)).toBeVisible();
    await shot(page, `governance-audit-${theme}`);
    await page.getByRole("tab", { name: "Consent ledger" }).click();
    await page.getByRole("searchbox").fill("Sharma");
    await expect(page.getByText("revoked").first()).toBeVisible();

    expect(errors).toEqual([]);
  });
}
