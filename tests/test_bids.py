"""Leveling math and award logic, fed the answer key's statuses (no model involved)."""
import json
from pathlib import Path

from amber.bids import award, level

KEY = json.loads((Path(__file__).resolve().parents[1] / "eval/answer_keys/bids_genset.json").read_text(encoding="utf-8"))

FORM = {"quantity": 4, "allowances": [
    {"scope_id": "S2", "amount": 38000, "basis": "per_unit"}, {"scope_id": "S3", "amount": 55000, "basis": "per_unit"},
    {"scope_id": "S4", "amount": 3200, "basis": "per_unit"}, {"scope_id": "S5", "amount": 6000, "basis": "per_unit"},
    {"scope_id": "S6", "amount": 18500, "basis": "per_unit"}, {"scope_id": "S7", "amount": 9500, "basis": "per_unit"},
    {"scope_id": "S8", "amount": 7500, "basis": "per_unit"}, {"scope_id": "S9", "amount": 14000, "basis": "per_unit"},
    {"scope_id": "S10", "amount": 3000, "basis": "lump_sum"}, {"scope_id": "S11", "amount": 24000, "basis": "per_unit"}]}

ALTS = {("B1", "S11"): (96000, "total"), ("B3", "S3"): (62000, "per_unit")}
LEADS = {"B1": 62, "B2": 54, "B3": 74, "B4": 60}
TERMS = {"B3": [{"note": "tariff adjustment clause", "risk": "unquantified_cost"}],
         "B4": [{"note": "budget number", "risk": "not_firm"}]}


def bids_from_key():
    out = {}
    for b in KEY["base_bid"]:
        items = {}
        for sid, row in KEY["matrix"].items():
            i = {"status": row[b]}
            if (b, sid) in ALTS:
                i["alt_amount"], i["alt_basis"] = ALTS[(b, sid)]
            items[sid] = i
        out[b] = {"base_total": KEY["base_bid"][b], "items": items, "lead_time": {"max_weeks": LEADS[b]},
                  "terms": TERMS.get(b, [])}
    return out


def test_leveling_reproduces_answer_key_totals():
    table = level(FORM, bids_from_key())
    for b, total in KEY["adjusted_total"].items():
        assert table[b]["adjusted"] == total, (b, table[b])
        assert table[b]["adjustments"] == KEY["adjustments"][b]


def test_award_is_not_automatic_when_cheapest_is_slow_and_has_tariff_clause():
    bids = bids_from_key()
    d = award(level(FORM, bids), bids)
    assert d["auto_award"] is False and d["recommend"] is None
    assert d["ranked"] == KEY["rank_by_adjusted"]
    assert [o["bid"] for o in d["options"]] == ["B3", "B2"]
    assert d["options"][1]["premium_vs_cheapest"] == 497200
    assert "B4" in d["clarify_before_award"]
    assert any("tariff" in b for b in d["blockers"]) and any("lead time" in b for b in d["blockers"])


def test_clean_cheapest_bid_is_awarded():
    bids = bids_from_key()
    for b in bids.values():
        b["terms"] = []
        b["lead_time"] = {"max_weeks": 50}
        b["items"] = {k: {"status": "included"} for k in b["items"]}
    d = award(level(FORM, bids), bids)
    assert d["auto_award"] is True and d["recommend"] == "B3"


def test_award_answer_cites_its_evidence():
    from amber.bids import _award_citations
    cite = {"doc_id": "b3", "page": 1, "locator": "", "quote": "Prices are subject to adjustment for tariffs", "match": "exact", "ocr": False}
    base = {"doc_id": "b3", "page": 1, "locator": "", "quote": "Total 3,980,000", "match": "exact", "ocr": False}
    bids = bids_from_key()
    bids["B3"]["terms"] = [{"note": "tariff clause", "risk": "unquantified_cost", "citation": cite}]
    bids["B3"]["base_citation"] = base
    d = award(level(FORM, bids), bids)
    quotes = [c.quote for c in _award_citations(d, bids)]
    assert "Prices are subject to adjustment for tariffs" in quotes and "Total 3,980,000" in quotes
