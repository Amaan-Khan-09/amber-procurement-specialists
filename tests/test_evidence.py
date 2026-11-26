"""The clause-by-clause evidence record: supersession, conflicting replies, revisions and absent proof."""
from amber import case as C
from amber import docs, evidence


def _doc(name, text):
    return docs.Document(doc_id=name, path=name, pages=[docs.Page(number=1, text=text, raw=text)], commitment=True)


def _part(doc, quote, verdict, conf=0.95):
    return {"cid": "x", "verdict": verdict, "conf": conf, "why": quote, "doc": doc.doc_id, "source": doc.doc_id,
            "cite": {"doc_id": doc.doc_id, "page": 1, "quote": quote, "match": "exact"}}


def _resolve(*items):
    documents = [d for d, _ in items]
    metas = [evidence.doc_meta(d, "reply" if "reply" in d.doc_id else "bid") for d in documents]
    return evidence.resolve_commitments([p for _, p in items], documents, metas), metas


def test_a_reply_that_says_it_replaces_the_bid_controls():
    bid = _doc("b2-bid", "Each set includes: 12-hour UL 2085 sub-base fuel tank.")
    rep = _doc("b2-reply", "Date: 2026-12-03\n1. Fuel tank: we will supply a 24 hour UL 2085 tank in place of the 12-hour tank.")
    res, _ = _resolve((bid, _part(bid, "12-hour UL 2085 sub-base fuel tank", "deviates")),
                      (rep, _part(rep, "24 hour UL 2085 tank", "complies")))
    assert res["conflict"] is None and res["effective"] == [1] and res["superseded"][0][0] == 0


def test_two_replies_that_disagree_without_saying_so_are_a_conflict_whatever_their_dates():
    a = _doc("v-reply-1", "Date: 2026-12-01\n1. The tank holds 24 hours at full load.")
    b = _doc("v-reply-2", "Date: 2026-12-05\n1. The tank holds 12 hours at full load.")
    res, _ = _resolve((a, _part(a, "tank holds 24 hours", "complies")), (b, _part(b, "tank holds 12 hours", "deviates")))
    assert res["conflict"] is not None and res["superseded"] == []


def test_replaces_elsewhere_in_the_document_does_not_count_for_this_item():
    a = _doc("v-reply-1", "1. The tank holds 24 hours at full load.")
    b = _doc("v-reply-2", "1. The tank holds 12 hours at full load.\n2. The annunciator replaces the older panel.")
    res, _ = _resolve((a, _part(a, "tank holds 24 hours", "complies")), (b, _part(b, "tank holds 12 hours", "deviates")))
    assert res["conflict"] is not None


def test_a_weak_mention_neither_supersedes_nor_conflicts():
    a = _doc("v-reply-1", "1. The tank holds 24 hours at full load.")
    b = _doc("v-reply-2", "1. Tank sizing to be confirmed, revised later.")
    res, _ = _resolve((a, _part(a, "tank holds 24 hours", "complies")), (b, _part(b, "Tank sizing to be confirmed", "unclear", 0.5)))
    assert res["conflict"] is None and res["effective"] == [0, 1]


def test_document_revision_and_date_are_read_as_printed_and_never_guessed():
    d = _doc("ds", "Part No. 10000031601 | Rev. D 06/12/2024")
    assert evidence.doc_meta(d)["revision"].startswith("Rev D")
    assert evidence.doc_meta(_doc("e", "From: x\nDate: Thu, 19 Nov 2026 16:42"))["date"] == "2026-11-19"
    assert evidence.doc_meta(_doc("n", "no date here"))["date"] == ""


def test_a_conflict_between_two_replies_reaches_the_answer_and_absent_proof_never_complies():
    req = [{"req_id": "R19", "requirement": "tank >= 24 h", "spec_citation": {"doc_id": "spec", "page": 1, "quote": "q"},
            "conditions": [{"cid": "R19b", "attribute": "fuel_tank_capacity_at_full_standby_load", "kind": "numeric",
                            "op": ">=", "value": 24, "unit": "h"}]}]
    ds = docs.Document(doc_id="ds", path="ds", pages=[docs.Page(number=1, text="Standard features", raw="")])
    r1 = _doc("v-reply-1", "Fuel tank capacity at full standby load: 24 h")
    r2 = _doc("v-reply-2", "Fuel tank capacity at full standby load: 12 h")
    offer = lambda q, v: {"R19b": {"cid": "R19b", "stated": True, "values": [v], "unit": "h", "quote": q, "page": 1, "meets": None}}
    out = C.reconcile_supplier(req, ds, {}, [r1, r2], [offer("Fuel tank capacity at full standby load: 24 h", "24"),
                                                       offer("Fuel tank capacity at full standby load: 12 h", "12")])
    f = out["findings"][0]
    assert f["status"] == "unclear" and f["route"]["route"] == "ask_supplier" and f["route"]["kind"] == "conflicting records"
    roles = [e["role"] for e in out["evidence"] if e["document"].startswith("v-reply")]
    assert roles == ["conflicts", "conflicts"]
    out = C.reconcile_supplier(req, ds, {}, [], [])
    assert out["findings"][0]["status"] != "complies"
