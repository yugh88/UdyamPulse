import re
import time

from agents.guard import unsupported_numbers
from agents.providers.llm import SemanticKernelLLM
from tests.conftest import login

MEMO_TEXT_KEYS = ("summary", "recommended_limit_display", "requested_display", "pricing_band")
MEMO_LIST_KEYS = ("strengths", "risks", "mitigants", "covenants")


def _memo_text(memo: dict) -> str:
    parts = [memo[k] for k in MEMO_TEXT_KEYS]
    for k in MEMO_LIST_KEYS:
        parts += memo[k]
    return "\n".join(parts)


def _new_scored_app(client) -> int:
    rm = login(client, "rm1")
    apps = [a for a in client.get("/applications", headers=rm).json() if a["state"] == "APPLIED"]
    app_id = apps[0]["id"]
    client.post(f"/applications/{app_id}/consent", headers=rm)
    client.post(f"/applications/{app_id}/score", headers=rm)
    return app_id


def test_memo_fast_cited_and_without_invented_numbers(client):
    from api.models.db import Application, SessionLocal

    app_id = _new_scored_app(client)
    rm = login(client, "rm1")
    t0 = time.perf_counter()
    r = client.post(f"/applications/{app_id}/memo", headers=rm)
    elapsed = time.perf_counter() - t0
    assert r.status_code == 200
    memo = r.json()
    assert elapsed < 10
    assert len(memo["citations"]) >= 2
    assert re.search(r"\[§\d+\.\d+\]", memo["summary"])
    with SessionLocal() as db:
        facts = db.get(Application, app_id).memo["facts"]
    source = {"facts": facts, "policy": [c["text"] for c in memo["citations"]]}
    text = _memo_text(memo)
    assert unsupported_numbers(text, source) == set(), "memo contains numbers not present in source facts"
    cited = set(re.findall(r"§(\d+\.\d+)", text))
    assert cited <= {c["section"] for c in memo["citations"]}, "every [§x.y] must resolve to retrieved policy"
    pdf = client.get(f"/applications/{app_id}/memo.pdf", headers=rm)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


def test_guard_flags_invented_numbers():
    facts = {"score": 723, "limit": "₹3.00 Cr", "pd": "0.67%"}
    assert unsupported_numbers("Score 723, limit ₹3.00 Cr, PD 0.67%.", facts) == set()
    assert unsupported_numbers("Score 723 and turnover grew 18% last year.", facts) == {"18"}


def test_llm_output_with_invented_number_falls_back_to_template():
    llm = object.__new__(SemanticKernelLLM)
    llm.name = "fake"

    async def fake_complete(task, facts, draft):
        return "The unit scores 723 and should get a ₹5.5 Cr limit."

    llm._complete = fake_complete
    draft = "The unit scores 723."
    assert llm.write("summary", {"score": 723}, draft) == draft
