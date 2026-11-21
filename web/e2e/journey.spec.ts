import { expect, test, type Page } from "@playwright/test";
import { expectAccessible, enterAs, setTheme, watchErrors } from "./helpers";

async function reset(page: Page) {
  const r = await page.request.post("/api/v1/demo/reset");
  expect(r.ok()).toBeTruthy();
}
async function switchTo(page: Page, role: string) {
  await page.getByRole("button", { name: /Account menu/ }).click();
  await page.getByRole("menuitem", { name: new RegExp(role) }).click();
  await expect(page.getByText(new RegExp(`Now viewing as ${role}`))).toBeVisible();
}
const shot = (page: Page, name: string) => page.screenshot({ path: `test-results/shots/${name}.png`, fullPage: true });

for (const theme of ["light", "dark"] as const) {
  test(`full demo story: journey, early warning, MSME in Hindi, governance (${theme})`, async ({ page }) => {
    test.setTimeout(120_000); // the whole story in one test: about 30 s locally, slower on CI runners
    const errors = watchErrors(page);
    await reset(page);
    await page.goto("/");
    await setTheme(page, theme);

    // Relationship manager: consent, score, memo.
    await enterAs(page, "rm1");
    await expect(page.getByRole("heading", { name: "Applications", level: 1 })).toBeVisible();
    await expect(page.getByRole("tab", { name: /Needs your action/ })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("row", { name: /Sharma Auto Components/ })).toBeVisible();
    await expect(page.getByText("Pink bar = changed since you last looked")).toBeVisible();
    await expectAccessible(page);
    await shot(page, `console-${theme}`);
    await page.getByRole("row", { name: /Sharma Auto Components/ }).click();
    await expect(page.getByRole("heading", { name: "Sharma Auto Components", level: 1 })).toBeVisible();
    await expect(page.getByRole("list", { name: "Application progress" })).toBeVisible();

    await page.getByRole("button", { name: "Request consent and pull data" }).click();
    await expect(page.getByText("Consent received").first()).toBeVisible();
    await page.getByRole("button", { name: "Run scoring" }).first().click();
    await expect(page.getByRole("img", { name: /Factory Health Score 742 out of 900, band Approve/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Why this score" })).toBeVisible();
    // The change is visible at a glance: a toast and a new timeline entry.
    await expect(page.getByText("Scored 742").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "What changed" })).toBeVisible();
    await page.getByRole("tab", { name: "Signals" }).click();
    await expect(page).toHaveURL(/tab=signals/);
    await page.getByRole("radio", { name: "Buyers" }).click();
    await page.getByRole("radio", { name: "Orders & dispatch" }).click();
    await expectAccessible(page);
    await shot(page, `detail-signals-${theme}`);

    // What-if simulator: labelled, and it does not change the real score.
    await page.getByRole("button", { name: "Try a what-if" }).click();
    const sim = page.getByRole("dialog", { name: "What-if simulator" });
    await expect(sim.getByTestId("sim-score")).toHaveText("742");
    await sim.getByLabel("Cheque/NACH bounces per month").fill("2");
    await expect(sim.getByTestId("sim-score")).not.toHaveText("742");
    await expect(sim.getByText(/Simulation only/).first()).toBeVisible();
    await expectAccessible(page);
    await shot(page, `detail-whatif-${theme}`);
    await sim.getByRole("button", { name: "Close" }).click();

    // Memo: citations open the clause; the RM cannot decide.
    await page.getByRole("button", { name: "Generate memo" }).click();
    await expect(page.getByText(/Memo ready/).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: /Credit memo/ })).toBeVisible();
    await page.getByRole("button", { name: "Open policy clause 4.1" }).first().click();
    await expect(page.getByRole("dialog", { name: /§4\.1/ })).toBeVisible();
    await page.getByRole("button", { name: "Close", exact: true }).click();
    await page.getByRole("button", { name: /Agent trace/ }).click();
    await expect(page.getByText(/scoring engine/).first()).toBeVisible();
    await expectAccessible(page);
    await shot(page, `detail-memo-${theme}`);
    await page.getByRole("tab", { name: "Decision" }).click();
    await expect(page.getByText("Only a credit officer can approve or reject").first()).toBeVisible();

    // Credit officer: review, approve against the KFS preview, disburse.
    await switchTo(page, "Credit Officer");
    await page.getByRole("row", { name: /Sharma Auto Components/ }).click();
    await page.getByRole("button", { name: "Review & decide" }).click();
    await expect(page).toHaveURL(/tab=decision/);
    await expect(page.getByRole("heading", { name: "Memo summary" })).toBeVisible();
    await page.getByRole("button", { name: "Confirm approval" }).click();
    await expect(page.getByText("A justification is mandatory")).toBeVisible();
    await page.getByLabel(/Comment/).fill("Approve per memo; strong order book and clean banking.");
    await expectAccessible(page);
    await shot(page, `detail-decision-${theme}`);
    await page.getByRole("button", { name: "Confirm approval" }).click();
    const confirm = page.getByRole("dialog", { name: "Approve this application?" });
    await expect(confirm).toContainText("₹3,00,00,000");
    await confirm.getByRole("button", { name: "Approve and issue KFS" }).click();
    await expect(page.getByText("Key Fact Statement issued")).toBeVisible();
    await page.getByRole("button", { name: "Disburse via LOS" }).first().click();
    await expect(page.getByText(/Disbursed \(ref LOS-/)).toBeVisible();
    await expect(page.getByText("under continuous early-warning monitoring")).toBeVisible();
    await page.getByRole("tab", { name: "Activity" }).click();
    await expect(page.getByText(/^Approved/).first()).toBeVisible();
    await shot(page, `detail-decided-${theme}`);

    // Early warning: play six weeks, the hero's HIGH alert fires with before → after, the RM logs a visit.
    await switchTo(page, "Relationship Manager");
    await page.getByRole("link", { name: /^Alerts/ }).click();
    await expect(page.getByRole("heading", { name: "Early-warning alerts" })).toBeVisible();
    await page.getByRole("button", { name: "Play 6 weeks" }).click();
    await expect(page.getByText(/Playing six weeks/)).toBeVisible();
    await expect(page.getByText(/Six weeks later: \d+ new alert/)).toBeVisible({ timeout: 30_000 });
    const heroAlert = page.getByRole("button", { name: "Open high alert for Sharma Auto Components" });
    await expect(heroAlert).toBeVisible();
    await heroAlert.click();
    await expect(page.getByRole("heading", { name: "Sharma Auto Components", level: 2 })).toBeVisible();
    await expect(page.getByText("Suggested next step")).toBeVisible();
    await expect(page.getByText("E-way bill value").first()).toBeVisible();
    await expect(page.getByText(/was/).first()).toBeAttached(); // before → after, read out for screen readers
    await expectAccessible(page);
    await shot(page, `alerts-${theme}`);
    await page.getByRole("button", { name: /^Log (visit|action)$/ }).click();
    const log = page.getByRole("dialog", { name: "Log action" });
    await log.getByLabel("Note").fill("Visited the unit; top buyer has cut orders. Limit review started.");
    await log.getByRole("button", { name: "Save action" }).click();
    await expect(page.getByText(/Action logged for Sharma Auto Components/)).toBeVisible();
    await page.getByRole("tab", { name: /Acted on/ }).click();
    await expect(page.getByRole("button", { name: "Open high alert for Sharma Auto Components" })).toBeVisible();

    // Portfolio: one visual per tab.
    await page.getByRole("link", { name: "Portfolio" }).click();
    await expect(page.getByRole("heading", { name: "Portfolio", level: 1 })).toBeVisible();
    await expectAccessible(page);
    await page.getByRole("tab", { name: /Band movement/ }).click();
    await expect(page.getByRole("table", { name: /Accounts by score band/ })).toBeVisible();
    await page.getByRole("tab", { name: /Exposure/ }).click();
    await expect(page.getByRole("table", { name: "Monitored accounts" })).toBeVisible();
    await shot(page, `portfolio-${theme}`);

    // MSME owner, in Hindi: readiness, the plan, then stop sharing.
    await switchTo(page, "MSME Owner");
    await expect(page.getByRole("heading", { name: "My factory" })).toBeVisible();
    await expect(page.getByText(/Namaste/)).toBeVisible();
    await page.getByRole("radio", { name: "हिन्दी" }).click();
    await expect(page.getByRole("heading", { name: "मेरी फ़ैक्टरी" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "सुधारने लायक एक बात" })).toBeVisible();
    await expectAccessible(page);
    await shot(page, `msme-home-hi-${theme}`);
    await page.getByRole("tab", { name: "योजना" }).click();
    // click, not check(): the tick is applied through the query cache on the next frame.
    await page.getByRole("checkbox").first().click();
    await expect(page.getByRole("checkbox").first()).toBeChecked();
    await expect(page.getByText(/^1 \/ \d+ पूरे$/)).toBeVisible();
    await expectAccessible(page);
    await shot(page, `msme-plan-hi-${theme}`);
    await page.getByRole("tab", { name: "सहमति" }).click();
    await page.getByRole("button", { name: "सहमति वापस लें" }).click();
    await page.getByRole("button", { name: "हाँ, वापस लें" }).click();
    await expect(page.getByText("सहमति वापस ले ली गई है").first()).toBeVisible();
    await page.getByRole("tab", { name: "होम" }).click();
    await expect(page.getByText(/अब कोई नया डेटा नहीं लिया जा रहा/)).toBeVisible();
    await page.getByRole("radio", { name: "English" }).click();

    // Risk head: governance and system.
    await switchTo(page, "Risk Head");
    await page.getByRole("link", { name: "Governance" }).click();
    await expect(page.getByRole("heading", { name: "Governance", level: 1 })).toBeVisible();
    await expect(page.getByText("AUC, out-of-time test")).toBeVisible();
    await expectAccessible(page);
    await shot(page, `governance-model-${theme}`);
    for (const [tab, marker] of [
      ["Audit trail", /entries/],
      ["Consent ledger", /Active consents/],
      ["Responsible AI", /memo\.summary\.v1/],
    ] as const) {
      await page.getByRole("tab", { name: tab }).click();
      await expect(page.getByText(marker).first()).toBeVisible();
      await expectAccessible(page);
    }
    await expect(page.getByText(/RBI Digital Lending Directions, 2025/).first()).toBeVisible();
    // Data & models: provenance of every dataset, real benchmarks kept apart from synthetic results.
    await page.getByRole("tab", { name: "Data & models" }).click();
    await expect(page.getByRole("heading", { name: "Data provenance" })).toBeVisible();
    await expect(page.getByText("Real public data").first()).toBeVisible();
    await expect(page.getByText("U.S. SBA 7(a) FOIA loans, manufacturing FY2010+")).toBeVisible();
    await expect(page.getByText(/Indian MSME accuracy will be proven in a lender pilot/)).toBeVisible();
    await expectAccessible(page);
    await shot(page, `governance-data-models-${theme}`);
    // The audit trail is filterable: the officer's decision is on record.
    await page.getByRole("tab", { name: "Audit trail" }).click();
    await page.getByLabel("Agent").selectOption("orchestrator");
    await expect(page.getByText(/orchestrator · credit_decision/)).toBeVisible();
    // The whole story so far is on one unbroken hash chain.
    await page.getByRole("button", { name: "Verify chain" }).click();
    await expect(page.getByText("Chain intact")).toBeVisible();
    await expectAccessible(page);
    await shot(page, `governance-audit-${theme}`);
    await page.getByRole("tab", { name: "Consent ledger" }).click();
    await page.getByRole("searchbox").fill("Sharma");
    await expect(page.getByText("revoked").first()).toBeVisible();

    await page.getByRole("link", { name: "System" }).click();
    await expect(page.getByRole("heading", { name: "System", level: 1 })).toBeVisible();
    await expect(page.getByText("Database").first()).toBeVisible();
    await expectAccessible(page);
    await shot(page, `system-${theme}`);

    expect(errors).toEqual([]);
  });
}
