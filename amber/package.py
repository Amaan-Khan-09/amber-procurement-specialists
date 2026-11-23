"""run_package_review: the three specialists as one product, each one's output feeding the next.

  level_bids            -> leveled cost, scope gaps, each bidder's quoted lead time (with its quote)
  check_submittal       -> for each bidder whose product submittal is supplied: does it meet the spec?
                           A rejected submittal means the bid is not like-for-like and adds a resubmittal cycle
  assess_delivery_risk  -> per bidder: arrival range and P(late), using the bid's lead time + resubmittal
  combine               -> one table: cost, compliance, schedule per bidder; a recommendation only when safe
"""
from __future__ import annotations

import time

from .bids import level_bids
from .delivery import assess_delivery_risk
from .llm import LLM
from .schema import Finding, RunInfo, ToolResult, Verdict
from .submittal import check_submittal


def run_package_review(bid_form: str, bids: dict[str, str], spec: str, tag: str, tag_group: str,
                       schedule: str, po_status: str, evidence: str, as_of: str,
                       submittals: dict[str, str] | None = None, checklist: list[dict] | None = None,
                       llm: LLM | None = None) -> ToolResult:
    t0 = time.time()
    llm = llm or LLM()
    submittals = submittals or {}

    lb = level_bids(bid_form, bids, llm=llm)
    sub_res = {b: check_submittal(spec, p, tag, schedule, checklist=checklist, llm=llm) for b, p in submittals.items()}

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
