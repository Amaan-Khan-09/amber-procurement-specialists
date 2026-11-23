"""Follow-up drafts: built only from verified findings, never sent, and every quoted fact is a real citation."""
import re

import pytest

from amber.followups import draft_follow_ups


def cite(doc, page, quote, locator=""):
    return {"doc_id": doc, "page": page, "locator": locator, "quote": quote, "match": "exact", "ocr": False}


SUBMITTAL_RESULT = {
    "tool": "check_submittal",
    "result": {"tag": "GEN-A", "submittal": "kohler-kd2000-g5-626"},
    "findings": [
        {"id": "F-R19", "claim": "UL 2085 sub-base tank, 24 h", "status": "deviates", "confidence": 0.9,
         "citations": [cite("26-32-13-engine-generators-alpha", 8, "UL 2085 listed manufacturer's standard in skid", "2.1.K.1"),
                       cite("kohler-kd2000-g5-626", 6, "tank meets UL 142 requirements")],
         "data": {"req_id": "R19", "locator": "2.1.K.1 (In Skid Diesel Fuel Tank)"}},
        {"id": "F-R18", "claim": "THD <= 5%", "status": "missing", "confidence": 0.8,
         "citations": [cite("26-32-13-engine-generators-alpha", 6, "shall not exceed 5% of the rated voltage", "2.1.I.4")],
         "data": {"req_id": "R18", "locator": "2.1.I.4"}},
        {"id": "F-R12", "claim": "Engine speed <= 1800 rpm", "status": "complies", "confidence": 0.95,
         "citations": [cite("kohler-kd2000-g5-626", 2, "Rated rpm 1800")], "data": {"req_id": "R12"}},
    ],
}

BID_RESULT = {
    "tool": "level_bids",
    "result": {"package": "BP-26-04 Standby Generators", "scope": [{"id": "S7", "item": "Offloading and rigging"},
                                                                  {"id": "S9", "item": "Field load bank test"}],
               "products": {"B1": "Cat 3516C"},
               "terms": {"B1": [{"note": "metals surcharge", "risk": "unquantified_cost",
                                 "citation": cite("b1-northline-power", 1, "subject to metals surcharge at time of shipment")}]}},
    "findings": [
        {"id": "F-B1-S7", "claim": "B1 S7: excluded", "status": "deviates", "confidence": 0.9,
         "citations": [cite("b1-northline-power", 1, "Offloading, rigging and setting on pads by others.")],
         "data": {"bid": "B1", "scope_id": "S7", "scope_status": "excluded"}},
        {"id": "F-B1-S9", "claim": "B1 S9: silent", "status": "missing", "confidence": 0.8, "citations": [],
         "data": {"bid": "B1", "scope_id": "S9", "scope_status": "silent"}},
        {"id": "F-B1-S1", "claim": "B1 S1: included", "status": "complies", "confidence": 0.9, "citations": [],
         "data": {"bid": "B1", "scope_id": "S1", "scope_status": "included"}},
    ],
}


def _quoted(body: str) -> list[str]:
    return re.findall(r'"([^"]+)"', body)


def test_submittal_draft_asks_about_each_gap_and_quotes_only_real_citations():
    res = draft_follow_ups(SUBMITTAL_RESULT)
    assert len(res.findings) == 1
    d = res.findings[0]
    body = d.data["body"]
    assert "UL 142" in body and "UL 2085" in body and "THD" in body
    assert "Engine speed" not in body  # compliant items are not chased
    known = {c.quote for c in d.citations}
    assert _quoted(body) and all(q in known for q in _quoted(body))
    assert d.needs_human and res.needs_human  # drafts are never sent automatically


def test_bid_draft_covers_exclusions_silence_and_risky_terms():
    res = draft_follow_ups(BID_RESULT)
    body = res.findings[0].data["body"]
    assert "S7" in body and "S9" in body and "S1 " not in body
    assert "metals surcharge" in body and "firm price" in body
    assert [ln.split(".")[0] for ln in body.splitlines() if re.match(r"^\d+\. ", ln)] == ["1", "2", "3"]


def test_rejects_unknown_input():
    with pytest.raises(ValueError):
        draft_follow_ups({"tool": "something_else"})
