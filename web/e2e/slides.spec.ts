import { expect, test, type Page } from "@playwright/test";
import { enterAs, setTheme } from "./helpers";

/**
 * Screenshots of every screen at 1920x1080 from the real running app, light theme, walking the demo story.
 *   SLIDES=1 npx playwright test e2e/slides.spec.ts                      → docs/media/slides/NN-name.png
 *   SLIDES=1 SCREENS_DIR=/some/folder npx playwright test e2e/slides.spec.ts  → that folder instead
 * Skipped in normal runs.
 */
test.skip(!process.env.SLIDES, "screenshots only on demand (SLIDES=1)");
test.use({ viewport: { width: 1920, height: 1080 } });

const OUT = process.env.SCREENS_DIR || "../docs/media/slides";
let n = 0;
const snap = async (page: Page, name: string) => {
  await page.waitForTimeout(1200); // let charts finish drawing
  await expect(page.getByRole("status", { name: /Loading/ })).toHaveCount(0);
  // No toasts on slides: hide them only while the picture is taken (the steps still wait on them).
  const hide = await page.addStyleTag({ content: "[data-sonner-toaster]{display:none!important}" });
  n += 1;
  await page.screenshot({ path: `${OUT}/${String(n).padStart(2, "0")}-${name}.png` });
  await hide.evaluate((el) => el.remove());
};
async function switchTo(page: Page, role: string) {
  await page.getByRole("button", { name: /Account menu/ }).click();
  await page.getByRole("menuitem", { name: new RegExp(role) }).click();
  await expect(page.getByText(new RegExp(`Now viewing as ${role}`))).toBeVisible();
}

test("screens", async ({ page }) => {
  test.setTimeout(240_000);
  expect((await page.request.post("/api/v1/demo/reset")).ok()).toBeTruthy();
  await page.goto("/");
  await setTheme(page, "light");
  await page.reload();
  // What a reviewer sees first: the app opens straight on the RM's queue, with the one-time prototype notice.
  const note = page.getByRole("note").filter({ hasText: "not a lending decision" });
  await expect(note).toBeVisible();
  await snap(page, "first-visit");
  await note.getByRole("button", { name: "Got it" }).click();

  // Relationship manager.
  await enterAs(page, "rm1");
  await expect(page.getByRole("row", { name: /Sharma Auto Components/ })).toBeVisible();
  await snap(page, "applications");
  await page.getByRole("row", { name: /Sharma Auto Components/ }).click();
  await page.getByRole("button", { name: "Request consent and pull data" }).click();
  await expect(page.getByText("Consent received").first()).toBeVisible();
  await page.getByRole("button", { name: "Run scoring" }).first().click();
  await expect(page.getByRole("heading", { name: "Why this score" })).toBeVisible();
  await expect(page.getByRole("img", { name: /Factory Health Score \d+ out of 900/ })).toBeVisible();
  await snap(page, "application-overview");
  await page.getByRole("tab", { name: "Signals" }).click();
  await snap(page, "application-signals");
  await page.getByRole("button", { name: "Try a what-if" }).click();
  await page.getByRole("dialog", { name: "What-if simulator" }).getByLabel("Cheque/NACH bounces per month").fill("2");
  await expect(page.getByText(/Simulation only/).first()).toBeVisible();
  await snap(page, "what-if");
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByRole("button", { name: "Generate memo" }).click();
  await expect(page.getByRole("heading", { name: /Credit memo/ })).toBeVisible();
  await page.getByRole("button", { name: /Agent trace/ }).click();
  await snap(page, "credit-memo");

  // Credit officer: the hero now shows as updated in the queue; decide.
  await switchTo(page, "Credit Officer");
  await expect(page.getByRole("row", { name: /Sharma Auto Components/ })).toBeVisible();
  await snap(page, "applications-credit-officer");
  await page.getByRole("row", { name: /Sharma Auto Components/ }).click();
  await expect(page.getByRole("heading", { name: "What changed" })).toBeVisible();
  await snap(page, "application-overview-credit-officer");
  await page.getByRole("button", { name: "Review & decide" }).click();
  await page.getByLabel(/Comment/).fill("Strong order growth backed by power use. Buyer concentration covered by covenant.");
  await snap(page, "decision");
  await page.getByRole("button", { name: "Confirm approval" }).click();
  await snap(page, "decision-kfs-preview");
  await page.getByRole("dialog", { name: "Approve this application?" }).getByRole("button", { name: "Approve and issue KFS" }).click();
  await expect(page.getByText("Key Fact Statement issued")).toBeVisible();
  await snap(page, "decision-approved");
  await page.getByRole("button", { name: "Disburse via LOS" }).first().click();
  await expect(page.getByText(/Disbursed \(ref LOS-/)).toBeVisible();
  await page.getByRole("tab", { name: "Activity" }).click();
  await snap(page, "application-activity");

  // Early warning.
  await switchTo(page, "Relationship Manager");
  await page.getByRole("link", { name: /^Alerts/ }).click();
  await page.getByRole("button", { name: "Play 6 weeks" }).click();
  await expect(page.getByText(/Six weeks later: \d+ new alert/)).toBeVisible({ timeout: 60_000 });
  await page.getByRole("button", { name: "Open high alert for Sharma Auto Components" }).click();
  await expect(page.getByText("Suggested next step")).toBeVisible();
  await snap(page, "alerts");

  // Portfolio and system.
  await page.getByRole("link", { name: "Portfolio" }).click();
  await snap(page, "portfolio-overview");
  await page.getByRole("tab", { name: /Band movement/ }).click();
  await snap(page, "portfolio-band-movement");
  await page.getByRole("tab", { name: /Exposure/ }).click();
  await snap(page, "portfolio-exposure");
  await page.getByRole("link", { name: "System" }).click();
  await page.waitForTimeout(10_500); // two live samples for the latency chart
  await snap(page, "system");

  // MSME owner, English then Hindi.
  await switchTo(page, "MSME Owner");
  await expect(page.getByRole("heading", { name: "My factory" })).toBeVisible();
  await snap(page, "msme-home");
  await page.getByRole("radio", { name: "हिन्दी" }).click();
  await snap(page, "msme-home-hindi");
  await page.getByRole("tab", { name: "योजना" }).click();
  await page.getByRole("checkbox").first().click();
  await snap(page, "msme-plan-hindi");
  await page.getByRole("tab", { name: "सहमति" }).click();
  await snap(page, "msme-consent-hindi");
  await page.getByRole("radio", { name: "English" }).click();

  // Risk head: governance.
  await switchTo(page, "Risk Head");
  await page.getByRole("link", { name: "Governance" }).click();
  await expect(page.getByText("AUC, out-of-time test")).toBeVisible();
  await snap(page, "governance-model-card");
  await page.getByRole("tab", { name: "Data & models" }).click();
  await expect(page.getByRole("heading", { name: "Data provenance" })).toBeVisible();
  await snap(page, "governance-data-models");
  await page.getByRole("tab", { name: "Audit trail" }).click();
  await page.getByRole("button", { name: "Verify chain" }).click();
  await expect(page.getByText("Chain intact")).toBeVisible();
  await snap(page, "governance-audit-trail");
  await page.getByRole("tab", { name: "Consent ledger" }).click();
  await snap(page, "governance-consent-ledger");
  await page.getByRole("tab", { name: "Responsible AI" }).click();
  await snap(page, "governance-responsible-ai");

  // Dark mode and the guided demo.
  await page.getByRole("link", { name: /^Alerts/ }).click();
  await page.getByRole("button", { name: "Switch to dark theme" }).click();
  await snap(page, "alerts-dark");
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await page.getByRole("button", { name: "Guided demo" }).click();
  await expect(page.getByRole("complementary", { name: "Guided demo" })).toBeVisible();
  await snap(page, "guided-demo");
});
