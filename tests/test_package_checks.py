"""Checks learned from how procurement teams work: scope that no bid includes, and substitutions (the submittal is
not for the product that was bid). Both are decided in code, with citations."""
from amber.bids import uncovered_scope
from amber.followups import draft_follow_ups
from amber.package import model_tokens, same_product

FORM = {"quantity": 4, "scope": [{"id": "S1", "item": "Generator sets"}, {"id": "S7", "item": "Offloading and rigging"}],
        "allowances": [{"scope_id": "S7", "amount": 9500, "basis": "per_unit"}]}
BIDS = {"B1": {"items": {"S1": {"status": "included"}, "S7": {"status": "excluded"}}},
        "B2": {"items": {"S1": {"status": "included"}, "S7": {"status": "silent"}}}}


def test_scope_that_no_bid_includes_is_found_and_priced_with_the_allowance():
    u = uncovered_scope(FORM, BIDS)
    assert [x["id"] for x in u] == ["S7"]
    assert u[0]["statuses"] == {"B1": "excluded", "B2": "silent"} and u[0]["allowance"] == 38000


def test_scope_included_by_any_bid_is_not_flagged():
    bids = {**BIDS, "B3": {"items": {"S1": {"status": "included"}, "S7": {"status": "included"}}}}
    assert uncovered_scope(FORM, bids) == []


def test_model_designations_not_ratings():
    assert model_tokens("Cummins C2000D6 (model DQKAB) diesel generator set") == ["C2000D6", "DQKAB"]
    assert model_tokens("Caterpillar 3516C") == ["3516C"]
    assert model_tokens("4 x 2000 ekW 480V gensets") == []


def test_substitution_is_caught_and_a_match_is_cited(tmp_path):
    sub = tmp_path / "submittal.txt"
    sub.write_text("Product data\nIndustrial Diesel Generator Set - KD2000\nRatings 2000 kW", encoding="utf-8")
    m = same_product("Kohler KD2000 2000 kW standby", str(sub))
    assert m["status"] == "match" and m["citation"]["quote"] == "Industrial Diesel Generator Set - KD2000"
    assert same_product("Caterpillar 3516C", str(sub))["status"] == "absent"
    assert same_product("a generator", str(sub))["status"] == "unknown"


def test_follow_up_tells_every_bidder_when_no_bid_includes_an_item():
    cite = {"doc_id": "b1", "page": 1, "locator": "", "quote": "Rigging by others.", "match": "exact", "ocr": False}
    res = {"tool": "level_bids",
           "result": {"package": "P", "scope": FORM["scope"], "uncovered_scope": [{"id": "S7"}]},
           "findings": [{"id": "F-B1-S7", "claim": "B1 S7: excluded", "status": "deviates", "confidence": 0.9,
                         "citations": [cite], "data": {"bid": "B1", "scope_id": "S7", "scope_status": "excluded"}}]}
    body = draft_follow_ups(res).findings[0].data["body"]
    assert "No bid we received includes this item" in body
