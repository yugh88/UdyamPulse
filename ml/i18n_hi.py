"""Hindi text for everything the MSME owner reads: score reasons, pillar names and plan steps.
Digits stay in Latin numerals, as is usual in Indian banking apps."""

from __future__ import annotations

import numpy as np

from ml.features import FEATURES

PILLARS_HI = {
    "order_book": "ऑर्डर बुक और डिस्पैच",
    "cash_flow": "नकदी प्रवाह",
    "production": "उत्पादन",
    "receivables": "वसूली की गुणवत्ता",
    "compliance": "नियम पालन",
}

# One template per model feature; "{v}" is replaced by the formatted value.
TEMPLATES_HI: dict[str, str] = {
    "eway_value_chg_1v3": "ई-वे बिल मूल्य 3 महीने के औसत से {v}",
    "eway_value_chg_1v2": "ई-वे बिल मूल्य पिछले 8 हफ़्तों से {v}",
    "eway_value_chg_3v12": "ई-वे बिल मूल्य (3 माह) 12 महीने के औसत से {v}",
    "eway_value_yoy": "ई-वे बिल मूल्य पिछले साल से {v}",
    "eway_count_chg_1v3": "ई-वे बिलों की संख्या 3 महीने के औसत से {v}",
    "eway_count_chg_3v12": "ई-वे बिलों की संख्या (3 माह) 12 महीने के औसत से {v}",
    "einvoice_value_chg_1v3": "ई-इनवॉइस मूल्य 3 महीने के औसत से {v}",
    "einvoice_value_chg_3v12": "ई-इनवॉइस मूल्य (3 माह) 12 महीने के औसत से {v}",
    "einvoice_value_yoy": "बिक्री पिछले साल से {v}",
    "einvoice_value_slope_6": "6 महीने का बिक्री रुझान {v} प्रति माह",
    "einvoice_count_chg_1v3": "ई-इनवॉइस की संख्या 3 महीने के औसत से {v}",
    "po_cover_months": "खुले ऑर्डर {v} की बिक्री के बराबर",
    "po_cover_chg_1v3": "ऑर्डर बुक 3 महीने के औसत से {v}",
    "eway_to_einvoice_ratio": "ई-वे बिल, इनवॉइस मूल्य के {v} के बराबर",
    "eway_value_cv_6": "डिस्पैच में उतार-चढ़ाव (6 माह) {v}",
    "einvoice_value_cv_12": "बिक्री में उतार-चढ़ाव (12 माह) {v}",
    "net_inflow_ratio_1": "इस महीने खाते में शुद्ध आवक {v}",
    "net_inflow_ratio_3": "3 महीनों में खाते में शुद्ध आवक {v}",
    "net_inflow_ratio_6": "6 महीनों में खाते में शुद्ध आवक {v}",
    "credits_chg_1v3": "बैंक में जमा 3 महीने के औसत से {v}",
    "credits_chg_3v12": "बैंक में जमा (3 माह) 12 महीने के औसत से {v}",
    "credits_yoy": "बैंक में जमा पिछले साल से {v}",
    "balance_chg_1v1": "औसत बैलेंस 30 दिनों में {v}",
    "balance_chg_1v3": "औसत बैलेंस 3 महीने के औसत से {v}",
    "balance_cv_6": "बैलेंस में उतार-चढ़ाव (6 माह) {v}",
    "balance_to_debits_1": "नकद बचत मासिक खर्च का {v}",
    "balance_to_debits_3": "3 महीने की नकद बचत खर्च का {v}",
    "bounces_1": "इस महीने {v} चेक/NACH बाउंस",
    "bounces_3": "3 महीनों में {v} चेक/NACH बाउंस",
    "bounces_6": "6 महीनों में {v} चेक/NACH बाउंस",
    "bounces_12": "12 महीनों में {v} चेक/NACH बाउंस",
    "debits_to_credits_3": "खर्च, आवक का {v} (3 माह)",
    "loan_to_turnover": "माँगा गया लोन सालाना टर्नओवर का {v}",
    "kwh_chg_1v3": "बिजली खपत 3 महीने के औसत से {v}",
    "kwh_chg_1v2": "बिजली खपत पिछले 8 हफ़्तों से {v}",
    "kwh_chg_3v12": "बिजली खपत (3 माह) 12 महीने के औसत से {v}",
    "kwh_yoy": "बिजली खपत पिछले साल से {v}",
    "kwh_vs_sector": "बिजली खपत अपने उद्योग के औसत से {v}",
    "kwh_per_lakh_3": "हर ₹1 लाख बिक्री पर {v} kWh",
    "kwh_slope_6": "6 महीने का बिजली खपत रुझान {v} प्रति माह",
    "kwh_cv_6": "बिजली खपत में उतार-चढ़ाव (6 माह) {v}",
    "rm_ratio_1": "कच्चे माल की खरीद बिक्री का {v}",
    "rm_ratio_3": "कच्चे माल की खरीद बिक्री का {v} (3 माह)",
    "rm_chg_1v3": "कच्चे माल की खरीद 3 महीने के औसत से {v}",
    "rm_chg_3v12": "कच्चे माल की खरीद (3 माह) 12 महीने के औसत से {v}",
    "top_buyer_share_1": "सबसे बड़ा खरीदार बिक्री का {v}",
    "top_buyer_share_6": "सबसे बड़ा खरीदार औसतन बिक्री का {v} (6 माह)",
    "buyer_hhi": "खरीदारों पर निर्भरता सूचकांक {v}",
    "top_buyer_share_chg_1v6": "सबसे बड़े खरीदार का हिस्सा 6 महीने के औसत से {v}",
    "days_to_pay_1": "खरीदार {v} में भुगतान करते हैं",
    "days_to_pay_3": "खरीदार {v} में भुगतान करते हैं (3 माह औसत)",
    "days_to_pay_chg_1v3": "भुगतान में लगने वाले दिन 3 महीने के औसत से {v}",
    "days_to_pay_chg_3v12": "भुगतान में लगने वाले दिन (3 माह) 12 महीने के औसत से {v}",
    "days_to_pay_slope_6": "भुगतान के दिनों का रुझान {v} प्रति माह",
    "n_buyers": "{v} सक्रिय खरीदार",
    "gst_delay_1": "GSTR-3B {v} देर से भरा",
    "gst_delay_3": "GSTR-3B औसतन {v} देर से भरा (3 माह)",
    "gst_late_months_3": "3 महीनों में {v} बार GST देर से भरा",
    "gst_late_months_6": "6 महीनों में {v} बार GST देर से भरा",
    "gst_late_months_12": "12 महीनों में {v} बार GST देर से भरा",
    "gst_consecutive_late": "लगातार {v} बार GST देर से भरा",
    "epfo_chg_1v3": "EPFO कर्मचारी संख्या 3 महीने के औसत से {v}",
    "epfo_chg_3v12": "EPFO कर्मचारी संख्या (3 माह) 12 महीने के औसत से {v}",
    "epfo_drop_months_6": "6 महीनों में {v} बार कर्मचारी संख्या घटी",
    "gst_bank_mismatch_1": "GST टर्नओवर और बैंक जमा में {v} का अंतर",
    "gst_bank_mismatch_3": "GST और बैंक जमा में औसतन {v} का अंतर (3 माह)",
    "vintage_years": "कारोबार में {v}",
}


def format_value_hi(name: str, value: float | None) -> str:
    kind = FEATURES[name].kind
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "उपलब्ध नहीं"
    if kind == "pct_chg":
        return f"{'↑' if value > 0 else '↓'}{abs(value) * 100:.0f}%"
    if kind == "pct":
        return f"{value * 100:.0f}%"
    if kind == "days":
        return f"{value:.0f} दिन"
    if kind == "days_delta":
        return f"{'+' if value >= 0 else '−'}{abs(value):.0f} दिन"
    if kind == "count":
        return f"{value:.0f}"
    if kind == "months":
        return f"{value:.1f} महीने"
    if kind == "years":
        return f"{value:.0f} साल"
    return f"{value:.2f}" if abs(value) < 10 else f"{value:.0f}"


def describe_hi(name: str, value: float | None) -> str:
    return TEMPLATES_HI[name].replace("{v}", format_value_hi(name, value))
