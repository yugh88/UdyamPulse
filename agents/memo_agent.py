"""Credit-memo agent: retrieves policy clauses (RAG), injects every number from structured facts,
lets the LLM write prose only (guarded), and exports a PDF."""

from __future__ import annotations

import re
import time
from pathlib import Path

from agents.base import Agent
from agents.policy_engine import assess_limit, inr
from agents.providers.llm import get_llm
from agents.providers.search import get_search
from api.models.db import Application
from core.settings import get_settings
from core.timeline import month_label

_SECTION_REF = re.compile(r"§(\d+\.\d+)")
AI_LABEL = "AI-generated recommendation · final decision by credit officer"

MITIGANTS = {
    "order_book": "Monthly e-way bill and purchase-order tracking through UdyamPulse early-warning monitoring [§8.1]",
    "cash_flow": "Route top-buyer receivables through an escrow / TReDS arrangement and monitor bounces monthly [§7.4]",
    "production": "Quarterly ERP-generated stock statements to confirm production levels [§7.5]",
    "receivables": "Discount buyer bills older than 45 days through TReDS [§7.3]",
    "compliance": "Covenant on timely GSTR-3B filing with review on two consecutive delays [§7.2]",
}
RAG_QUERIES = {
    "order_book": "falling orders e-way bills monitoring early warning",
    "cash_flow": "cheque NACH returns banking discipline escrow",
    "production": "stock statements ERP production electricity",
    "receivables": "buyer concentration receivables TReDS 45 days",
    "compliance": "GST filing late consecutive review",
}


def build_facts(app: Application, profile: dict, history, score: dict) -> dict:
    last12 = history.tail(12)
    annual = float(last12["gst_turnover"].sum() * 12 / max(len(last12), 1))
    top_share = float(history["top_buyer_share"].iloc[-1])
    lim = assess_limit(annual, app.requested_amount, score["score"], score["band"], top_share)
    eway3, eway12 = history["eway_value"].tail(3).mean(), last12["eway_value"].mean()
    kwh3, kwh12 = history["kwh"].tail(3).mean(), last12["kwh"].mean()
    on_time = int((last12["gst_filing_delay_days"] == 0).sum())
    return {
        "factory": {
            "factory_id": profile["factory_id"], "name": profile["name"], "sector": profile["sector_label"],
            "cluster": profile["cluster"], "udyam_category": profile["udyam_category"],
            "vintage_years": int(round(profile["vintage_years"])), "turnover_band": profile["turnover_band"],
        },
        "as_of": month_label(score["month"]),
        "score": score["score"],
        "band": score["band"],
        "pd_12m": f"{score['pd_12m'] * 100:.2f}%",
        "reasons": [{"text": r["text"], "points": r["points"], "pillar": r["pillar"], "direction": r["direction"]}
                    for r in score["reasons"]],
        "pillars": [{"label": p["label"], "points": p["points"], "pillar": p["pillar"]} for p in score["pillars"]],
        "metrics": {
            "annual_gst_turnover": inr(annual),
            "avg_monthly_eway_value_3m": inr(eway3),
            "eway_trend_3m_vs_12m": f"{(eway3 / eway12 - 1) * 100:+.0f}%",
            "kwh_trend_3m_vs_12m": f"{(kwh3 / kwh12 - 1) * 100:+.0f}%",
            "bounces_12m": int(last12["bounces"].sum()),
            "top_buyer_share": f"{top_share * 100:.0f}%",
            "days_to_pay": f"{history['avg_days_to_pay'].iloc[-1]:.0f} days",
            "gst_on_time_12m": f"{on_time} of {len(last12)}",
        },
        "limit": {
            "requested": inr(lim.requested),
            "turnover_limit": inr(lim.turnover_limit),
            "turnover_share": "20%",
            "band_factor": f"{lim.band_factor * 100:.0f}%",
            "concentration_haircut": "15%" if lim.concentration_haircut else "none",
            "recommended": inr(lim.recommended_limit),
            "recommended_inr": lim.recommended_limit,
        },
        "pricing_band": lim.pricing_band,
        "policy_sections": lim.citations,
        "checks": app.data_checks or [],
    }


class MemoAgent(Agent):
    name = "credit_memo_agent"

    def draft(self, app: Application, profile: dict, history, score: dict) -> dict:
        t0 = time.perf_counter()
        facts = self.tool("build_facts", build_facts, audit_app=app.id,
                          **{"app": app, "profile": profile, "history": history, "score": score})
        f, m, lim = facts["factory"], facts["metrics"], facts["limit"]
        search = get_search()

        risk_up = [r for r in facts["reasons"] if r["direction"] == "risk_up"]
        risk_down = [r for r in facts["reasons"] if r["direction"] == "risk_down"]
        risk_pillars = list(dict.fromkeys(r["pillar"] for r in risk_up))

        best = max(facts["pillars"], key=lambda p: p["points"])
        worst = min(facts["pillars"], key=lambda p: p["points"])
        strengths = [f"{r['text']} ({r['points']:+} points)" for r in risk_down]
        strengths.append(f"{best['label']} contributes {best['points']:+} points to the score [§3.1]")
        if m["bounces_12m"] == 0:
            strengths.append(f"Clean banking conduct: {m['bounces_12m']} cheque/NACH bounces in 12 months [§7.4]")
        risks = [f"{r['text']} ({r['points']:+} points)" for r in risk_up]
        if lim["concentration_haircut"] != "none":
            risks.append(f"Top buyer is {m['top_buyer_share']} of sales; limit reduced by {lim['concentration_haircut']} [§4.3]")
        else:
            risks.append(f"Largest buyer accounts for {m['top_buyer_share']} of sales [§7.3]")
        risks += [f"Data check — {c['name']}: {c['detail']}" for c in facts["checks"] if c["status"] != "pass"]
        mitigants = [MITIGANTS[p] for p in risk_pillars] or [MITIGANTS["order_book"]]
        covenants = [
            "Keep Account Aggregator and GST consent active for monitoring through the tenor [§7.1]",
            "File GSTR-3B by the due date every month [§7.2]",
            "Not more than one cheque/NACH return in any month; route business credits through the Bank [§7.4]",
            "Notify the Bank on loss of any buyer contributing more than 25% of sales [§7.3]",
        ]

        # Retrieval: deterministic clauses for limit/pricing, semantic search per risk theme, and every
        # clause referenced in the bullets, so each [§x.y] in the memo resolves to retrieved policy text.
        sections = ["3.2", *facts["policy_sections"], "9.2"]
        for p in risk_pillars[:2]:
            hits = self.tool("policy_search", search.search, audit_app=app.id,
                             audit_output=lambda cs: [c.section for c in cs], **{"query": RAG_QUERIES[p], "k": 2})
            sections += [h.section for h in hits]
        sections += _SECTION_REF.findall(" ".join(strengths + risks + mitigants + covenants))
        citations = []
        for sec in dict.fromkeys(sections):
            c = search.get(sec)
            if c:
                citations.append({"section": c.section, "title": c.title, "excerpt": c.text[:240], "text": c.text})
        facts["citations"] = [{"section": c["section"], "title": c["title"]} for c in citations]

        decision_word = {"APPROVE": "approval", "WATCH": "approval with mitigants and a reduced limit",
                         "HIGH_RISK": "decline with an improvement plan"}[facts["band"]]
        summary_draft = (
            f"{f['name']} is a {f['vintage_years']}-year-old {f['udyam_category']} {f['sector'].lower()} unit in "
            f"{f['cluster']} with annual GST turnover of {m['annual_gst_turnover']}. As of {facts['as_of']} it scores "
            f"{facts['score']} ({facts['band'].replace('_', ' ')}) on the Factory Health Score, a 12-month PD of "
            f"{facts['pd_12m']} [§3.2]. The strongest pillar is {best['label'].lower()} ({best['points']:+} points); "
            f"the weakest is {worst['label'].lower()} ({worst['points']:+} points). Against a request of "
            f"{lim['requested']}, the policy limit is {lim['recommended']} at {facts['pricing_band']} [§4.1][§5.2]. "
            f"Recommendation: {decision_word}."
        )
        summary = self.tool("llm.write", get_llm().write, audit_app=app.id,
                            **{"task": "credit memo executive summary", "facts": facts, "draft": summary_draft})

        memo = {
            "application_id": app.id,
            "title": f"Credit memo — {f['name']}, {f['cluster']}",
            "summary": summary,
            "recommended_limit": lim["recommended_inr"],
            "recommended_limit_display": lim["recommended"],
            "requested_display": lim["requested"],
            "pricing_band": facts["pricing_band"],
            "limit_workings": lim,
            "key_metrics": m,
            "strengths": strengths,
            "risks": risks,
            "mitigants": mitigants,
            "covenants": covenants,
            "citations": citations,
            "facts": facts,
            "llm_provider": get_llm().name,
            "ai_label": AI_LABEL,
        }
        memo["pdf_path"] = self.tool("render_pdf", render_pdf, audit_app=app.id,
                                     audit_output=lambda p: str(p), **{"memo": memo})
        memo["generated_in_ms"] = int((time.perf_counter() - t0) * 1000)
        return memo


def _pdf_text(s: str) -> str:
    """Core PDF fonts lack ₹ and arrows; substitute readable ASCII."""
    return (s.replace("₹", "Rs. ").replace("↓", "down ").replace("↑", "up ").replace("−", "-")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render_pdf(memo: dict) -> str:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import ListFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    out_dir = get_settings().var_dir / "memos"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"memo_{memo['application_id']}.pdf"
    styles = getSampleStyleSheet()
    navy = colors.HexColor("#0B1033")
    h = ParagraphStyle("h", parent=styles["Heading2"], textColor=navy, spaceBefore=8, spaceAfter=4)
    body = ParagraphStyle("b", parent=styles["BodyText"], fontSize=9.5, leading=13)
    small = ParagraphStyle("s", parent=body, fontSize=8, textColor=colors.HexColor("#E5397A"))
    f = memo["facts"]

    story = [
        Paragraph(_pdf_text(memo["title"]), ParagraphStyle("t", parent=styles["Title"], textColor=navy, fontSize=16)),
        Paragraph(_pdf_text(memo["ai_label"]), small),
        Spacer(1, 4 * mm),
    ]
    grid = [
        ["Factory Health Score", f"{f['score']} ({f['band'].replace('_', ' ')})", "12-month PD", f["pd_12m"]],
        ["Requested", _pdf_text(memo["requested_display"]), "Recommended limit", _pdf_text(memo["recommended_limit_display"])],
        ["Pricing", _pdf_text(memo["pricing_band"]), "Data as of", f["as_of"]],
    ]
    t = Table(grid, colWidths=[38 * mm, 50 * mm, 38 * mm, 50 * mm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF0FA")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#EEF0FA")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9CCE0")),
    ]))
    story += [t, Paragraph("Summary", h), Paragraph(_pdf_text(memo["summary"]), body)]
    for key, title in (("strengths", "Strengths"), ("risks", "Risks"), ("mitigants", "Mitigants"),
                       ("covenants", "Covenants")):
        story.append(Paragraph(title, h))
        story.append(ListFlowable([Paragraph(_pdf_text(x), body) for x in memo[key]], bulletType="bullet",
                                  leftIndent=10))
    story.append(Paragraph("Policy citations", h))
    for c in memo["citations"]:
        story.append(Paragraph(f"<b>[§{c['section']}] {_pdf_text(c['title'])}</b> — {_pdf_text(c['excerpt'])}", body))
    story += [Spacer(1, 6 * mm), Paragraph(_pdf_text(memo["ai_label"]), small)]
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm,
                      bottomMargin=14 * mm, title=memo["title"]).build(story)
    return str(Path(path).relative_to(get_settings().var_dir))


__all__ = ["MemoAgent", "build_facts", "render_pdf", "AI_LABEL"]
