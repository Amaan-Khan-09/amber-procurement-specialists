"""check_submittal: does a supplier's submittal meet the spec, requirement by requirement?

Pipeline (the model extracts, code decides, every quote is verified):
  1. requirements  spec clause (+ the tag's schedule row) -> requirement with one or more typed
                   conditions; the spec quote is verified against the spec, schedule values are
                   cited to the schedule row
  2. retrieve      for each condition, the few submittal passages most likely to answer it
  3. extract       what the submittal offers for each condition, with a quote that is verified
  4. decide        checks.decide() per condition, in code; a requirement passes only if all its
                   conditions pass; confidence from evidence; under 0.70 goes to a person
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path

from . import checks, docs, retrieve, spec
from .llm import LLM, LLMError
from .schema import Citation, Finding, RunInfo, ToolResult, Verdict
from .verify import MATCH_TRUST, verify

BATCH = 6  # conditions per extraction call
PASSAGES_PER_COND = 3
MAX_CONTEXT_CHARS = 9000  # submittal text per extraction call
OCR_CAP = 0.65  # max confidence for anything resting on OCR text (always below the 0.70 handoff line)

REQ_SYSTEM = """You turn construction specification clauses into checkable requirements for a product submittal review.
Rules:
- Use only the clause text and the equipment schedule row. Never invent values.
- "quote": copy 6-30 consecutive words EXACTLY from the clause text (same spelling and punctuation). Never put schedule values into the quote.
- Split each requirement into "conditions", each checking ONE attribute:
  - numeric: {"cid","attribute","kind":"numeric","op":">=|<=|==|between","value"|"min"+"max","unit","source":"clause|schedule","schedule_field":"<column if source is schedule>"}
    units like kW, kVA, V, A, Hz, rpm, gph, °F, °C, %, h, hp, ft, W.
  - text: {"cid","attribute","kind":"text","terms":[...],"match":"any|all"} where terms are 1-3 short words a supplier would print (e.g. "brushless", "electronic", "class h"). Use "any" for alternatives (e.g. ["8 cylinder","12 cylinder","16 cylinder"] or ["class f","class h"] for "Class F or better").
- Direction of op: capabilities and ratings the product must reach (kW, kVA, motor-starting kVA, max ambient it can run in, tank hours, short-circuit rating) use ">="; limits it must stay under (fuel consumption, THD, voltage dip, regulation band, rpm, noise) use "<=". Fixed characteristics (voltage, phases, Hz, pole count) use "==" or text terms.
- Where the clause says "as scheduled"/"scheduled on the drawings", take the value from the schedule row and set source "schedule".
Reply with JSON: {"requirements": [{"req_id","locator","requirement":"plain words","quote","conditions":[...]}]}"""

EXTRACT_SYSTEM = """You read excerpts of a supplier's product submittal and report what it states for each condition.
Rules:
- Report only what the excerpts state. If a condition is not addressed, set "stated": false.
- "quote": copy 3-20 consecutive words EXACTLY from one excerpt (same spelling, numbers and units), containing the value.
- "page": the page number of the excerpt the quote is from.
- "values": every option the submittal offers for that attribute, as printed (e.g. several voltages or radiator ratings).
- "unit": the unit of the values as printed. Each value is ONE number in that unit. If the submittal prints two units side by side (e.g. "L/hr (gph): 528.3 (139.6)"), report the number in the condition's unit (139.6 with unit "gph").
- Checkbox lists (❑, ☐) mark OPTIONAL accessories: an unticked option is not "stated" as supplied; say so in "note".
- "selected": true only if the submittal clearly marks which option is supplied for this project, otherwise null.
- "meets": "yes", "no" or "unknown": does what is stated satisfy the condition?
- For ratings, report STANDBY when the condition is about standby; never substitute prime.
Reply with JSON: {"offers": [{"cid","stated","values":[...],"unit","selected","quote","page","meets","note"}]}"""


def load_schedule(path: str | Path, tag: str) -> dict:
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["tag"] == tag:
                return {k: v for k, v in row.items() if v}
    raise KeyError(f"tag {tag} not in schedule {path}")


def _items(obj, key: str) -> list[dict]:
    """Accept a list of objects or a dict keyed by id; drop anything malformed."""
    if isinstance(obj, dict):
        if key in obj:
            return [obj]
        obj = [dict(v, **{key: k}) for k, v in obj.items() if isinstance(v, dict)]
    return [o for o in obj if isinstance(o, dict)] if isinstance(obj, list) else []


def _schedule_citation(cond: dict, row: dict, schedule_id: str) -> Citation | None:
    """Cite the schedule cell a value came from, only if the cell really holds that value."""
    field = cond.get("schedule_field")
    if not field or field not in row:
        return None
    try:
        if abs(float(row[field]) - float(cond.get("value"))) > 1e-6:
            return None
    except (TypeError, ValueError):
        if str(row[field]).lower() != str(cond.get("value")).lower():
            return None
    return Citation(doc_id=schedule_id, page=1, locator=f"{row['tag']} / {field}", quote=f"{field} = {row[field]}")


def structure_requirements(llm: LLM, spec_doc: docs.Document, row: dict, schedule_id: str,
                           checklist: list[dict] | None = None) -> list[dict]:
    clauses = spec.products(spec.parse(spec_doc))
    if checklist:
        payload = []
        for item in checklist:
            anchor = (item.get("spec_anchor") or "").lower()
            c = next((c for c in clauses if anchor and c.text.lower().startswith(anchor)), None) \
                or next((c for c in clauses if c.locator == item["spec_locator"].split(" ")[0]), None)
            if c:
                payload.append({"req_id": item["req_id"], "locator": c.cite_label(), "page": c.page,
                                "clause": c.text, "focus": item["requirement"]})
    else:
        payload = [{"req_id": f"R{i + 1:02d}", "locator": c.cite_label(), "page": c.page, "clause": c.text}
                   for i, c in enumerate(clauses)]

    out: list[dict] = []
    for i in range(0, len(payload), 7):
        part = payload[i:i + 7]
        user = ("Equipment schedule row for this tag:\n" + json.dumps(row) +
                "\n\nClauses. When 'focus' is given, write exactly one requirement for that focus, with that req_id:\n" +
                json.dumps(part, ensure_ascii=False))
        src = {p["req_id"]: p for p in part}
        try:
            reply = llm.json(REQ_SYSTEM, user, max_tokens=3500)
        except LLMError as e:  # keep going: these requirements are reported as not checked, never as missing
            for p in part:
                out.append({"req_id": p["req_id"], "locator": p["locator"], "requirement": p.get("focus") or p["clause"][:120],
                            "conditions": [], "error": f"model unavailable: {str(e)[:100]}"})
            continue
        for r in _items(reply.get("requirements", reply), "req_id"):
            s = src.get(r.get("req_id"), {})
            cite = verify(spec_doc, r.get("quote", ""), s.get("page"), s.get("locator", r.get("locator", "")))
            if cite is None and s.get("clause"):
                # fall back to citing the clause opening, which is certainly on the page
                cite = verify(spec_doc, " ".join(s["clause"].split()[:12]), s.get("page"), s.get("locator", ""))
                if cite:
                    cite.match = "clause"
            r["locator"] = s.get("locator", r.get("locator"))
            r["spec_citation"] = cite.model_dump() if cite else None
            conds = [c for c in r.get("conditions", []) if isinstance(c, dict)]
            for j, c in enumerate(conds):
                c["cid"] = f"{r['req_id']}{chr(97 + j)}"
                if c.get("source") == "schedule":
                    sc = _schedule_citation(c, row, schedule_id)
                    c["schedule_citation"] = sc.model_dump() if sc else None
            r["conditions"] = conds
            out.append(r)
    return out


def _context(doc: docs.Document, conds: list[dict]) -> str:
    chosen: list[tuple[int, str]] = []
    for c in conds:
        q = " ".join([str(c.get("attribute", "")).replace("_", " "), str(c.get("unit") or ""),
                      " ".join(c.get("terms") or []), str(c.get("value") or ""), str(c.get("requirement") or "")])
        for p in retrieve.rank_passages(doc, q, k=PASSAGES_PER_COND):
            if p not in chosen:
                chosen.append(p)
    blocks, used = [], 0
    for page, text in chosen:
        if used + len(text) > MAX_CONTEXT_CHARS:
            break
        blocks.append(f"[page {page}]\n{text.strip()}")
        used += len(text)
    return "\n\n---\n\n".join(blocks)


def extract_offers(llm: LLM, sub_doc: docs.Document, reqs: list[dict]) -> dict[str, dict]:
    conds = [dict(c, requirement=r.get("requirement")) for r in reqs for c in r["conditions"]]
    offers: dict[str, dict] = {}
    for i in range(0, len(conds), BATCH):
        batch = conds[i:i + BATCH]
        ctx = _context(sub_doc, batch)
        if not ctx:
            continue
        ask = [{k: c.get(k) for k in ("cid", "attribute", "requirement", "kind", "op", "value", "min", "max", "unit", "terms")
                if c.get(k) not in (None, [], "")} for c in batch]
        try:
            reply = llm.json(EXTRACT_SYSTEM, "Conditions:\n" + json.dumps(ask, ensure_ascii=False) +
                             "\n\nSubmittal excerpts:\n" + ctx, max_tokens=2000)
        except LLMError as e:
            for c in batch:
                offers[c["cid"]] = {"cid": c["cid"], "not_checked": f"model unavailable: {str(e)[:100]}"}
            continue
        for o in _items(reply.get("offers", reply), "cid"):
            offers[o.get("cid")] = o
    return offers


def _decide_condition(c: dict, o: dict | None, sub_doc: docs.Document):
    """-> (Decision, submittal Citation | None, confidence)"""
    if o and o.get("not_checked"):
        return checks.Decision(Verdict.unclear, f"not checked ({o['not_checked']})", False), None, 0.0
    if not o or not o.get("stated"):
        d = checks.decide(c, None)
        return d, None, (0.8 if not sub_doc.scanned_pages else 0.55)
    cite = verify(sub_doc, o.get("quote", ""), o.get("page"))
    if cite is None:
        return (checks.Decision(Verdict.unclear, f"reported quote not found in the submittal ({o.get('quote', '')[:60]!r}); "
                                                 "value discarded", False), None, 0.4)
    d = checks.decide(c, o, evidence=cite.quote)
    exact = d.exact
    meets = str(o.get("meets", "")).lower()
    grounded = all(checks._squash(str(v)) in checks._squash(cite.quote) for v in (o.get("values") or []))
    if c.get("kind") == "text" and d.verdict == Verdict.deviates and meets == "yes" and grounded:
        # the wording differs from the expected terms but the verified quote may still satisfy it
        d = checks.Decision(Verdict.complies, f"model judgement on verified quote: {cite.quote!r}", False)
        exact = False
    conf = (0.95 if exact else 0.74) * MATCH_TRUST.get(cite.match, 0.8)
    if cite.ocr:
        # vision OCR can misread digits and model numbers (seen: KD1000 read as KD2000), so evidence from
        # a scanned page is a candidate for a person to confirm, never an automatic pass or fail
        conf = min(conf, OCR_CAP)
        d = checks.Decision(d.verdict, d.why + f"; read from scanned page {cite.page} by OCR, confirm against the scan",
                            d.exact)
    return d, cite, conf


def _combine(parts: list[tuple]) -> tuple[Verdict, str, float]:
    verdicts = [d.verdict for d, _, _ in parts]
    conf = min(c for _, _, c in parts)
    why = "; ".join(f"{d.why}" for d, _, _ in parts)
    if Verdict.deviates in verdicts:
        return Verdict.deviates, why, conf
    if Verdict.unclear in verdicts:
        return Verdict.unclear, why, conf
    if all(v == Verdict.missing for v in verdicts):
        return Verdict.missing, why, conf
    if Verdict.missing in verdicts:
        return Verdict.unclear, "only partly stated: " + why, min(conf, 0.6)
    return Verdict.complies, why, conf


def check_submittal(spec_path: str, submittal_path: str, tag: str, schedule_path: str,
                    checklist: list[dict] | None = None, llm: LLM | None = None, ocr: bool = True) -> ToolResult:
    t0 = time.time()
    llm = llm or LLM()
    reader = None
    if ocr:
        from .ocr import VisionOCR
        reader = VisionOCR(meter=llm.meter)
    spec_doc, sub_doc = docs.load(spec_path, ocr=reader), docs.load(submittal_path, ocr=reader)
    schedule_id = docs.doc_id_for(schedule_path)
    row = load_schedule(schedule_path, tag)

    reqs = structure_requirements(llm, spec_doc, row, schedule_id, checklist)
    offers = extract_offers(llm, sub_doc, reqs)

    findings, rows = [], []
    for r in reqs:
        rid = r["req_id"]
        spec_cite = Citation(**r["spec_citation"]) if r.get("spec_citation") else None
        parts = [_decide_condition(c, offers.get(c["cid"]), sub_doc) for c in r["conditions"]]
        if not parts:
            verdict, why, conf = Verdict.unclear, r.get("error") or "requirement could not be turned into a checkable condition", \
                0.0 if r.get("error") else 0.3
        else:
            verdict, why, conf = _combine(parts)
        if spec_cite is None:
            conf, why = min(conf, 0.5), why + "; spec quote not verified"
        cites = [spec_cite] if spec_cite else []
        cites += [Citation(**c["schedule_citation"]) for c in r["conditions"] if c.get("schedule_citation")]
        cites += [cite for _, cite, _ in parts if cite]
        detail = [{"cid": c["cid"], "attribute": c.get("attribute"), "condition": checks._describe(c),
                   "verdict": d.verdict.value, "why": d.why,
                   "offered": {k: (offers.get(c["cid"]) or {}).get(k) for k in ("values", "unit", "selected", "quote", "page", "meets")}}
                  for c, (d, _, _) in zip(r["conditions"], parts)]
        findings.append(Finding(id=f"F-{rid}", claim=r.get("requirement", ""), status=verdict, confidence=round(conf, 3),
                                citations=cites, why=why, data={"req_id": rid, "locator": r.get("locator"), "conditions": detail}))
        rows.append({"req_id": rid, "locator": r.get("locator"), "requirement": r.get("requirement"),
                     "verdict": verdict.value, "confidence": round(conf, 3)})

    counts = {v.value: sum(1 for f in findings if f.status == v) for v in Verdict}
    res = ToolResult(tool="check_submittal", findings=findings,
                     result={"tag": tag, "spec": spec_doc.doc_id, "submittal": sub_doc.doc_id, "summary": counts,
                             "overall": "reject" if counts["deviates"] else
                                        ("review" if counts["unclear"] or counts["missing"] else "approve"),
                             "rows": rows, "unread_scanned_pages": sub_doc.scanned_pages,
                             "provider_switches": list(llm.switched)},
                     run=RunInfo(models=llm.meter.models(), latency_ms=int((time.time() - t0) * 1000)))
    return res.finalize()
