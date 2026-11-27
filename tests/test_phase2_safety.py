"""Regressions for the exact unsafe decisions observed in the Phase 1 judge drive."""
from amber.bids import award, level, read_bid
from amber.docs import Document, Page
from amber.schema import Verdict
from amber.submittal import _decide_condition, _structure_requirements, decide_all


def test_ups_peak_efficiency_cannot_prove_full_load_minimum():
    words = "Efficiency: Up to 96.8% in ECO mode."
    doc = Document("ups", "ups.pdf", pages=[Page(1, words)])
    req = {"cid": "U05a", "kind": "numeric", "attribute": "efficiency_at_full_load",
           "op": ">=", "value": 96, "unit": "%"}
    offer = {"stated": True, "values": [96.8], "unit": "%", "quote": words, "page": 1, "meets": "yes"}
    d, cite, confidence = _decide_condition(req, offer, doc)
    assert cite and d.verdict == Verdict.unclear and confidence < 0.7
    assert "up to" in d.why


def test_ups_overload_upper_bound_cannot_prove_required_minimum():
    words = "Overload capacity: <125% load for ≤10 min."
    doc = Document("ups", "ups.pdf", pages=[Page(1, words)])
    req = {"cid": "U08a", "kind": "numeric", "attribute": "overload_capacity",
           "op": ">=", "value": 125, "unit": "%"}
    offer = {"stated": True, "values": ["<125%"], "unit": "%", "quote": words,
             "page": 1, "meets": "yes"}
    d, cite, confidence = _decide_condition(req, offer, doc)
    assert cite and d.verdict == Verdict.unclear and confidence < 0.7
    assert "upper bound" in d.why


def test_rating_at_wrong_ambient_cannot_prove_specified_condition():
    words = "Continuous rating: 600 kVA at 30 C ambient."
    doc = Document("transformer", "transformer.pdf", pages=[Page(1, words)])
    req = {"req_id": "R01", "requirement": "at least 500 kVA at 40 C ambient",
           "spec_citation": {"doc_id": "spec", "page": 1, "locator": "2.1",
                             "quote": "Continuous rating shall be at least 500 kVA at 40 C ambient."},
           "conditions": [{"cid": "R01a", "kind": "numeric", "attribute": "continuous_rating",
                           "op": ">=", "value": 500, "unit": "kVA"}]}
    offer = {"stated": True, "values": [600], "unit": "kVA", "quote": words, "page": 1, "meets": "yes"}
    findings, _ = decide_all([req], {"R01a": offer}, doc)
    assert findings[0].status == Verdict.unclear
    assert "at 40" in findings[0].why


def test_missing_bid_base_is_unpriced_while_quoted_zero_is_zero():
    class Reader:
        def __init__(self, answer): self.answer = answer
        def json(self, *_args, **_kwargs): return self.answer

    form = {"scope": [], "allowances": [], "quantity": 1}
    missing = Document("missing", "missing.txt", pages=[Page(1, "Price on request")])
    zero = Document("zero", "zero.txt", pages=[Page(1, "Base total: $0")])
    no_price = read_bid(Reader({"base_total": 0, "base_quote": "Price on request",
                                "items": [], "terms": []}), missing, form)
    free = read_bid(Reader({"base_total": 0, "base_quote": "Base total: $0",
                            "items": [], "terms": []}), zero, form)
    assert no_price["base_total"] is None and free["base_total"] == 0
    table = level(form, {"missing": no_price, "zero": free})
    decision = award(table, {"missing": no_price, "zero": free})
    assert table["missing"]["adjusted"] is None
    assert table["zero"]["adjusted"] == 0
    assert decision["ranked"] == ["zero"] and "missing" in decision["unpriced"]
    assert decision["auto_award"] is False


def test_model_omitted_manufacturer_clause_stays_visible_for_review():
    class Reader:
        def json(self, *_args, **_kwargs):
            return {"requirements": [{"req_id": "R01", "requirement": "rated 1200 A",
                                       "quote": "Rated current 1200 A",
                                       "conditions": [{"kind": "numeric", "attribute": "rated current",
                                                       "op": ">=", "value": 1200, "unit": "A"}]}]}

    doc = Document("switchgear", "switchgear.pdf", pages=[Page(1,
        "2.1 Rated current 1200 A\n2.2 Manufacturer shall be Acme or equal")])
    reqs = _structure_requirements(Reader(), doc, {}, "")
    assert len(reqs) == 2
    omitted = next(r for r in reqs if "Manufacturer" in r["requirement"])
    assert omitted["error"] and omitted["spec_citation"]
    findings, _ = decide_all(reqs, {}, Document("supplier", "supplier.pdf", pages=[Page(1, "No maker stated")]))
    finding = next(f for f in findings if f.data["req_id"] == omitted["req_id"])
    assert finding.status == Verdict.unclear and finding.confidence == 0
    assert finding.data["next_action"].startswith("Engineer:")
