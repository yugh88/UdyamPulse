import type { Band, Severity } from "./format";

export type AppState = "APPLIED" | "CONSENTED" | "SCORED" | "MEMO_DRAFTED" | "DECIDED" | "DISBURSED" | "MONITORING";

export interface AppSummary {
  id: number;
  factory_id: string;
  name: string;
  sector: string;
  cluster: string;
  udyam_category: string;
  state: AppState;
  requested_amount: number;
  score: number | null;
  band: Band | null;
  pd_12m: number | null;
  decision: "APPROVED" | "REJECTED" | null;
  channel: string;
  created_at: string | null;
  last_activity: string | null;
  review_requested: boolean;
  /** Change tracking (from the API): set when the item changed after the user last looked at it. */
  changed_since_seen?: boolean;
  change_kind?: ChangeKind;
  score_trend?: { prev: number; delta: number; since: string } | null;
  prev_score?: number | null;
  score_delta?: number | null;
  next_step?: { text: string; owner_role: string | null; yours: boolean } | null;
}

export type ChangeKind = "new" | "updated" | null;

/** A stat tile from the API: the value, the previous value, the difference and the period compared. */
export interface Tile {
  value: number | null;
  prev_value: number | null;
  delta: number | null;
  period: string;
  good_when_up: boolean;
}

/** One entry of an application's change timeline (`GET /applications/{id}/changes`) or the live stream. */
export interface ChangeEvent {
  id: number;
  entity_type: string;
  entity_id: string;
  application_id?: number | null;
  event_type: string;
  summary: string;
  /** One short line of facts under the event (from the API), e.g. "Limit ₹40.0 L · MCLR + 2.25% · 3 policy citations". */
  detail?: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  actor: string | null;
  created_at: string;
  new?: boolean;
}

export interface AlertSignalChange {
  key: string;
  label: string;
  unit: string;
  good_when_up: boolean;
  before: number | null;
  after: number | null;
  before_period: string;
  after_period: string;
}

export interface AlertDetail {
  id: number;
  application_id: number;
  factory_id: string;
  name: string;
  cluster: string;
  sector: string;
  month: string;
  severity: Severity;
  rules: string[];
  reasons: string[];
  next_best_action: string;
  briefing: string;
  status: string;
  action_taken: string | null;
  outcome: string | null;
  raised_on: string;
  changed_since_seen: boolean;
  change_kind: ChangeKind;
  signals: AlertSignalChange[];
  score: { before: number | null; after: number | null; before_period?: string; after_period?: string } | null;
}

export interface AppStats {
  pending: number;
  needs_decision: number;
  scored_today: number;
  decisions: number;
  approval_rate: number | null;
  avg_decision_hours: number | null;
  review_requested: number;
  tiles: { waiting_on_you: Tile; avg_hours_to_memo: Tile; approval_rate_30d: Tile };
}

export interface Reason {
  feature: string;
  pillar: string;
  text: string;
  value: number | null;
  points: number;
  direction: "risk_up" | "risk_down";
}
export interface Pillar {
  pillar: string;
  label: string;
  prior_weight: number;
  points: number;
  health: number;
}
export interface ScoreDetail {
  factory_id: string;
  month: number;
  pd_12m: number;
  score: number;
  band: Band;
  reasons: Reason[];
  pillars: Pillar[];
  base_points: number;
}

export interface SignalPoint {
  month: string;
  eway_value: number;
  einvoice_value: number;
  open_po_value: number;
  aa_credits: number;
  aa_debits: number;
  avg_balance: number;
  bounces: number;
  kwh: number;
  rm_purchases: number;
  epfo_headcount: number;
  avg_days_to_pay: number;
  top_buyer_share: number;
  gst_filing_delay_days: number;
  gst_bank_mismatch: number;
}

export interface Consent {
  active: boolean;
  consent_id?: string;
  purpose?: string;
  fi_types?: string[];
  data_from?: string;
  data_to?: string;
  expires_on?: string;
  frequency?: string;
  status?: string;
}

export interface DataCheck {
  name: string;
  status: "pass" | "warn" | "fail";
  detail: string;
}

export interface Citation {
  section: string;
  title: string;
  excerpt: string;
  text: string;
}
export interface Memo {
  application_id: number;
  title: string;
  summary: string;
  recommended_limit: number;
  recommended_limit_display: string;
  requested_display: string;
  pricing_band: string;
  limit_workings: Record<string, string | number>;
  key_metrics: Record<string, string | number>;
  strengths: string[];
  risks: string[];
  mitigants: string[];
  covenants: string[];
  citations: Citation[];
  llm_provider: string;
  generated_in_ms?: number;
}

export interface PeerRow {
  metric: string;
  label: string;
  value: string;
  peer_median: string;
}

export interface AppDetail extends AppSummary {
  profile: { vintage_years: number; turnover_band: string; annual_turnover_cr: number; n_buyers: number; udyam_number: string };
  consent: Consent;
  data_checks: DataCheck[] | null;
  score_detail: ScoreDetail | null;
  memo: Memo | null;
  memo_pdf_url: string | null;
  pricing_band: string | null;
  recommended_limit: number | null;
  decision_comment: string | null;
  decided_by: string | null;
  decided_at: string | null;
  kfs: Record<string, string> | null;
  sanctioned_limit: number | null;
  disbursement_ref: string | null;
  disbursed_on: string | null;
  signals: SignalPoint[];
  score_history: { month: string; score: number; band: Band }[];
  stress_start: { month: string; severity: Severity } | null;
  peers: { cluster: string; peer_count: number; month: string; rows: PeerRow[] } | null;
  alerts: { id: number; month: string; severity: Severity; status: string; next_best_action: string }[];
  review_note: string | null;
  ai_label: string;
}

export interface Lever {
  key: string;
  label: string;
  unit: "%" | "pp" | "days" | "count";
  min: number;
  max: number;
  step: number;
  help: string;
}
export interface Simulation {
  simulation: true;
  label: string;
  as_of: string;
  window_months: number;
  adjustments: Record<string, number>;
  base: { score: number; band: Band; pd_12m: number };
  simulated: { score: number; band: Band; pd_12m: number; reasons: Reason[]; pillars: Pillar[] };
  delta: number;
}

export interface FactoryHit {
  factory_id: string;
  name: string;
  sector_label: string;
  cluster: string;
  udyam_category: string;
  turnover_band: string;
  loan_requested_inr: number;
}

export interface PortfolioAccount {
  application_id: number;
  factory_id: string;
  name: string;
  sector: string;
  cluster: string;
  udyam_category: string;
  exposure: number;
  score: number;
  band: Band;
  pd_12m: number;
  trend_3m: number;
  sparkline: number[];
  open_alerts: number;
  max_severity: Severity | null;
  consent_active: boolean;
}
export interface Portfolio {
  as_of: string;
  data_month: string;
  kpis: {
    accounts: number;
    avg_score: number | null;
    exposure: number;
    alerts_by_severity: Record<Severity, number>;
    expected_slippage_avoided: number;
    slippage_formula: string;
  };
  heatmap: { cluster: string; sector: string; accounts: number; avg_score: number; alerts: number }[];
  accounts: PortfolioAccount[];
}

export interface AlertEvent {
  id: number;
  month: string;
  severity: Severity;
  rules: string[];
  reasons: string[];
  status: string;
  action_taken: string | null;
  raised_on: string;
}
export interface AlertRow extends AlertEvent {
  application_id: number;
  factory_id: string;
  name: string;
  cluster: string;
  sector: string;
  next_best_action: string;
  briefing: string;
  action_note: string | null;
  actioned_by: string | null;
  outcome: string | null;
  owner: string | null;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
  days_open: number;
  exposure: number;
  timeline: AlertEvent[];
  changed_since_seen?: boolean;
  change_kind?: ChangeKind;
}

export interface Migration {
  from_month: string;
  to_month: string;
  bands: Band[];
  matrix: Record<Band, Record<Band, number>>;
  accounts: number;
  downgrades: number;
  upgrades: number;
  movers: { application_id: number; factory_id: string; name: string; from_band: Band; to_band: Band; from_score: number; to_score: number; direction: "up" | "down" }[];
}

export interface StaffUser {
  username: string;
  display_name: string;
  role: string;
}

export interface AdvanceResult {
  sim_date: string;
  data_month: string;
  checked: number;
  new_alerts: number[];
  blocked: number[];
}
