"""assess_delivery_risk: when will each long-lead item really arrive, and which ones will make us late?

No model calls: forecasting is done in code from cited evidence, so every number can be traced.
  1. evidence   published lead-time ranges for the item's class and size (data/leadtime_sources), each a
                weighted uniform range; a vendor's own quote for this order weighs most. A source whose range
                sits far from the others is kept but flagged as dissent and down-weighted.
  2. timeline   order date (or today + procurement time if not ordered) + submittal cycle when the lead
                time counts from approval (+ a resubmittal cycle if the submittal check found deviations)
  3. forecast   P10 / P50 / P90 arrival dates from the weighted mixture; P(late) against the need date
  4. actions    latest order date for 80% on-time, and rule-based suggestions
Honest ranges, not single guesses: the spread of the published evidence is the uncertainty.
"""
from __future__ import annotations

import csv
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from .schema import Citation, Finding, RunInfo, ToolResult, Verdict

PROCURE_WEEKS = 2.0  # award/PO paperwork if not ordered yet
SUBMITTAL_PREP, SUBMITTAL_REVIEW, RESUBMITTAL = 3.0, 2.0, 4.0
GRID = 0.25  # weeks

CLASS_BY_SECTION = {"26 32 13": "diesel_genset", "26 33 53": "static_ups", "26 23 00": "lv_switchgear",
                    "26 12 19": "padmount_transformer"}

# How much a source kind is trusted (from the 'basis' column). Vendor quotes for this order: 2.0.
BASIS_WEIGHT = [("contractor", 1.0), ("vendor blog", 0.6), ("trade press", 0.5), ("recruiting", 0.3)]


@dataclass
class Evidence:
    id: str
    low: float
    high: float
    weight: float
    label: str
    citation: Citation
    dissent: bool = False
    notes: list[str] = field(default_factory=list)


def _f(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def size_of(row: dict, cls: str) -> tuple[float | None, str]:
    if cls == "diesel_genset":
        return _f(row.get("standby_kw")), "kW"
    if cls == "static_ups":
        return _f(row.get("ups_kva")), "kVA"
    if cls == "padmount_transformer":
        kva = _f(row.get("transformer_kva"))
        return (kva / 1000 if kva else None), "MVA"
    if cls == "lv_switchgear":
        return _f(row.get("bus_amps")), "A"
    return None, ""


def load_evidence(path: str | Path, cls: str, size: float | None) -> list[Evidence]:
    out = []
    doc_id = Path(path).stem.replace("_", "-")
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["equipment_class"] != cls:
                continue
            lo_b, hi_b = _f(r["band_min"]), _f(r["band_max"])
            banded = lo_b is not None or hi_b is not None
            if banded and size is not None and not ((lo_b or 0) <= size <= (hi_b or float("inf"))):
                continue
            low, high, kind = _f(r["low_weeks"]), _f(r["high_weeks"]), r["kind"]
            if low is None:
                continue
            if kind == "floor" or high is None:
                high = low * 1.25
            elif kind == "average":
                low, high = low * 0.9, low * 1.1
            elif kind == "range_open_high":
                high = high * 1.1
            w = next((wt for key, wt in BASIS_WEIGHT if key in r["basis"].lower()), 0.5)
            if not banded:
                w *= 0.6  # not specific to this size
            notes = [] if banded else ["source does not give a size band"]
            if "citing" in r["source_org"].lower() and "terrapin" in r["source_org"].lower():
                w *= 0.4  # secondary report of a source already counted
                notes.append("repeats Terrapin data; down-weighted to avoid double counting")
            out.append(Evidence(r["id"], low, high, w, f"{r['source_org']} ({r['published']})",
                                Citation(doc_id=doc_id, page=1, locator=f"{r['id']} ({r['band']})", quote=r["quote"]),
                                notes=notes))
    _flag_dissent(out)
    return out


def _flag_dissent(ev: list[Evidence]) -> None:
    """A source whose range doesn't overlap the weighted middle of the others is dissent: kept, shown, down-weighted."""
    if len(ev) < 3:
        return
    for e in ev:
        others = [o for o in ev if o is not e]
        q = _quantiles(others, (0.25, 0.75))
        if e.high < q[0] * 0.8 or e.low > q[1] * 1.25:
            e.dissent, e.weight = True, e.weight * 0.2
            e.notes.append(f"far from the other sources ({q[0]:.0f}-{q[1]:.0f} wk); kept as dissent, down-weighted")


def _quantiles(ev: list[Evidence], qs=(0.1, 0.5, 0.9)) -> list[float]:
    """Quantiles of a weighted mixture of uniform ranges (weeks), by integrating on a grid."""
    total = sum(e.weight for e in ev)
    lo, hi = min(e.low for e in ev), max(e.high for e in ev)
    out, cdf, x, qi = [], 0.0, lo, 0
    qs = list(qs)
    while x <= hi + GRID and qi < len(qs):
        dens = sum(e.weight / max(e.high - e.low, GRID) for e in ev if e.low <= x < e.high) / total
        cdf += dens * GRID
        while qi < len(qs) and cdf >= qs[qi] - 1e-9:
            out.append(x + GRID)
            qi += 1
        x += GRID
    out += [hi] * (len(qs) - len(out))
    return out


def _p_late(ev: list[Evidence], weeks_available: float) -> float:
    total = sum(e.weight for e in ev)
    late = 0.0
    for e in ev:
        span = max(e.high - e.low, GRID)
        frac = min(1.0, max(0.0, (e.high - max(weeks_available, e.low)) / span))
        late += e.weight * frac
    return late / total


def _d(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


def assess_delivery_risk(schedule_path: str, po_path: str, evidence_path: str, as_of: str,
                         submittal_results: dict[str, str] | None = None,
                         bid_lead_times: dict[str, dict] | None = None) -> ToolResult:
    """submittal_results: {tag_group: 'approve'|'review'|'reject'} from check_submittal.
    bid_lead_times: {tag_group: {bidder: {min_weeks, max_weeks, basis, citation?}}} from level_bids, used to
    compare bidders for items not yet ordered."""
    t0 = time.time()
    today = date.fromisoformat(as_of)
    with open(schedule_path, newline="", encoding="utf-8") as f:
        sched = {r["tag"]: r for r in csv.DictReader(f)}
    with open(po_path, newline="", encoding="utf-8") as f:
        pos = list(csv.DictReader(f))
    submittal_results = submittal_results or {}
    bid_lead_times = bid_lead_times or {}

    findings, rows = [], []
    for po in pos:
        tags = po["tags"].split(";")
        row = sched[tags[0]]
        cls = CLASS_BY_SECTION.get(row["spec_section"], "")
        size, unit = size_of(row, cls)
        need = _d(row["need_on_site"])
        market = load_evidence(evidence_path, cls, size)

        scenarios = {}  # name -> (evidence list, start date, submittal weeks, notes, vendor citation)
        quoted = _f(po.get("quoted_min_weeks"))
        if po["status"] == "placed":
            start = _d(po["po_date"])
            approved = _d(po.get("submittal_approved"))
            ev = list(market)
            sub_weeks, notes = 0.0, [f"ordered {po['po_date']} from {po['vendor']}"]
            if quoted is not None:
                vc = Citation(doc_id="po-status", page=1, locator=f"{po['tag_group']} / {po['quote_source']}",
                              quote=po["quote_text"])
                ev.append(Evidence("VENDOR", quoted, _f(po["quoted_max_weeks"]), 2.0, f"vendor quote ({po['quote_source']})", vc))
                if po["quote_basis"] == "after_submittal_approval":
                    if approved:
                        start, notes = approved, notes + [f"lead time counts from submittal approval {approved}"]
                    else:
                        sub_weeks = SUBMITTAL_PREP + SUBMITTAL_REVIEW
            scenarios["as ordered"] = (ev, start, sub_weeks, notes)
        else:
            start = today + timedelta(weeks=PROCURE_WEEKS)
            base_sub = SUBMITTAL_PREP + SUBMITTAL_REVIEW
            if submittal_results.get(po["tag_group"]) == "reject":
                base_sub += RESUBMITTAL
            scenarios["market (not ordered)"] = (list(market), start, 0.0,
                                                 [f"not ordered; assumes PO by {start} (today + {PROCURE_WEEKS:.0f} wk)"])
            for bidder, q in (bid_lead_times.get(po["tag_group"]) or {}).items():
                mn, mx = _f(q.get("min_weeks")), _f(q.get("max_weeks"))
                if mn is None:
                    continue
                cit = Citation(**q["citation"]) if q.get("citation") else None
                ev = [e for e in market] + [Evidence("VENDOR", mn, mx or mn, 2.0, f"{bidder} bid lead time",
                                                     cit or Citation(doc_id=bidder, page=1, quote=f"{mn}-{mx} weeks"))]
                resub = q.get("resubmittal", submittal_results.get(po["tag_group"]) == "reject")
                sw = (SUBMITTAL_PREP + SUBMITTAL_REVIEW + (RESUBMITTAL if resub else 0.0)) \
                    if q.get("basis") == "after_submittal_approval" else (RESUBMITTAL if resub else 0.0)
                n = [f"if awarded to {bidder} and ordered by {start}"]
                if resub:
                    n.append("submittal check found deviations: one resubmittal cycle added")
                scenarios[f"award to {bidder}"] = (ev, start, sw, n)

        for name, (ev, start, sub_weeks, notes) in scenarios.items():
            if not ev:
                findings.append(Finding(id=f"F-{po['tag_group']}-{name}", claim=f"{po['tag_group']}: no lead-time evidence",
                                        status=Verdict.missing, confidence=0.3, why=f"no published lead times for {cls}"))
                continue
            p10, p50, p80, p90 = _quantiles(ev, (0.1, 0.5, 0.8, 0.9))
            arrive = {k: start + timedelta(weeks=sub_weeks + w) for k, w in (("P10", p10), ("P50", p50), ("P90", p90))}
            available = (need - start).days / 7 - sub_weeks
            p_late = round(_p_late(ev, available), 2)
            float_p50 = (need - arrive["P50"]).days // 7
            latest_order = need - timedelta(weeks=sub_weeks + p80)
            level = "high" if p_late >= 0.5 else "medium" if p_late >= 0.2 else "low"
            actions = []
            if po["status"] != "placed":
                actions.append(f"place the order by {latest_order} for an 80% chance of arriving by {need}"
                               + (" - that date has already passed" if latest_order < today else ""))
            if level != "low":
                actions.append("ask the vendor for a confirmed production slot and a dated shipping commitment")
                actions.append(f"plan for arrival around {arrive['P50']} (P50) and protect the install sequence; "
                               "consider temporary/rental equipment for commissioning if P90 is past energisation")
            if any(e.dissent for e in ev):
                actions.append("sources disagree: see dissenting evidence before relying on the low end")
            verdict = Verdict.deviates if level == "high" else Verdict.unclear if level == "medium" else Verdict.complies
            cites = [e.citation for e in ev]
            conf = 0.85 if len(ev) >= 3 else 0.7 if len(ev) == 2 else 0.55
            findings.append(Finding(
                id=f"F-{po['tag_group']}-{name.replace(' ', '_')}",
                claim=f"{po['tag_group']} ({len(tags)} x {row['item']}), {name}: P50 arrival {arrive['P50']}, "
                      f"need {need}, P(late) {p_late:.0%}",
                status=verdict, confidence=conf, citations=cites,
                why="; ".join(notes + [f"{len(ev)} evidence sources"]),
                data={"tag_group": po["tag_group"], "tags": tags, "scenario": name, "need_on_site": str(need),
                      "arrival": {k: str(v) for k, v in arrive.items()},
                      "lead_weeks": {"P10": p10, "P50": p50, "P90": p90}, "submittal_weeks": sub_weeks,
                      "p_late": p_late, "risk": level, "float_weeks_at_P50": float_p50,
                      "latest_order_date_80pct": str(latest_order), "actions": actions,
                      "evidence": [{"id": e.id, "range_weeks": [e.low, e.high], "weight": round(e.weight, 2),
                                    "source": e.label, "dissent": e.dissent, "notes": e.notes} for e in ev]}))
            rows.append({"tag_group": po["tag_group"], "scenario": name, "need": str(need), "P10": str(arrive["P10"]),
                         "P50": str(arrive["P50"]), "P90": str(arrive["P90"]), "p_late": p_late, "risk": level})

    ranked = sorted(rows, key=lambda r: (-r["p_late"], r["P50"]))
    res = ToolResult(tool="assess_delivery_risk", findings=findings,
                     result={"as_of": as_of, "ranked": ranked,
                             "method": "weighted mixture of cited published lead-time ranges (+ vendor quote, weight 2), "
                                       "plus procurement and submittal cycles; no model calls"},
                     run=RunInfo(models=[], latency_ms=int((time.time() - t0) * 1000)))
    return res.finalize()
