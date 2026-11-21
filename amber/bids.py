"""level_bids: line up bids that each cover something different, on one common scope.

Pipeline (model reads, code does every number):
  1. bid form   scope items (S1..Sn), quantity, and the owner's leveling allowances, each with a verified quote
  2. each bid   base price, a status for every scope item (included / excluded / qualified / silent /
                alternate), alternates, terms, lead time - each with a verified quote from that bid
  3. silence    'silent' is double-checked in code: if the bid text does mention the item's key words,
                the cell becomes 'unclear' for a person instead of a confident gap
  4. level      adjusted total = base + allowance (or the bidder's own alternate price) for each gap
  5. award      ranked; an award is recommended only when it is safe to; otherwise the options are
                laid out (cheapest, fastest, deltas) and the decision goes to a person
"""
from __future__ import annotations

import json
import re
import time

from . import docs
from .llm import LLM
from .schema import Citation, Finding, RunInfo, ToolResult, Verdict
from .verify import MATCH_TRUST, verify

GAP = {"excluded", "qualified", "silent"}

FORM_SYSTEM = """You read a construction bid form (invitation to bid) and extract its structure.
Rules: copy quotes word for word from the text (5-25 words). Never invent items or amounts.
Reply with JSON: {"package": "...", "quantity": <number of units being bought>, "unit_name": "set|unit|...",
 "need_date": "YYYY-MM-DD or null",
 "scope": [{"id": "S1", "item": "...", "quote": "..."}],
 "allowances": [{"scope_id": "S2", "amount": 38000, "basis": "per_unit|lump_sum", "quote": "..."}]}"""

BID_SYSTEM = """You read one supplier's bid and report, for every scope item of the bid form, what the bid says.
Status for each scope item:
- included: the bid clearly includes it as required
- excluded: the bid says it is not included / by others
- qualified: the bid offers it but short of the requirement (smaller, shorter, different type, fewer hours/years)
- alternate: the bid prices it as an option/alternate that is NOT in the base total
- silent: the bid does not mention it at all
How to decide:
- "included" only if the bid's words meet EVERY part of the scope item (type, size, rating, duration, hours,
  years). A different type or a smaller amount is "qualified", e.g. "NEMA 1 enclosure" against "NEMA 3R enclosure",
  "standard 1-year warranty" against "3 years", "6 hours of training" against "8 hours".
- If an item is left out of the base price but priced anywhere in the bid as an option/alternate/add, the status
  is "alternate" (even if the exclusions list also mentions it), with that price.
- "excluded" is for items the bid says are not provided / by others, with no price offered.
Rules:
- "quote": copy 4-25 words EXACTLY from the bid that support the status (omit only for silent).
- For alternate: give "alt_amount" and "alt_basis" ("per_unit" or "total") as written in the bid.
- "base_total": the bid's total base price (number) with its quote.
- "offered_product": manufacturer and model exactly as written in the bid.
- "lead_time": {"min_weeks", "max_weeks", "basis": "after_order|after_submittal_approval|unknown", "quote"}.
- "terms": short notes on validity, escalation, tariffs, surcharges, budget/non-firm pricing, each with a quote.
Reply with JSON: {"bidder": "...", "offered_product": "...", "product_quote": "...", "base_total": 0, "base_quote": "...",
 "items": [{"scope_id": "S1", "status": "...", "quote": "...", "alt_amount": null, "alt_basis": null, "note": "..."}],
 "lead_time": {...}, "terms": [{"note": "...", "quote": "...", "risk": "none|unquantified_cost|short_validity|not_firm"}]}"""

CHECK_SYSTEM = """You check claims that a bid includes a scope item. For each pair, look ONLY at the quote.
Answer "no" ONLY if the quote states something that CONTRADICTS the scope item: a different type or kind
(e.g. "open skid" vs "walk-in enclosure"), or a smaller number, size, duration or rating than required.
A quote that is merely shorter or less detailed than the scope item is "yes".
For "no", name the contradicting part in a few words.
Reply with JSON: {"checks": [{"scope_id": "...", "answer": "yes|no", "missing": "..."}]}"""

STOP = {"the", "and", "for", "per", "with", "one", "set", "sets", "each", "by", "of", "to", "a", "in", "on", "at", "or"}


def _num(v) -> float | None:
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"-?\d[\d,]*\.?\d*", str(v or ""))
    return float(m.group(0).replace(",", "")) if m else None


def _keywords(item: str) -> list[str]:
    words = [w for w in re.findall(r"[a-z0-9]+", item.lower()) if w not in STOP and len(w) > 3]
    return words[:4]


def read_form(llm: LLM, form: docs.Document) -> dict:
    f = llm.json(FORM_SYSTEM, form.text()[:14000], max_tokens=2500)
    for s in f.get("scope", []):
        c = verify(form, s.get("quote", ""))
        s["citation"] = c.model_dump() if c else None
    for a in f.get("allowances", []):
        c = verify(form, a.get("quote", ""))
        a["citation"] = c.model_dump() if c else None
        a["amount"] = _num(a.get("amount"))
        a["basis"] = _basis(a.get("basis"), a.get("quote"))
    return f


def _basis(basis, quote="") -> str:
    """'per set', 'per unit', 'each', 'per_unit' -> per_unit; 'lump sum', 'LS', 'total' -> lump_sum."""
    s = f"{basis or ''} {quote or ''}".lower()
    if re.search(r"lump|\bls\b|total|per (job|project|package)", s):
        return "lump_sum"
    if re.search(r"per[ _]?(unit|set|each|generator|machine|piece)|\beach\b|/ ?(set|unit|ea)\b|\bea\b", s):
        return "per_unit"
    return "lump_sum"


def read_bid(llm: LLM, bid: docs.Document, form: dict) -> dict:
    scope = [{"id": s["id"], "item": s["item"]} for s in form.get("scope", [])]
    b = llm.json(BID_SYSTEM, "Scope items:\n" + json.dumps(scope) + "\n\nBid text:\n" + bid.text()[:12000], max_tokens=3000)
    b["base_total"] = _num(b.get("base_total"))
    b["base_citation"] = _cite(bid, b.get("base_quote"))
    b["product_citation"] = _cite(bid, b.get("product_quote") or b.get("offered_product"))
    lt = b.get("lead_time") or {}
    lt["citation"] = _cite(bid, lt.get("quote"))
    b["lead_time"] = lt
    for t in b.get("terms", []) or []:
        t["citation"] = _cite(bid, t.get("quote"))
    items = {i.get("scope_id"): i for i in b.get("items", []) if isinstance(i, dict)}
    text = bid.text().lower()
    for s in form.get("scope", []):
        i = items.setdefault(s["id"], {"scope_id": s["id"], "status": "silent"})
        i["status"] = str(i.get("status", "silent")).lower()
        i["citation"] = _cite(bid, i.get("quote")) if i["status"] != "silent" else None
        if i["status"] != "silent" and i["citation"] is None:
            i["status_reported"], i["status"] = i["status"], "unclear"
            i["why"] = "the quote given for this status is not in the bid"
        if i["status"] == "silent":
            hits = [k for k in _keywords(s["item"]) if k in text]
            if len(hits) >= 2:
                i["status"], i["why"] = "unclear", f"reported as not mentioned, but the bid mentions {hits}"
    b["items"] = items
    _second_check(llm, b, form)
    return b


def _second_check(llm: LLM, b: dict, form: dict) -> None:
    """Re-check every 'included' cell against its own quote only; a quote that doesn't prove the whole
    scope item turns the cell into 'qualified', naming what is missing."""
    scope = {s["id"]: s["item"] for s in form.get("scope", [])}
    pairs = [{"scope_id": sid, "scope_item": scope.get(sid), "quote": i["citation"]["quote"]}
             for sid, i in b["items"].items() if i["status"] == "included" and i.get("citation")]
    if not pairs:
        return
    reply = llm.json(CHECK_SYSTEM, json.dumps(pairs, ensure_ascii=False), max_tokens=1500)
    for c in reply.get("checks", []) if isinstance(reply.get("checks"), list) else []:
        i = b["items"].get(c.get("scope_id"))
        if i and str(c.get("answer", "")).lower() == "no":
            i["status"], i["why"] = "qualified", f"second check: {c.get('missing') or 'quote does not show the full scope'}"


def _cite(doc: docs.Document, quote) -> dict | None:
    c = verify(doc, quote or "") if quote else None
    return c.model_dump() if c else None


def level(form: dict, bids: dict[str, dict]) -> dict:
    qty = _num(form.get("quantity")) or 1
    allow = {a["scope_id"]: a for a in form.get("allowances", []) if a.get("amount") is not None}
    table = {}
    for bid_id, b in bids.items():
        adds, notes = {}, []
        for sid, i in b["items"].items():
            st = i["status"]
            if st == "alternate" and _num(i.get("alt_amount")) is not None:
                per_unit = _basis(i.get("alt_basis"), i.get("quote")) == "per_unit"
                amt = _num(i["alt_amount"]) * (qty if per_unit else 1)
                adds[sid] = amt
                notes.append(f"{sid}: bidder's alternate price {amt:,.0f}")
            elif st in GAP or st == "alternate":
                a = allow.get(sid)
                if a:
                    amt = a["amount"] * (qty if a.get("basis") == "per_unit" else 1)
                    adds[sid] = amt
                    notes.append(f"{sid}: {st}, owner's allowance {amt:,.0f}")
                else:
                    notes.append(f"{sid}: {st}, no allowance in the bid form - not priced")
        base = b.get("base_total") or 0
        table[bid_id] = {"base": base, "adjustments": adds, "adjusted": base + sum(adds.values()), "notes": notes}
    return table


def _lead_max(b: dict) -> float | None:
    return _num((b.get("lead_time") or {}).get("max_weeks"))


def award(table: dict, bids: dict) -> dict:
    ranked = sorted(table, key=lambda k: table[k]["adjusted"])
    cheapest = ranked[0]
    leads = {k: _lead_max(bids[k]) for k in bids}
    known = {k: v for k, v in leads.items() if v is not None}
    fastest = min(known, key=known.get) if known else None
    blockers = []
    risky = [t["note"] for t in bids[cheapest].get("terms", []) or [] if t.get("risk") not in (None, "none")]
    if risky:
        blockers.append(f"{cheapest} has open commercial risk: " + "; ".join(risky))
    unclear = [s for s, i in bids[cheapest]["items"].items() if i["status"] in ("unclear", "silent")]
    if unclear:
        blockers.append(f"{cheapest} needs clarification on {', '.join(sorted(unclear))}")
    if fastest and fastest != cheapest and known.get(cheapest, 0) - known[fastest] >= 8:
        blockers.append(f"{cheapest} lead time is {known[cheapest]:.0f} weeks vs {known[fastest]:.0f} for {fastest}")
    if not blockers:
        return {"recommend": cheapest, "auto_award": True, "ranked": ranked,
                "why": f"{cheapest} has the lowest leveled cost with no open risks"}
    opts = [{"bid": cheapest, "reason": "lowest leveled cost", "adjusted": table[cheapest]["adjusted"],
             "lead_max_weeks": known.get(cheapest)}]
    if fastest and fastest != cheapest:
        opts.append({"bid": fastest, "reason": "shortest lead time", "adjusted": table[fastest]["adjusted"],
                     "lead_max_weeks": known[fastest],
                     "premium_vs_cheapest": table[fastest]["adjusted"] - table[cheapest]["adjusted"]})
    clarify = [k for k in bids if sum(i["status"] in ("silent", "unclear") for i in bids[k]["items"].values()) >= 3
               or any(t.get("risk") == "not_firm" for t in bids[k].get("terms", []) or [])]
    return {"recommend": None, "auto_award": False, "ranked": ranked, "options": opts,
            "clarify_before_award": clarify, "blockers": blockers,
            "why": "A person should decide: " + " | ".join(blockers)}


def level_bids(form_path: str, bid_paths: dict[str, str], llm: LLM | None = None) -> ToolResult:
    t0 = time.time()
    llm = llm or LLM()
    form_doc = docs.load(form_path)
    form = read_form(llm, form_doc)
    bid_docs = {k: docs.load(p) for k, p in bid_paths.items()}
    bids = {k: read_bid(llm, d, form) for k, d in bid_docs.items()}
    table = level(form, bids)
    decision = award(table, bids)

    findings = []
    for bid_id, b in bids.items():
        for sid, i in b["items"].items():
            st = i["status"]
            cite = Citation(**i["citation"]) if i.get("citation") else None
            if st == "silent":
                conf, verdict = 0.8, Verdict.missing
            elif st == "unclear":
                conf, verdict = 0.5, Verdict.unclear
            else:
                conf = 0.92 * (MATCH_TRUST.get(cite.match, 0.8) if cite else 0.5)
                verdict = Verdict.complies if st == "included" else Verdict.deviates
            findings.append(Finding(id=f"F-{bid_id}-{sid}", claim=f"{bid_id} {sid}: {st}", status=verdict,
                                    confidence=round(conf, 3), citations=[cite] if cite else [],
                                    why=i.get("why") or i.get("note") or st,
                                    data={"bid": bid_id, "scope_id": sid, "scope_status": st,
                                          "adjustment": table[bid_id]["adjustments"].get(sid)}))
        if not b.get("base_citation"):
            findings.append(Finding(id=f"F-{bid_id}-base", claim=f"{bid_id} base price {b.get('base_total')}",
                                    status=Verdict.unclear, confidence=0.3,
                                    why="base price quote not found in the bid", data={"bid": bid_id}))
    findings.append(Finding(id="F-award", claim="award recommendation", confidence=0.9 if decision["auto_award"] else 0.6,
                            status=Verdict.complies if decision["auto_award"] else Verdict.unclear,
                            why=decision["why"], needs_human=not decision["auto_award"], data=decision))

    result = {"package": form.get("package"), "quantity": form.get("quantity"),
              "scope": [{"id": s["id"], "item": s["item"]} for s in form.get("scope", [])],
              "matrix": {k: {sid: i["status"] for sid, i in b["items"].items()} for k, b in bids.items()},
              "products": {k: b.get("offered_product") for k, b in bids.items()},
              "leveling": table, "lead_time": {k: b.get("lead_time") for k, b in bids.items()},
              "terms": {k: b.get("terms") for k, b in bids.items()}, "award": decision}
    res = ToolResult(tool="level_bids", findings=findings, result=result,
                     run=RunInfo(models=llm.meter.models(), latency_ms=int((time.time() - t0) * 1000)))
    return res.finalize()
