"""Document parsing: stub parser for sample PDFs/text (default) or Azure AI Document Intelligence (prod)."""

from __future__ import annotations

import re
from functools import lru_cache

from agents.providers.base import ParsedDocument
from core.settings import get_settings

_PATTERNS = {
    "units_kwh": re.compile(r"units?\s*(?:consumed)?\s*[:\-]?\s*([\d,]+)\s*kwh", re.I),
    "amount_inr": re.compile(r"(?:amount|total)\s*(?:payable|due)?\s*[:\-]?\s*(?:rs\.?|₹|inr)\s*([\d,]+(?:\.\d+)?)", re.I),
    "invoice_no": re.compile(r"invoice\s*(?:no|number)\.?\s*[:\-]?\s*([A-Z0-9/\-]+)", re.I),
    "po_no": re.compile(r"(?:po|purchase order)\s*(?:no|number)\.?\s*[:\-]?\s*([A-Z0-9/\-]+)", re.I),
}


class StubDocParser:
    """Regex extraction over text-layer documents (electricity bills, invoices, POs)."""

    def parse(self, content: bytes, filename: str) -> ParsedDocument:
        text = content.decode("utf-8", errors="ignore")
        fields = {k: m.group(1).replace(",", "") for k, p in _PATTERNS.items() if (m := p.search(text))}
        if "units_kwh" in fields:
            doc_type = "electricity_bill"
        elif "po_no" in fields:
            doc_type = "purchase_order"
        elif "invoice_no" in fields:
            doc_type = "invoice"
        else:
            doc_type = "unknown"
        return ParsedDocument(doc_type=doc_type, fields=fields, confidence=0.9 if fields else 0.0)


class AzureDocIntelParser:  # pragma: no cover - production adapter
    """Azure AI Document Intelligence (prebuilt-invoice / custom electricity-bill model)."""

    def __init__(self) -> None:
        import os

        if not os.environ.get("AZURE_DOCINTEL_ENDPOINT"):
            raise RuntimeError("AZURE_DOCINTEL_ENDPOINT not set; use UP_DOC_PARSER=stub")

    def parse(self, content: bytes, filename: str) -> ParsedDocument:
        raise NotImplementedError("Wire azure-ai-documentintelligence DocumentIntelligenceClient here")


@lru_cache
def get_doc_parser() -> StubDocParser:
    if get_settings().doc_parser == "azure_docintel":
        return AzureDocIntelParser()  # type: ignore[return-value]
    return StubDocParser()
