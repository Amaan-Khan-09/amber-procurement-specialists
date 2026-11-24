"""run_package_review: the three specialists as one product, each one's output feeding the next.

  level_bids            -> leveled cost, scope gaps, each bidder's quoted lead time (with its quote)
  check_submittal       -> for each bidder whose product submittal is supplied: does it meet the spec?
                           A rejected submittal means the bid is not like-for-like and adds a resubmittal cycle
  assess_delivery_risk  -> per bidder: arrival range and P(late), using the bid's lead time + resubmittal
  combine               -> one table: cost, compliance, schedule per bidder; a recommendation only when safe
"""
from __future__ import annotations

import re
import time

from . import docs
from .bids import level_bids
from .delivery import assess_delivery_risk
from .llm import LLM
from .schema import Citation, Finding, RunInfo, ToolResult, Verdict
from .submittal import check_submittal
from .verify import verify

_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{2,}")


def model_tokens(product: str | None) -> list[str]:
    """The model designations in a product name ("Cummins C2000D6 (model DQKAB)" -> C2000D6, DQKAB): mixed letters and
    digits, or a code in capitals. Ratings such as 2000 kW are not model names."""
    out = []
    for t in _TOKEN.findall(product or ""):
        t = t.strip("-")
        if re.fullmatch(r"\d+(?:e?kw|kva|v|hz|rpm|a)?", t, re.I):
            continue
        if (re.search(r"\d", t) and re.search(r"[A-Za-z]", t)) or re.fullmatch(r"[A-Z]{4,}", t):
            out.append(t)
    return out


def same_product(product: str | None, submittal_path: str) -> dict:
    """Is the submittal for the product the bidder offered? Checked in code: a model designation from the bid must
    appear in the submittal's text. The line it appears on is cited. A substitution is the classic way a cheap bid
    becomes an expensive problem, so an absent model goes to a person."""
    tokens = model_tokens(product)
    if not tokens:
        return {"status": "unknown", "why": "the bid names no model designation to look for"}
    doc = docs.load(submittal_path)
    squash = lambda s: re.sub(r"[\s\-]", "", s).lower()
    for pg in doc.pages:
        flat = squash(pg.text)
        for t in tokens:
            if squash(t) in flat:
                line = next((ln.strip() for ln in pg.text.splitlines() if squash(t) in squash(ln)), "")
                c = verify(doc, line[:160], page=pg.number) if line else None
                return {"status": "match", "token": t, "citation": c.model_dump() if c else None}
    if doc.scanned_pages:
        return {"status": "unknown", "tokens": tokens,
                "why": f"{', '.join(tokens)} not on the text pages; {len(doc.scanned_pages)} scanned pages were not read"}
    return {"status": "absent", "tokens": tokens}


def run_package_review(bid_form: str, bids: dict[str, str], spec: str, tag: str, tag_group: str,
                       schedule: str, po_status: str, evidence: str, as_of: str,
                       submittals: dict[str, str] | None = None, checklist: list[dict] | None = None,
                       llm: LLM | None = None) -> ToolResult:
    t0 = time.time()
    llm = llm or LLM()
    submittals = submittals or {}

    lb = level_bids(bid_form, bids, llm=llm)
    sub_res = {b: check_submittal(spec, p, tag, schedule, checklist=checklist, llm=llm) for b, p in submittals.items()}

    same = {b: same_product(lb.result["products"].get(b), p) for b, p in submittals.items()}

    lead = {}
    for b, lt in (lb.result.get("lead_time") or {}).items():
        if not lt or lt.get("min_weeks") is None:
            continue
        basis = lt.get("basis") if lt.get("basis") in ("after_order", "after_submittal_approval") else "after_order"
        lead[b] = {"min_weeks": lt.get("min_weeks"), "max_weeks": lt.get("max_weeks") or lt.get("min_weeks"),
                   "basis": basis, "citation": lt.get("citation"),
                   "resubmittal": b in sub_res and sub_res[b].result["overall"] == "reject"}
    dr = assess_delivery_risk(schedule, po_status, evidence, as_of, bid_lead_times={tag_group: lead})

    table = []
    for b in bids:
        lv = lb.result["leveling"].get(b, {})
        gaps = [s for s, st in lb.result["matrix"].get(b, {}).items() if st not in ("included",)]
        sr = sub_res.get(b)
        fc = next((f for f in dr.findings if f.data.get("tag_group") == tag_group
                   and f.data.get("scenario") == f"award to {b}"), None)
        table.append({
            "bid": b, "product": lb.result["products"].get(b),
            "base": lv.get("base"), "leveled_cost": lv.get("adjusted"), "scope_gaps": gaps,
            "submittal": (sr.result["overall"] if sr else "not supplied"),
            "submittal_summary": (sr.result["summary"] if sr else None),
            "same_product": (same[b]["status"] if b in same else None),
            "arrival_P50": fc.data["arrival"]["P50"] if fc else None,
            "arrival_P90": fc.data["arrival"]["P90"] if fc else None,
            "p_late": fc.data["p_late"] if fc else None,
        })
    table.sort(key=lambda r: r["leveled_cost"] or float("inf"))

    award = lb.result["award"]
    notes = []
    for r in table:
        if r["submittal"] == "reject":
            notes.append(f"{r['bid']}: product submittal deviates from the spec - not like-for-like; resolve "
                         "deviations before award or price them")
        elif r["submittal"] == "not supplied":
            notes.append(f"{r['bid']}: no product submittal checked yet - request it before award")
        if r.get("same_product") == "absent":
            notes.append(f"{r['bid']}: the submittal does not name the product bid ({r['product']}) - possible "
                         "substitution; confirm before relying on the check")
    for u in lb.result.get("uncovered_scope") or []:
        notes.append(f"no bid includes {u['id']} ({u['item']}): ask every bidder to price it, or buy it separately")
    if all((r["p_late"] or 0) >= 0.5 for r in table if r["p_late"] is not None):
        notes.append("every option is likely to miss the need date: escalate schedule mitigation now "
                     "(production slot reservation, phased energisation, temporary power)")
    decision = {"recommend": award.get("recommend"), "auto_award": bool(award.get("auto_award")) and not notes,
                "options": award.get("options"), "notes": notes, "level_bids_reason": award.get("why")}

    award_f = next((f for f in lb.findings if f.id == "F-award"), None)
    findings = [Finding(id="F-package", claim=f"package review: {len(bids)} bids, {len(submittals)} submittals checked",
                        status=Verdict.complies if decision["auto_award"] else Verdict.unclear,
                        confidence=0.9 if decision["auto_award"] else 0.6, needs_human=not decision["auto_award"],
                        citations=list(award_f.citations) if award_f else [],
                        why=" | ".join(notes) or award.get("why", ""), data=decision)]
    bid_cites = lb.result.get("product_citations") or {}
    for b, m in same.items():
        cites = [Citation(**c) for c in (bid_cites.get(b), m.get("citation")) if c]
        prod = lb.result["products"].get(b)
        if m["status"] == "match":
            f = Finding(id=f"F-same-product-{b}", claim=f"{b}: the submittal is for the product bid ({m['token']})",
                        status=Verdict.complies, confidence=0.9, citations=cites,
                        why=f"the model {m['token']} from the bid appears in the submittal", data={"bid": b, **m})
        elif m["status"] == "absent":
            f = Finding(id=f"F-same-product-{b}", claim=f"{b}: possible substitution: the submittal does not name {prod}",
                        status=Verdict.deviates, confidence=0.6, needs_human=True, citations=cites,
                        why=f"none of {', '.join(m['tokens'])} appears in the submittal text", data={"bid": b, **m})
        else:
            f = Finding(id=f"F-same-product-{b}", claim=f"{b}: could not confirm the submittal is for {prod}",
                        status=Verdict.unclear, confidence=0.5, needs_human=True, citations=cites,
                        why=m.get("why", "not checked"), data={"bid": b, **m})
        findings.append(f)
    for name, r in [("level_bids", lb), ("delivery", dr)] + [(f"submittal:{b}", s) for b, s in sub_res.items()]:
        for f in r.findings:
            f.id = f"{name}/{f.id}"
            findings.append(f)
    res = ToolResult(tool="run_package_review", findings=findings,
                     result={"package": lb.result.get("package"), "comparison": table, "decision": decision,
                             "parts": {"level_bids": lb.result, "delivery": dr.result,
                                       "submittals": {b: s.result for b, s in sub_res.items()}}},
                     run=RunInfo(models=llm.meter.models(), latency_ms=int((time.time() - t0) * 1000),
                                 steps=list(llm.meter.steps)))
    res = res.finalize()
    # the next action: ready-to-send follow-ups for every gap found, built only from verified findings
    from .followups import draft_follow_ups
    res.result["follow_ups"] = [f.data for f in draft_follow_ups(res.model_dump(mode="json")).findings]
    return res
