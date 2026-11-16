/** Feature-to-regulation mapping shown to the Risk Head. Mirrors docs/COMPLIANCE.md. */
export interface Control {
  expectation: string;
  control: string;
  evidence: string;
  status: "implemented" | "stub" | "production";
}

export const COMPLIANCE: { framework: string; note: string; controls: Control[] }[] = [
  {
    framework: "RBI Digital Lending Directions, 2025",
    note: "UdyamPulse acts as a technology service provider to the regulated lender.",
    controls: [
      {
        expectation: "The regulated entity owns the credit decision",
        control: "Only a credit officer can approve or reject, with a mandatory comment. The system only recommends.",
        evidence: "Decision panel · role check on the decision endpoint",
        status: "implemented",
      },
      {
        expectation: "Key Fact Statement before execution",
        control: "KFS preview before the officer confirms, and a KFS on approval. APR and fees come from the lender's LOS.",
        evidence: "Application → Memo and decision",
        status: "stub",
      },
      {
        expectation: "Disbursal directly to the borrower's account",
        control: "The LOS stub records direct disbursal with no pass-through account. UdyamPulse never holds funds.",
        evidence: "Audit trail: los_stub.disburse",
        status: "stub",
      },
      {
        expectation: "Collect only necessary data; no biometrics",
        control: "The consent artefact lists the exact data types. The MSME app lists what is never collected.",
        evidence: "MSME app → My data",
        status: "implemented",
      },
      {
        expectation: "Data stored in India",
        control: "The API refuses to start if the configured region is outside India.",
        evidence: "Start-up residency check",
        status: "implemented",
      },
      {
        expectation: "Grievance redressal stays with the lender",
        control: "The KFS names the lender's nodal officer and the RBI Integrated Ombudsman.",
        evidence: "Key Fact Statement",
        status: "stub",
      },
    ],
  },
  {
    framework: "DPDP Act 2023 and DPDP Rules 2025",
    note: "The MSME owner is the data principal; the lender is the data fiduciary.",
    controls: [
      {
        expectation: "Notice stating the purpose",
        control: "Purpose, data types and expiry are shown before and after consent, in English and Hindi.",
        evidence: "Consent card · MSME app → My data",
        status: "implemented",
      },
      {
        expectation: "Consent ledger",
        control: "Append-only ledger of grants, data pulls, blocked pulls, revocations, expiries and deletion jobs.",
        evidence: "Governance → Consent ledger",
        status: "implemented",
      },
      {
        expectation: "Withdrawal as easy as giving consent",
        control: "Revoke in the MSME app with one confirm step. Every later pull is blocked.",
        evidence: "Test: revoking consent blocks new pulls",
        status: "implemented",
      },
      {
        expectation: "Retention limits",
        control: "Stored snapshots are deleted on revocation; the retention policy is shown to the owner.",
        evidence: "Ledger event: DELETION_JOB",
        status: "implemented",
      },
      { expectation: "Data-principal rights", control: "Download my data and an erasure request, both audited.", evidence: "MSME app → My data", status: "stub" },
    ],
  },
  {
    framework: "RBI FREE-AI principles",
    note: "Framework for Responsible and Ethical Enablement of AI.",
    controls: [
      {
        expectation: "Explainability",
        control: "Every score has its top five reasons in plain language and pillar contributions in score points.",
        evidence: "Application → Assessment",
        status: "implemented",
      },
      {
        expectation: "Human in the loop",
        control: "Recommendations only. The decision endpoint is restricted to credit officers.",
        evidence: "Decision panel",
        status: "implemented",
      },
      {
        expectation: "Disclosure of AI use",
        control: "Every AI output carries an AI-generated label. The KFS states AI-assisted analysis was used.",
        evidence: "Memo banner · alert briefing",
        status: "implemented",
      },
      {
        expectation: "Right to challenge",
        control: "The MSME can request a human review; the case is flagged in the console.",
        evidence: "MSME app → Home",
        status: "implemented",
      },
      {
        expectation: "No invented facts",
        control: "A number guard rejects LLM text containing any number not present in the structured facts.",
        evidence: "Test: invented number falls back to template",
        status: "implemented",
      },
      {
        expectation: "Model inventory and card",
        control: "Model card with data, metrics, limitations, fairness and drift.",
        evidence: "Governance → Model",
        status: "implemented",
      },
      {
        expectation: "AI usage transparency",
        control: "Each writer call is logged with template id, provider, latency and a token estimate.",
        evidence: "Governance → AI usage",
        status: "implemented",
      },
      {
        expectation: "Audit trail",
        control: "Every API action and agent tool call is logged with masked inputs and a hash of the output.",
        evidence: "Governance → Audit trail",
        status: "implemented",
      },
    ],
  },
];
