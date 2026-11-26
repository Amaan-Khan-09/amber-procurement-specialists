"""Who has to act on each answer: the agent alone, the supplier, or an engineer?

"Handed to a person" used to mean one queue. It hides two very different jobs:
  * ask_supplier: the documents do not establish the item (an option not marked, a value not given). No engineer
    can settle that by reading harder: only the supplier can, so a question is drafted for them, citing what was read.
  * engineer: the evidence is there but needs judgement (a derating footnote, a reading the model judged, two readings
    that disagree, a value from a scanned page, a conflict between records).

An answer goes to the supplier only when the document does not establish it AND an independent second reading of the
whole document (amber/crossread.py, a model of another family that never sees our answer) also finds it not
established. Without that second reading, or when it found a value, an engineer looks first. Nothing here changes a
verdict; it decides who acts. Code only, no model calls.
"""
from __future__ import annotations

ROUTES = {
    "decide": "settled by the agent, with verified quotes",
    "ask_supplier": "only the supplier can settle it: a question citing what was read is drafted",
    "engineer": "a person must judge, with the evidence laid out",
}
# reasons (from the decision code's own words) meaning "the document does not establish it"
NOT_ESTABLISHED = ("no value found, but the submittal mentions", "listed as a choice", "but no value that can be compared",
                   "not stated", "the selected option is not marked", "not included, optional or by others")
# reasons meaning "the evidence is there but someone must judge it"
NEEDS_JUDGEMENT = ("model judgement", "disagree", "do not appear in the quote", "quote not found", "does not mention",
                   "different columns", "scanned page", "probably a different attribute", "not checked", "is not shown in the quote",
                   "shortened", "conditional rating", "conflicting records")
OPEN = ("unclear", "missing")


def _whys(f: dict) -> list[str]:
    conds = (f.get("data") or {}).get("conditions") or []
    return [str(c.get("why", "")) for c in conds] or [str(f.get("why", ""))]


def not_established(f: dict) -> bool:
    """The answer is open only because the document does not say (no judgement involved)."""
    if f.get("status") not in OPEN:
        return False
    conds = (f.get("data") or {}).get("conditions") or []
    whys = _whys(f)
    if any(k in w for w in whys for k in NEEDS_JUDGEMENT):
        return False
    open_ = [str(c.get("why", "")) for c in conds if c.get("verdict") != "complies"] or whys
    return all(any(k in w for k in NOT_ESTABLISHED) for w in open_)


def route(f: dict, second: str | None = None) -> dict:
    """f: a finding as JSON (status, needs_human, why, data.conditions). second: the independent reader's verdict for
    the same requirement (complies / deviates / missing / unclear) or None when the document was not read twice."""
    st, human = f.get("status"), bool(f.get("needs_human"))
    hint = (f.get("data") or {}).get("route")
    if hint in ROUTES:  # a step that knows better (the package reconciliation) set it
        return {"route": hint, "kind": (f.get("data") or {}).get("route_kind", hint),
                "why": (f.get("data") or {}).get("route_why", "")}
    if not human:
        if st == "missing":
            return {"route": "ask_supplier", "kind": "not stated",
                    "why": "the document does not state it (the code searched the whole document for its words)"}
        return {"route": "decide", "kind": "decided", "why": "verified quote and a comparison made in code"}
    if not_established(f):
        if second in OPEN:
            return {"route": "ask_supplier", "kind": "not established, read twice",
                    "why": f"the document does not establish it, and an independent reading of the whole document agrees ({second})"}
        if second is None:
            return {"route": "engineer", "kind": "absence not confirmed",
                    "why": "the document does not seem to establish it, but it was not read a second time: a person checks before asking the supplier"}
        return {"route": "engineer", "kind": "contested",
                "why": f"our reading found no value, but an independent reading says {second}: a person checks the page"}
    if st in ("complies", "deviates"):
        contested = second not in (None, st)
        return {"route": "engineer", "kind": "contested" if contested else "confirm a reading",
                "why": (f"an independent reading says {second}; " if contested else "")
                       + "the evidence is quoted but judged, not computed: a person confirms it"}
    return {"route": "engineer", "kind": "judgement", "why": "the evidence needs judgement: " + _whys(f)[0][:160]}


def route_bid_cell(f: dict) -> dict:
    """A cell of the bid comparison (scope item x bidder)."""
    status = (f.get("data") or {}).get("scope_status")
    if status in ("silent", "qualified"):
        return {"route": "ask_supplier", "kind": f"scope {status}",
                "why": "the bid " + ("does not mention it" if status == "silent" else "offers less than the scope or words it differently")
                       + ": a clarification request is drafted; leveling meanwhile uses the owner's allowance"}
    if f.get("needs_human"):
        return {"route": "engineer", "kind": "judgement", "why": str(f.get("why", ""))[:160]}
    return {"route": "decide", "kind": "decided", "why": "the bid's own words, verified on the page"}


def summarize(routed: list[dict]) -> dict:
    n = len(routed) or 1
    out = {r: sum(1 for x in routed if x["route"] == r) for r in ROUTES}
    out["total"] = len(routed)
    out["engineer_share"] = round(out["engineer"] / n, 3)
    out["kinds"] = {}
    for x in routed:
        out["kinds"][x["kind"]] = out["kinds"].get(x["kind"], 0) + 1
    return out
