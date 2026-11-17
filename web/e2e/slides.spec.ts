import { expect, test, type Page } from "@playwright/test";
import { loginAs, setTheme } from "./helpers";

/** Deck and README screenshots at 1920x1080, light theme: `SLIDES=1 npx playwright test e2e/slides.spec.ts`.
 * Writes docs/media/slides/NN-name.png. Skipped in normal runs. */
test.skip(!process.env.SLIDES, "screenshots only on demand (SLIDES=1)");
test.use({ viewport: { width: 1920, height: 1080 } });

const OUT = "../docs/media/slides";
let n = 0;
const snap = async (page: Page, name: string) => {
  await page.waitForTimeout(400); // let charts finish drawing
  // No toasts on slides: hide them only while the picture is taken (the steps still wait on them).
  const hide = await page.addStyleTag({ content: "[data-sonner-toaster]{display:none!important}" });
  n += 1;
  await page.screenshot({ path: `${OUT}/${String(n).padStart(2, "0")}-${name}.png` });
  await hide.evaluate((el) => el.remove());
};
async function switchTo(page: Page, role: string) {
  await page.getByRole("button", { name: /Account menu/ }).click();
  await page.getByRole("menuitem", { name: new RegExp(role) }).click();
  await expect(page.getByText(new RegExp(`Now signed in as ${role}`))).toBeVisible();
}

test("deck screenshots", async ({ page }) => {
  test.setTimeout(180_000);
  expect((await page.request.post("/api/v1/demo/reset")).ok()).toBeTruthy();
  await page.goto("/login");
  await setTheme(page, "light");
  await page.reload();
  await snap(page, "login");

  await loginAs(page, "rm1");
  await expect(page.getByRole("row", { name: /Sharma Auto Components/ })).toBeVisible();
  await snap(page, "rm-console");
  await page.getByRole("row", { name: /Sharma Auto Components/ }).click();
  await page.getByRole("button", { name: "Request consent and pull data" }).click();
  await expect(page.getByText("Consent received")).toBeVisible();
  await page.getByRole("button", { name: "Run scoring" }).click();
  await expect(page.getByRole("heading", { name: "Top 5 reasons" })).toBeVisible();
  await snap(page, "score-and-reasons");
  await page.getByRole("button", { name: "Generate memo" }).click();
  await expect(page.getByRole("heading", { name: /Credit memo/ })).toBeVisible();
  await snap(page, "credit-memo");
  await page.getByRole("tab", { name: "What-if simulator" }).click();
  await page.getByLabel("Cheque/NACH bounces per month").fill("2");
  await expect(page.getByText(/Simulation only/)).toBeVisible();
  await snap(page, "what-if-simulator");

  await switchTo(page, "Credit Officer");
  await page.getByRole("row", { name: /Sharma Auto Components/ }).click();
  await page.getByRole("button", { name: "Review memo and decide" }).click();
  await page.getByLabel(/Comment/).fill("Approve per memo; strong order book and clean banking.");
  await page.getByRole("button", { name: "Review Key Fact Statement" }).click();
  await snap(page, "officer-decision-kfs");
  await page.getByRole("dialog", { name: "Confirm approval" }).getByRole("button", { name: "Confirm approval" }).click();
  await page.getByRole("button", { name: "Disburse via LOS" }).first().click();
  await expect(page.getByText(/Disbursed \(ref LOS-/)).toBeVisible();

  await switchTo(page, "Relationship Manager");
  await page.getByRole("link", { name: "Risk cockpit" }).click();
  await page.getByRole("button", { name: "Play story" }).first().click();
  await expect(page.getByText(/Six weeks later: \d+ new alert/)).toBeVisible({ timeout: 30_000 });
  await snap(page, "risk-cockpit");
  await page.getByRole("row", { name: "Open high alert for Sharma Auto Components" }).click();
  await expect(page.getByRole("dialog", { name: "Sharma Auto Components" })).toContainText("Order loss");
  await snap(page, "early-warning-alert");
  await page.keyboard.press("Escape");

  await switchTo(page, "MSME Owner");
  await page.getByRole("radio", { name: "हिन्दी" }).click();
  await expect(page.getByRole("heading", { name: /नमस्ते/ })).toBeVisible();
  await snap(page, "msme-app-hindi");
  await page.getByRole("tab", { name: "90 दिन की योजना" }).click();
  await snap(page, "msme-90-day-plan-hindi");
  await page.getByRole("radio", { name: "English" }).click();

  await switchTo(page, "Risk Head");
  await page.getByRole("link", { name: "Governance" }).click();
  await expect(page.getByText("AUC, out-of-time test")).toBeVisible();
  await snap(page, "governance-model");
  await page.getByRole("tab", { name: "Data & Models" }).click();
  await expect(page.getByRole("heading", { name: "Data provenance" })).toBeVisible();
  await snap(page, "governance-data-and-models");
  await page.getByRole("tab", { name: "Audit trail" }).click();
  await page.getByRole("button", { name: "Verify chain" }).click();
  await expect(page.getByText("Chain intact")).toBeVisible();
  await snap(page, "audit-chain-verified");
  await page.getByRole("button", { name: "Guided demo" }).click();
  await expect(page.getByRole("complementary", { name: "Guided demo" })).toBeVisible();
  await snap(page, "guided-demo");
});
