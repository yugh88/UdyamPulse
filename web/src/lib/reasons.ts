import type { Reason } from "./types";

/**
 * Score reasons in words an owner or a branch officer would use. The model's 60+ features are grouped into a few
 * themes (orders, power use, buyers paying, ...): several features of one theme are one reason, never a repeated
 * title. Each theme has a title for "helps" and one for "hurts", in English and Hindi, and the detail line restates
 * the measured value without jargon (no HHI, CV, EPFO, GSTR-3B or NACH).
 */
type Lang = "en" | "hi";
interface Theme {
  en: [helps: string, hurts: string];
  hi: [helps: string, hurts: string];
}

const THEMES: Record<string, Theme> = {
  bounces: { en: ["No payment bounces", "Payments are bouncing"], hi: ["कोई भुगतान बाउंस नहीं", "भुगतान बाउंस हो रहे हैं"] },
  gst: { en: ["GST filed on time", "GST filed late"], hi: ["GST समय पर भरा", "GST देर से भरा"] },
  mismatch: { en: ["Sales match bank deposits", "Sales and bank deposits differ"], hi: ["बिक्री और बैंक जमा मेल खाते हैं", "बिक्री और बैंक जमा में फ़र्क है"] },
  buyers: { en: ["Sales spread across buyers", "One buyer gives most of your sales"], hi: ["बिक्री कई खरीदारों में बँटी है", "ज़्यादातर बिक्री एक खरीदार से"] },
  paytime: { en: ["Buyers pay on time", "Buyers are paying slowly"], hi: ["खरीदार समय पर भुगतान करते हैं", "खरीदार देर से भुगतान कर रहे हैं"] },
  staff: { en: ["Workforce is steady", "Workforce is shrinking"], hi: ["कर्मचारी संख्या स्थिर है", "कर्मचारी घट रहे हैं"] },
  age: { en: ["Established business", "Young business"], hi: ["पुराना, जमा हुआ कारोबार", "नया कारोबार"] },
  power: { en: ["Factory is running steadily", "Power use is falling"], hi: ["फ़ैक्टरी लगातार चल रही है", "बिजली की खपत घट रही है"] },
  rawmat: { en: ["Buying raw material steadily", "Raw-material buying is down"], hi: ["कच्चा माल लगातार ख़रीदा जा रहा है", "कच्चे माल की ख़रीद घटी है"] },
  orders: { en: ["Orders are growing", "Orders are slowing"], hi: ["ऑर्डर बढ़ रहे हैं", "ऑर्डर धीमे पड़ रहे हैं"] },
  orderbook: { en: ["Plenty of orders in hand", "Few orders in hand"], hi: ["हाथ में काफ़ी ऑर्डर हैं", "हाथ में कम ऑर्डर हैं"] },
  steady: { en: ["Sales are steady month to month", "Sales swing a lot month to month"], hi: ["हर महीने बिक्री स्थिर रहती है", "हर महीने बिक्री बहुत ऊपर-नीचे होती है"] },
  dispatch: { en: ["Goods shipped match invoices", "Goods shipped don't match invoices"], hi: ["भेजा गया माल बिलों से मेल खाता है", "भेजा गया माल बिलों से मेल नहीं खाता"] },
  cashleft: { en: ["Money left over each month", "Little money left each month"], hi: ["हर महीने पैसा बचता है", "हर महीने कम पैसा बचता है"] },
  inflows: { en: ["Steady money coming in", "Less money coming in"], hi: ["पैसा लगातार आ रहा है", "कम पैसा आ रहा है"] },
  balance: { en: ["Bank balance is healthy", "Bank balance is falling"], hi: ["बैंक बैलेंस अच्छा है", "बैंक बैलेंस घट रहा है"] },
  cushion: { en: ["Good cash cushion", "Thin cash cushion"], hi: ["अच्छा नकद सहारा", "कम नकद सहारा"] },
  spending: { en: ["Spending is under control", "Spending is close to income"], hi: ["ख़र्च काबू में है", "ख़र्च लगभग कमाई जितना है"] },
  loansize: { en: ["Loan size fits the business", "Loan is large for the business"], hi: ["लोन कारोबार के हिसाब से ठीक है", "लोन कारोबार के हिसाब से बड़ा है"] },
  compliance: { en: ["Records in order", "Compliance slips"], hi: ["काग़ज़ात ठीक हैं", "नियम पालन में चूक"] },
};

/** Which theme a model feature belongs to. */
export function themeOf(feature: string, pillar = ""): string {
  const f = feature;
  if (f.startsWith("bounces")) return "bounces";
  if (f.startsWith("gst_bank_mismatch")) return "mismatch";
  if (f.startsWith("gst_")) return "gst";
  if (f.startsWith("top_buyer_share") || f === "buyer_hhi" || f === "n_buyers") return "buyers";
  if (f.startsWith("days_to_pay")) return "paytime";
  if (f.startsWith("epfo")) return "staff";
  if (f === "vintage_years") return "age";
  if (f.startsWith("kwh")) return "power";
  if (f.startsWith("rm_")) return "rawmat";
  if (f.startsWith("po_cover")) return "orderbook";
  if (f === "eway_to_einvoice_ratio") return "dispatch";
  if (f.endsWith("_cv_6") || f.endsWith("_cv_12")) return f.startsWith("balance") ? "balance" : "steady";
  if (f.startsWith("eway") || f.startsWith("einvoice")) return "orders";
  if (f.startsWith("net_inflow")) return "cashleft";
  if (f.startsWith("credits")) return "inflows";
  if (f.startsWith("balance_to_debits")) return "cushion";
  if (f.startsWith("balance")) return "balance";
  if (f.startsWith("debits_to_credits")) return "spending";
  if (f === "loan_to_turnover") return "loansize";
  return { order_book: "orders", cash_flow: "inflows", production: "power", receivables: "paytime" }[pillar] ?? "compliance";
}

const n0 = (v: number) => Math.round(v).toLocaleString("en-IN");
const p0 = (v: number) => `${Math.round(Math.abs(v) * 100)}%`;
const upDown = (v: number) => (v >= 0 ? "up" : "down");

function windowOf(f: string): string {
  if (f.endsWith("_1v3") || f.endsWith("_1v1") || f.endsWith("_1v6")) return f.endsWith("_1v6") ? "the 6-month average" : "the last 3 months";
  if (f.endsWith("_1v2")) return "8 weeks ago";
  if (f.endsWith("_3v12")) return "the past year";
  if (f.endsWith("_yoy")) return "a year ago";
  return "";
}
function periodOf(f: string): string {
  const m = f.match(/_(\d+)$/);
  if (!m) return "";
  return m[1] === "1" ? "this month" : `in ${m[1]} months`;
}

/** The measured value in plain words (English). Falls back to the model's own text without its jargon. */
export function plainDetail(r: Reason): string {
  const f = r.feature;
  const v = r.value;
  if (v == null || Number.isNaN(v)) return dejargon(r.text);
  if (f.startsWith("bounces")) return v < 0.5 ? `No cheque or auto-debit bounces ${periodOf(f)}` : `${n0(v)} cheque or auto-debit bounces ${periodOf(f)}`;
  if (f.startsWith("gst_late_months")) return v < 0.5 ? `No late GST returns ${periodOf(f)}` : `${n0(v)} late GST returns ${periodOf(f)}`;
  if (f === "gst_consecutive_late") return v < 0.5 ? "No late GST returns in a row" : `${n0(v)} late GST returns in a row`;
  if (f.startsWith("gst_delay")) return v < 0.5 ? "GST return filed on time" : `GST return filed ${n0(v)} days late${f.endsWith("_3") ? " on average" : ""}`;
  if (f.startsWith("gst_bank_mismatch")) return `Sales on GST and money in the bank differ by ${p0(v)}`;
  if (f.startsWith("top_buyer_share_chg")) return `Top buyer's share of sales is ${upDown(v)} ${p0(v)} vs the 6-month average`;
  if (f.startsWith("top_buyer_share")) return `Top buyer gives ${p0(v)} of sales`;
  if (f === "buyer_hhi") return v > 0.25 ? "Most sales come from a few buyers" : "Sales are spread across many buyers";
  if (f === "n_buyers") return `${n0(v)} buyers bought this month`;
  if (f === "days_to_pay_slope_6") return `Time to get paid is ${v >= 0 ? "rising" : "falling"} by ${n0(Math.abs(v))} days a month`;
  if (f.startsWith("days_to_pay_chg")) return `Buyers take ${n0(Math.abs(v))} ${v >= 0 ? "more" : "fewer"} days to pay than ${windowOf(f)}`;
  if (f.startsWith("days_to_pay")) return `Buyers pay in ${n0(v)} days on average`;
  if (f === "epfo_drop_months_6") return v < 0.5 ? "Staff numbers did not fall in the last 6 months" : `Staff numbers fell in ${n0(v)} of the last 6 months`;
  if (f.startsWith("epfo")) return `Staff on the payroll ${upDown(v)} ${p0(v)} vs ${windowOf(f)}`;
  if (f === "vintage_years") return `${n0(v)} years in business`;
  if (f === "kwh_vs_sector") return `Uses ${p0(v)} ${v >= 0 ? "more" : "less"} power than similar factories`;
  if (f === "kwh_per_lakh_3") return `${n0(v)} units of power per ₹1 lakh of sales`;
  if (f === "kwh_cv_6") return v > 0.25 ? "Power use swings a lot month to month" : "Power use is steady month to month";
  if (f === "kwh_slope_6") return `Power use trend ${upDown(v)} ${p0(v)} a month`;
  if (f.startsWith("kwh")) return `Electricity use ${upDown(v)} ${p0(v)} vs ${windowOf(f)}`;
  if (f.startsWith("rm_ratio")) return `Raw material is ${p0(v)} of sales`;
  if (f.startsWith("rm_")) return `Raw-material buying ${upDown(v)} ${p0(v)} vs ${windowOf(f)}`;
  if (f === "po_cover_months") return `Open orders cover ${v.toFixed(1)} months of sales`;
  if (f.startsWith("po_cover")) return `Open orders ${upDown(v)} ${p0(v)} vs the last 3 months`;
  if (f === "eway_to_einvoice_ratio") return `Goods shipped match ${p0(v)} of invoiced sales`;
  if (f.endsWith("_cv_6") || f.endsWith("_cv_12")) return `Month-to-month swing of ${p0(v)}`;
  if (f === "einvoice_value_slope_6") return `Sales trend ${upDown(v)} ${p0(v)} a month over 6 months`;
  if (f.startsWith("eway_count") || f.startsWith("einvoice_count")) return `Number of shipments ${upDown(v)} ${p0(v)} vs ${windowOf(f)}`;
  if (f.startsWith("eway")) return `Goods shipped ${upDown(v)} ${p0(v)} vs ${windowOf(f)}`;
  if (f.startsWith("einvoice")) return `Invoiced sales ${upDown(v)} ${p0(v)} vs ${windowOf(f)}`;
  if (f.startsWith("net_inflow")) return `${p0(v)} of the money coming in is left after paying out (${periodOf(f).replace(/^in /, "")})`;
  if (f.startsWith("credits")) return `Money coming into the bank ${upDown(v)} ${p0(v)} vs ${windowOf(f)}`;
  if (f.startsWith("balance_to_debits")) return `Bank balance covers ${p0(v)} of a month's spending`;
  if (f.startsWith("balance_chg_1v1")) return `Average bank balance ${upDown(v)} ${p0(v)} in 30 days`;
  if (f.startsWith("balance")) return `Average bank balance ${upDown(v)} ${p0(v)} vs ${windowOf(f)}`;
  if (f.startsWith("debits_to_credits")) return `Spends ${p0(v)} of what comes in`;
  if (f === "loan_to_turnover") return `Loan asked is ${p0(v)} of a year's sales`;
  return dejargon(r.text);
}

/** Replaces model jargon in free text (memo lines) with plain words. */
export function dejargon(text: string): string {
  return text
    .replace(/\s*\((?:[+−-]?\d+(?:\.\d+)?) points\)/g, "")
    .replace(/Buyer concentration index \(HHI\) at ([\d.]+)/g, (_, x) => (Number(x) > 0.25 ? "Most sales come from a few buyers" : "Sales are spread across many buyers"))
    .replace(/\s*\(HHI\)/g, "")
    .replace(/\((\d+m) CV\)/g, "")
    .replace(/EPFO headcount/g, "staff on the payroll")
    .replace(/GSTR-3B/g, "GST return")
    .replace(/cheque\/NACH/g, "cheque or auto-debit")
    .replace(/E-way bill value/g, "Goods shipped")
    .replace(/E-invoice value/g, "Invoiced sales")
    .replace(/\(3m\)/g, "(3 months)")
    .replace(/\((\d+)m\)/g, "($1 months)")
    .replace(/kWh/g, "electricity")
    .replace(/\s{2,}/g, " ")
    .trim();
}

export interface PlainReason {
  key: string;
  title: string;
  detail: string;
  points: number;
  helps: boolean;
  pillar: string;
}

/** Reasons grouped by theme and direction: one row per theme, points summed, the strongest reason's detail kept. */
export function plainReasons(reasons: Reason[], lang: Lang = "en"): PlainReason[] {
  const groups = new Map<string, { best: Reason; points: number }>();
  for (const r of reasons) {
    const helps = r.points >= 0;
    const key = `${themeOf(r.feature, r.pillar)}:${helps ? "+" : "-"}`;
    const g = groups.get(key);
    if (!g) groups.set(key, { best: r, points: r.points });
    else {
      g.points += r.points;
      if (Math.abs(r.points) > Math.abs(g.best.points)) g.best = r;
    }
  }
  return [...groups.entries()]
    .map(([key, { best, points }]) => {
      const helps = points >= 0;
      const theme = THEMES[key.split(":")[0]!] ?? THEMES.compliance!;
      return { key, title: theme[lang][helps ? 0 : 1], detail: plainDetail(best), points, helps, pillar: best.pillar };
    })
    .sort((a, b) => Math.abs(b.points) - Math.abs(a.points));
}
