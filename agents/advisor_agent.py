"""MSME advisor agent: for rejected or watch-band units, turns SHAP reasons + the cash-flow forecast
into a 90-day improvement plan in simple language, with an optional Hindi summary."""

from __future__ import annotations

from agents.base import Agent
from agents.policy_engine import inr
from agents.providers.llm import get_llm
from ml.forecast import forecast_cashflow

ACTIONS = {
    "order_book": [
        "Share confirmed purchase orders with the bank every month so your order book is visible.",
        "Add at least two new buyers through GeM or ONDC so one buyer slowing down hurts less.",
    ],
    "cash_flow": [
        "Keep a buffer of at least one month of loan instalments in your account to avoid cheque/NACH bounces.",
        "Route payments from your biggest buyers into this account so your bank inflows show your real sales.",
    ],
    "production": [
        "Plan raw-material purchases against confirmed orders to protect cash.",
        "Keep your electricity connection and ERP stock records up to date; they prove you are producing.",
    ],
    "receivables": [
        "Register on a TReDS platform and discount bills from buyers who pay after 45 days.",
        "For bills overdue beyond 45 days, use the MSME Samadhaan portal under the MSMED Act.",
    ],
    "compliance": [
        "File GSTR-3B by the 20th every month; set a reminder 3 days before.",
        "Keep EPFO filings regular so your workforce record stays continuous.",
    ],
}
HINDI = {
    "order_book": "हर महीने अपने पक्के ऑर्डर बैंक के साथ साझा करें और GeM/ONDC से नए खरीदार जोड़ें।",
    "cash_flow": "खाते में कम से कम एक महीने की किस्त जितना बैलेंस रखें ताकि चेक/NACH बाउंस न हो।",
    "production": "कच्चा माल पक्के ऑर्डर के हिसाब से खरीदें और बिजली व स्टॉक रिकॉर्ड अपडेट रखें।",
    "receivables": "TReDS पर पंजीकरण करें और 45 दिन से ज़्यादा देर से भुगतान करने वाले बिल डिस्काउंट कराएँ।",
    "compliance": "GSTR-3B हर महीने 20 तारीख तक भरें और EPFO फाइलिंग नियमित रखें।",
}
PHASES = ["Days 1–30", "Days 31–60", "Days 61–90"]


class AdvisorAgent(Agent):
    name = "msme_advisor_agent"

    def plan(self, score: dict, history, target: int = 650) -> dict:
        forecast = self.tool("forecast_cashflow", forecast_cashflow, audit_output=lambda r: r["forecast"],
                             **{"history": history, "periods": 3})
        hurting = [r for r in score["reasons"] if r["direction"] == "risk_up"]
        pillars_sorted = sorted(score["pillars"], key=lambda p: p["points"])
        focus = list(dict.fromkeys([r["pillar"] for r in hurting] + [p["pillar"] for p in pillars_sorted]))[:3]
        recoverable = round(-sum(r["points"] for r in hurting), 1)

        steps = []
        for i, pillar in enumerate(focus):
            for j, text in enumerate(ACTIONS[pillar]):
                steps.append({"phase": PHASES[min(i + j, 2)], "pillar": pillar, "action": text})
        steps.sort(key=lambda s: PHASES.index(s["phase"]))
        if forecast["negative_months"]:
            steps.insert(0, {"phase": PHASES[0], "pillar": "cash_flow",
                             "action": f"Cash may run short in {', '.join(forecast['negative_months'])}: "
                                       "talk to your RM early about a short-term limit review."})

        gap = target - score["score"]
        draft = (
            f"Your loan-readiness score is {score['score']}. "
            + (f"You need {gap} more points to reach {target}. " if gap > 0 else f"You are above {target}. ")
            + (f"The issues below are costing you about {recoverable} points. " if recoverable > 0 else "")
            + "Focus on: " + "; ".join(r["text"] for r in hurting[:3]) + "."
        ) if hurting else f"Your loan-readiness score is {score['score']}. Keep your current discipline going."
        facts = {"score": score["score"], "target": target, "gap": gap, "recoverable_points": recoverable,
                 "reasons": [r["text"] for r in hurting[:3]]}
        summary = self.tool("llm.write", get_llm().write,
                            **{"task": "MSME-friendly plan summary", "facts": facts, "draft": draft})
        hindi = " ".join(HINDI[p] for p in focus)
        return {
            "score": score["score"],
            "band": score["band"],
            "target": target,
            "points_to_target": max(gap, 0),
            "recoverable_points": recoverable,
            "summary": summary,
            "hindi_summary": f"आपका लोन-रेडीनेस स्कोर {score['score']} है। अगले 90 दिनों में: {hindi}",
            "steps": steps,
            "forecast": forecast,
            "avg_monthly_credits": inr(forecast["avg_monthly_credits"]),
        }
