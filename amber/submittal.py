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
import hashlib
import json
import os
import re
import time
from pathlib import Path

from . import checks, docs, retrieve, spec
from .llm import LLM, LLMError
from .schema import Citation, Finding, RunInfo, ToolResult, Verdict
from .verify import MATCH_TRUST, verify

BATCH = 6  # conditions per extraction call
PASSAGES_PER_COND = 3
MAX_CONTEXT_CHARS = 9000  # submittal text per extraction call
SECOND_PASS_PASSAGES = 8  # passages per condition on the second look
SECOND_PASS_CHARS = 12000
JUDGEMENT_CAP = 0.65  # a verdict resting on the model's reading of a verified quote is always for a person to confirm
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
- A qualifier or test condition of another attribute ("at 30% voltage dip", "at 0.8 power factor", "at standby rating", "at full load") is NOT its own condition: keep it inside that attribute's name (e.g. "motor_starting_kva_at_30pct_dip").
- Keep one electrical system together: voltage, phases and wires are ONE text condition (terms like ["277/480","3 phase","4 wire"], match "all"); frequency may be its own numeric condition. Starting-system voltage and electric/motor type are one text condition.
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
- Derating: if a condition is about operating altitude or ambient temperature and the excerpts state a derate or reduction that applies at that condition (e.g. "derates 17.6% per 10 C above 40 C"), set "stated": true, quote that derate sentence, leave "values" empty, and set "meets": "no" when full rating is not kept at the required condition.
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


REQ_CACHE = Path(os.getenv("AMBER_REQ_CACHE", Path(__file__).resolve().parents[1] / "data" / "requirements"))


def _req_cache_file(spec_doc: docs.Document, row: dict, checklist) -> Path:
    """Structured requirements depend only on the spec, the equipment row and the checklist, so they are
    computed once and reused for every submittal checked against that spec."""
    key = json.dumps([spec_doc.sha256, row, checklist], sort_keys=True, ensure_ascii=False)
    return REQ_CACHE / (hashlib.sha256(key.encode()).hexdigest()[:16] + ".json")


def structure_requirements(llm: LLM, spec_doc: docs.Document, row: dict, schedule_id: str,
                           checklist: list[dict] | None = None) -> list[dict]:
    cf = _req_cache_file(spec_doc, row, checklist)
    if cf.exists():
        return json.loads(cf.read_text(encoding="utf-8"))["requirements"]
    out = _structure_requirements(llm, spec_doc, row, schedule_id, checklist)
    if out and all(r.get("conditions") for r in out):  # cache only a complete, error-free structuring
        REQ_CACHE.mkdir(parents=True, exist_ok=True)
        cf.write_text(json.dumps({"spec": spec_doc.doc_id, "tag": row.get("tag"), "model": llm.model,
                                  "requirements": out}, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


def _structure_requirements(llm: LLM, spec_doc: docs.Document, row: dict, schedule_id: str,
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
            reply = llm.json(REQ_SYSTEM, user, max_tokens=3500,
                             purpose="structure spec requirements " + ", ".join(p["req_id"] for p in part))
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


CONFIG_CHARS = 3000
_CONFIG_RX = re.compile(r"bill of materials?|\bbom\b|scope of supply|equipment list|feature code", re.I)


def _config_pages(doc: docs.Document, max_pages: int = 2) -> list[int]:
    """Pages that list the supplied configuration (bill of material etc.): short, high-value, easy to miss."""
    found = [p.number for p in doc.pages if p.text and len(p.text) < 6000 and _CONFIG_RX.search(p.text[:600])]
    return found[:max_pages]


def _context(doc: docs.Document, conds: list[dict], k: int = PASSAGES_PER_COND, limit: int = MAX_CONTEXT_CHARS) -> str:
    chosen: list[tuple[int, str]] = []
    for c in conds:
        q = " ".join([str(c.get("attribute", "")).replace("_", " "), str(c.get("unit") or ""),
                      " ".join(c.get("terms") or []), str(c.get("value") or ""), str(c.get("requirement") or "")])
        for p in retrieve.rank_passages(doc, q, k=k):
            if p not in chosen:
                chosen.append(p)
    blocks, used = [], 0
    for n in _config_pages(doc):  # a bill of material states what is actually supplied: always show it
        blocks.append(f"[page {n}]\n{doc.page(n).text.strip()[:CONFIG_CHARS]}")
    for page, text in chosen:
        if used + len(text) > limit:
            break
        blocks.append(f"[page {page}]\n{text.strip()}")
        used += len(text)
    return "\n\n---\n\n".join(blocks)


OFFER_SCHEMA = {"type": "object", "required": ["offers"], "properties": {"offers": {"type": "array", "items": {
    "type": "object", "required": ["cid", "stated", "values", "unit", "quote", "page", "meets"],
    "properties": {"cid": {"type": "string"}, "stated": {"type": "boolean"},
                   "values": {"type": "array", "items": {"type": "string"}}, "unit": {"type": "string"},
                   "selected": {"type": "boolean"}, "quote": {"type": "string"}, "page": {"type": "integer"},
                   "meets": {"type": "string", "enum": ["yes", "no", "unknown"]}, "note": {"type": "string"}}}}}}


def _limits(llm: LLM) -> dict:
    """Cloud models read big batches; a small local model on a CPU gets small, focused questions instead
    (fewer conditions per call, fewer and shorter excerpts), which is both faster and easier for it."""
    if llm.local:
        return {"batch": 3, "k": 2, "chars": 3500, "k2": 4, "chars2": 5000, "batch2": 3, "batch3": 2}
    return {"batch": BATCH, "k": PASSAGES_PER_COND, "chars": MAX_CONTEXT_CHARS, "k2": SECOND_PASS_PASSAGES,
            "chars2": SECOND_PASS_CHARS, "batch2": 8, "batch3": 3}


def extract_offers(llm: LLM, sub_doc: docs.Document, reqs: list[dict]) -> dict[str, dict]:
    conds = [dict(c, requirement=r.get("requirement")) for r in reqs for c in r["conditions"]]
    offers: dict[str, dict] = {}
    lim = _limits(llm)
    for i in range(0, len(conds), lim["batch"]):
        batch = conds[i:i + lim["batch"]]
        ctx = _context(sub_doc, batch, k=lim["k"], limit=lim["chars"])
        if not ctx:
            continue
        ask = [{k: c.get(k) for k in ("cid", "attribute", "requirement", "kind", "op", "value", "min", "max", "unit", "terms")
                if c.get(k) not in (None, [], "")} for c in batch]
        try:
            reply = llm.json(EXTRACT_SYSTEM, "Conditions:\n" + json.dumps(ask, ensure_ascii=False) +
                             "\n\nSubmittal excerpts:\n" + ctx, max_tokens=2000 if not llm.local else 700,
                             schema=OFFER_SCHEMA, purpose="read submittal: " + ", ".join(c["cid"] for c in batch))
        except LLMError as e:
            for c in batch:
                offers[c["cid"]] = {"cid": c["cid"], "not_checked": f"model unavailable: {str(e)[:100]}"}
            continue
        for o in _items(reply.get("offers", reply), "cid"):
            offers[o.get("cid")] = o

    # Second chance for "not stated": a false 'missing' is a risky claim, so look again with a wider net
    # (more passages per condition) before accepting it. Only conditions the first pass gave up on cost anything.
    again = [c for c in conds if not (offers.get(c["cid"]) or {}).get("stated")
             and not (offers.get(c["cid"]) or {}).get("not_checked")]
    for i in range(0, len(again), lim["batch2"]):
        batch = again[i:i + lim["batch2"]]
        ctx = _context(sub_doc, batch, k=lim["k2"], limit=lim["chars2"])
        if not ctx:
            continue
        ask = [{k: c.get(k) for k in ("cid", "attribute", "requirement", "kind", "op", "value", "min", "max", "unit", "terms")
                if c.get(k) not in (None, [], "")} for c in batch]
        try:
            reply = llm.json(EXTRACT_SYSTEM, "A first read found nothing for these conditions. Read the excerpts again "
                             "carefully, including tables and lists, and report anything that addresses them.\n"
                             "Conditions:\n" + json.dumps(ask, ensure_ascii=False) + "\n\nSubmittal excerpts:\n" + ctx,
                             max_tokens=2000 if not llm.local else 700, schema=OFFER_SCHEMA,
                             purpose="second look for not stated: " + ", ".join(c["cid"] for c in batch))
        except LLMError:
            continue  # keep the first-pass answer
        for o in _items(reply.get("offers", reply), "cid"):
            if o.get("stated"):
                o["second_pass"] = True
                offers[o.get("cid")] = o
    if os.getenv("AMBER_TARGETED_READ", "on").lower() != "off":
        offers = _targeted_reread(llm, sub_doc, conds, offers, lim)
    return offers


_NEGATION = re.compile(r"\bnot\s+(?:included|provided|supplied|available|furnished|offered)\b|\bexcluded\b|\bexclusions?\b"
                       r"|\bby others\b|\bfurnished by others\b|\boptional\b|\bn/?a\b|\bnone\b", re.I)
_DUAL = re.compile(r"(-?\d[\d,]*\.?\d*)\s*\(\s*(-?\d[\d,]*\.?\d*)\s*\)")
_DUAL_HEADER = re.compile(r"([A-Za-z][A-Za-z./°³ ]{0,12}?)\s*\(\s*([A-Za-z][A-Za-z./°³ ]{0,12}?)\s*\)")


def _pick_dual_unit(o: dict, c: dict, cite: Citation, doc: docs.Document) -> dict | None:
    """Datasheets often print 'metric (imperial)': '528.3 (139.6)' under a header 'L/hr (gal./hr)'.
    If the quote is such a pair and the page has a header whose bracketed (or leading) unit is the condition's
    unit, keep the matching number. Otherwise return None and the pair stays ambiguous (unclear)."""
    m = _DUAL.search(cite.quote)
    unit = c.get("unit")
    if not m or not unit or len(o.get("values") or []) < 2:
        return None
    page = doc.page(cite.page)
    for h in _DUAL_HEADER.finditer(page.text if page else ""):
        first, second = h.group(1).strip(), h.group(2).strip()
        if checks.unit_in_text(unit, f" {second} ") and not checks.unit_in_text(unit, f" {first} ") and checks.UNIT_WORDS.get(unit.strip().lower()):
            return dict(o, values=[m.group(2)], unit=unit, dual_unit=f"picked {m.group(2)} by header '{h.group(0).strip()}'")
        if checks.unit_in_text(unit, f" {first} ") and not checks.unit_in_text(unit, f" {second} ") and checks.UNIT_WORDS.get(unit.strip().lower()):
            return dict(o, values=[m.group(1)], unit=unit, dual_unit=f"picked {m.group(1)} by header '{h.group(0).strip()}'")
    return None


def _grounded(values: list, quote: str) -> bool:
    """Every word and number of each reported value occurs in the verified quote (any order, so
    'Electronic governor' is grounded in '...digital electronic isochronous governor')."""
    qt = set(re.findall(r"[a-z0-9]+", checks._squash_keep_words(quote)))
    return bool(values) and all(set(re.findall(r"[a-z0-9]+", checks._squash_keep_words(str(v)))) <= qt for v in values)


_GENERIC = {"the", "and", "for", "with", "load", "full", "rated", "rating", "voltage", "type", "value", "set", "sets",
             "generator", "engine", "system", "standby", "max", "min", "maximum", "minimum", "shall", "must", "per", "from"}


def _attr_words(c: dict) -> set[str]:
    words = re.findall(r"[a-z]{3,}", str(c.get("attribute", "")).lower().replace("_", " "))
    return {w for w in words if w not in _GENERIC}


def _flag_shared_evidence(reqs: list[dict], offers: dict[str, dict]) -> None:
    """One line of a datasheet cannot be the evidence for two different requirements with the same value
    (seen: 'Voltage regulation ... +/-0.25%' offered both as voltage regulation and as THD). When that happens, the
    condition whose own attribute words appear in the quote keeps it; the others are marked for a person."""
    owner = {c["cid"]: (r["req_id"], c) for r in reqs for c in r["conditions"]}
    groups: dict[tuple, list[str]] = {}
    for cid, o in offers.items():
        if cid not in owner or not o.get("stated") or not o.get("quote") or not o.get("values"):
            continue
        key = (re.sub(r"\W+", "", str(o["quote"]).lower()), tuple(sorted(str(v) for v in o["values"])))
        groups.setdefault(key, []).append(cid)
    for cids in groups.values():
        if len({owner[c][0] for c in cids}) < 2:
            continue  # several conditions of one requirement may share a quote naturally
        quote = str(offers[cids[0]]["quote"]).lower()
        score = {c: sum(w in quote for w in _attr_words(owner[c][1])) for c in cids}
        best = max(score.values())
        winners = [c for c in cids if score[c] == best] if best > 0 else []
        keep = winners[0] if len(winners) == 1 else None
        for c in cids:
            if c != keep:
                others = ", ".join(owner[x][0] for x in cids if x != c)
                offers[c] = dict(offers[c], shared_with=others)


def _mentioned(doc: docs.Document, c: dict) -> dict | None:
    """Pages where the condition's distinctive words (4+ letters, not generic) occur. Used to double-check a
    'not stated' answer against the whole document instead of the few passages the model read."""
    words = set(_attr_words(c))
    for t in c.get("terms") or []:
        words |= {w for w in re.findall(r"[a-z]{4,}", str(t).lower()) if w not in _GENERIC}
    words = {w for w in words if len(w) >= 4}
    if not words:
        return None
    hits: dict[str, list[int]] = {}
    for p in doc.pages:
        low = p.text.lower()
        for w in words:
            if re.search(rf"\b{re.escape(w)}", low):
                hits.setdefault(w, []).append(p.number)
    if not hits:
        return None
    pages = sorted({n for ns in hits.values() for n in ns})
    per_page = {n: sum(1 for ns in hits.values() if n in ns) for n in pages}
    return {"words": sorted(hits, key=lambda w: -len(hits[w])), "pages": pages,
            "ranked": sorted(pages, key=lambda n: (-per_page[n], n))}


def _partial_terms(c: dict, evidence: str) -> tuple[list[str], list[str]] | None:
    """For a requirement that needs ALL of several terms: (terms found, terms not found) when some but not all are in the
    evidence. None when there is nothing partial to say (all found, none found, or the terms are alternatives)."""
    terms, how = checks.terms_of(c)
    if how != "all" or len(terms) < 2:
        return None
    sq = checks._squash(evidence)
    got = [t for t in terms if checks._squash(t) in sq]
    return (got, [t for t in terms if t not in got]) if 0 < len(got) < len(terms) else None


def _condition_words(c: dict) -> set[str]:
    words = set(_attr_words(c))
    for t in c.get("terms") or []:
        words |= {w for w in re.findall(r"[a-z]{4,}", str(t).lower()) if w not in _GENERIC}
    return {w for w in words if len(w) >= 4}


def _mention_passages(doc: docs.Document, c: dict, pages: list[int], window: int = 350, limit: int = 2400) -> list[tuple[int, str]]:
    """The stretches of text around the condition's words on the pages that mention it (at most two per page)."""
    words, out, used = _condition_words(c), [], 0
    for n in pages:
        pg = doc.page(n)
        if not pg:
            continue
        text, low = pg.text, pg.text.lower()
        spans = sorted((max(0, m.start() - window), min(len(text), m.end() + window))
                       for w in words for m in re.finditer(rf"\b{re.escape(w)}", low))
        merged: list[list[int]] = []
        for a, b in spans:
            if merged and a <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        for a, b in merged[:2]:
            seg = text[a:b].strip()
            if used + len(seg) > limit:
                return out
            out.append((n, seg))
            used += len(seg)
    return out


TARGETED_ASK = ("A first and a second read found no value for these conditions, but a scan shows the submittal mentions "
                "them. For each condition, read ONLY the passages listed under it. Decide whether the submittal STATES the "
                "required value or feature there. If it does, report it and quote the exact words (verbatim from the "
                "passage). If a passage only mentions it as an option, an extra-cost accessory, a different feature or in "
                "another context, report stated=false and say why in note. Do not guess.")


def _targeted_reread(llm: LLM, doc: docs.Document, conds: list[dict], offers: dict[str, dict], lim: dict) -> dict[str, dict]:
    """Conditions the model gave up on, although the document mentions them, get one more look: exactly the passages that
    mention them. A statement found this way goes through the same quote verification and guards as any other, and is
    never automatic (a person confirms it), so this can only turn a blind 'unclear' into an evidenced answer."""
    todo = []
    for c in conds:
        o = offers.get(c["cid"]) or {}
        if o.get("stated") or o.get("not_checked"):
            continue
        seen = _mentioned(doc, c)
        passages = _mention_passages(doc, c, (seen or {}).get("ranked", [])[:5]) if seen else []
        if passages:
            todo.append((c, passages))
    for i in range(0, len(todo), lim["batch3"]):
        batch = todo[i:i + lim["batch3"]]
        ask = [{k: c.get(k) for k in ("cid", "attribute", "requirement", "kind", "op", "value", "min", "max", "unit", "terms")
                if c.get(k) not in (None, [], "")} for c, _ in batch]
        text = "\n\n".join(f"Passages for condition {c['cid']}:\n" + "\n---\n".join(f"[page {n}]\n{t}" for n, t in ps)
                            for c, ps in batch)
        try:
            reply = llm.json(EXTRACT_SYSTEM, TARGETED_ASK + "\nConditions:\n" + json.dumps(ask, ensure_ascii=False) + "\n\n" + text,
                             max_tokens=1600 if not llm.local else 600, schema=OFFER_SCHEMA,
                             purpose="targeted re-read: " + ", ".join(c["cid"] for c, _ in batch))
        except LLMError:
            continue  # keep the earlier answer
        wanted = {c["cid"] for c, _ in batch}
        for o in _items(reply.get("offers", reply), "cid"):
            if o.get("cid") in wanted and o.get("stated"):
                o["third_look"] = True
                offers[o["cid"]] = o
    return offers


def _decide_condition(c: dict, o: dict | None, sub_doc: docs.Document):
    """-> (Decision, submittal Citation | None, confidence)"""
    if o and o.get("shared_with"):
        return (checks.Decision(Verdict.unclear, f"the same quote and value ({str(o.get('quote'))[:60]!r}) are also the "
                                                 f"evidence for {o['shared_with']}: probably a different attribute", False),
                None, 0.4)
    if o and o.get("not_checked"):
        return checks.Decision(Verdict.unclear, f"not checked ({o['not_checked']})", False), None, 0.0
    if not o or not o.get("stated"):
        # "Not stated" is a claim about the whole document, made after reading a few passages: verify it. If the
        # condition's distinctive words appear anywhere, it is mentioned (partly, as an option...) -> a person reads it.
        seen = _mentioned(sub_doc, c)
        if seen:
            return (checks.Decision(Verdict.unclear, f"no value found, but the submittal mentions "
                                                     f"{', '.join(seen['words'][:3])} on page(s) {seen['pages'][:6]}", False),
                    None, 0.5)
        d = checks.decide(c, None)
        return d, None, (0.8 if not sub_doc.scanned_pages else 0.55)
    cite = verify(sub_doc, o.get("quote", ""), o.get("page"))
    if cite is None:
        return (checks.Decision(Verdict.unclear, f"reported quote not found in the submittal ({o.get('quote', '')[:60]!r}); "
                                                 "value discarded", False), None, 0.4)
    if c.get("kind", "numeric") == "numeric":
        unsupported = checks.values_in_quote([v for v in (o.get("values") or []) if v not in (None, "")], cite.quote)
        if unsupported:  # the quote is real but does not contain what was claimed: no source, no claim
            return (checks.Decision(Verdict.unclear, f"reported value(s) {unsupported} do not appear in the quote "
                                                     f"{cite.quote!r}; discarded", False), cite, 0.4)
        picked = _pick_dual_unit(o, c, cite, sub_doc)
        if picked:
            o = picked
    else:
        # Text conditions are judged on the verified quote, plus only those reported values that are themselves
        # grounded in it: a reported 'UL 2085' next to a quote saying 'UL 2200' must not count as UL 2085.
        raw = " | ".join(str(v) for v in (o.get("values") or []))
        vals = [v for v in (o.get("values") or []) if v not in (None, "") and _grounded([v], cite.quote)]
        o = dict(o, values=vals or [cite.quote], quote_only=not vals and bool(o.get("values")),
                 negated=bool(_NEGATION.search(raw + " | " + cite.quote)))
    d = checks.decide(c, o, evidence=cite.quote)
    if o.get("negated") and d.verdict == Verdict.complies:
        # the required words are there, but so is a negation or a limit ('Included 300-500 kW', 'Not included
        # 600-1200 kW', 'by others'): finding the words is not the same as the requirement being met
        return (checks.Decision(Verdict.unclear, f"the evidence also says something is not included, optional or by "
                                                 f"others ({(raw or cite.quote)[:90]!r}); a person must read it", False),
                cite, 0.5)
    if o.get("quote_only"):
        # none of the reported values is in the quote, so the quote may be about something else: judge it,
        # but never confidently (it goes to a person)
        d = checks.Decision(d.verdict, d.why + "; the reported value is not in the quote, judged on the quote text only", False)
    partial_hit = False
    if c.get("kind") == "text" and d.verdict == Verdict.deviates and str(o.get("meets", "")).lower() != "yes":
        part = _partial_terms(c, " | ".join(str(v) for v in (o.get("values") or [])) + " | " + cite.quote)
        if part:  # some required words are there, others are not written: that is not the same as contradicting them
            d = checks.Decision(Verdict.unclear, f"the evidence shows {', '.join(part[0])} but does not mention "
                                                 f"{', '.join(part[1])}; nothing contradicts it, a person decides", False)
            partial_hit = True
    exact = d.exact
    unit_shown = c.get("kind", "numeric") != "numeric" or checks.unit_in_text(o.get("unit") or c.get("unit"), cite.quote)
    meets = str(o.get("meets", "")).lower()
    values = [v for v in (o.get("values") or []) if v not in (None, "")]
    judged = bool(o.get("quote_only")) or partial_hit or bool(o.get("third_look"))  # capped below the handoff line
    if not values and meets in ("yes", "no") and cite.match in ("exact", "normalized", "compact"):
        # Nothing to compare in code (e.g. a derate sentence), but the model read a quote that is really on the
        # page. Its verdict is used, flagged as judgement and capped so a person always confirms it.
        v = Verdict.complies if meets == "yes" else Verdict.deviates
        d, exact, judged = checks.Decision(v, f"model judgement on verified quote: {cite.quote!r}", False), False, True
    elif c.get("kind") == "text" and d.verdict == Verdict.deviates and meets == "yes" and _grounded(values, cite.quote):
        # the wording differs from the expected terms but the verified quote may still satisfy it
        d = checks.Decision(Verdict.complies, f"model judgement on verified quote: {cite.quote!r}", False)
        exact, judged = False, True
    if not judged and meets in ("yes", "no") and d.verdict in (Verdict.complies, Verdict.deviates):
        model_says = Verdict.complies if meets == "yes" else Verdict.deviates
        if model_says != d.verdict:  # two independent readings disagree: neither is asserted
            d = checks.Decision(Verdict.unclear, f"model reading ({model_says.value}) and code check ({d.verdict.value}) "
                                                 f"disagree: {d.why}", False)
            exact, judged = False, True
    if not judged and c.get("kind") == "text" and d.verdict == Verdict.deviates and meets != "no":
        # a quote that lacks the expected words is not the same as a quote that states something different
        d = checks.Decision(Verdict.unclear, d.why + "; the expected words are missing from the quote but nothing "
                                                     "contradicts the requirement", False)
        exact, judged = False, True
    conf = (0.95 if exact else 0.74) * MATCH_TRUST.get(cite.match, 0.8)
    if o.get("third_look"):
        d = checks.Decision(d.verdict, d.why + "; found on a targeted re-read of the pages that mention it, confirm", d.exact)
    if judged:
        conf = min(conf, JUDGEMENT_CAP)
    if not unit_shown and d.verdict in (Verdict.complies, Verdict.deviates):
        # a number whose unit is not written in its own quote may belong to a different row or column
        conf = min(conf, JUDGEMENT_CAP)
        d = checks.Decision(d.verdict, d.why + f"; unit {o.get('unit') or c.get('unit')} is not shown in the quote, confirm", d.exact)
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


def decide_all(reqs: list[dict], offers: dict[str, dict], sub_doc: docs.Document) -> tuple[list[Finding], list[dict]]:
    """Turn what the model read (offers) into one finding per requirement. All decisions are made here, in code, so
    a saved run can be replayed through it without a model (scripts/replay_decisions.py)."""
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
    return findings, rows


def check_submittal(spec_path: str, submittal_path: str, tag: str, schedule_path: str,
                    checklist: list[dict] | None = None, llm: LLM | None = None, ocr: bool = True,
                    only: list[str] | None = None) -> ToolResult:
    """only: check just these requirement ids (product discovery screens a few key ratings this way)."""
    t0 = time.time()
    llm = llm or LLM()
    reader = None
    if ocr:  # default: cached scan text only, no model calls; AMBER_OCR=gemini|groq|ollama to read new scans; off: none
        from .ocr import reader_from_env
        reader = reader_from_env(meter=llm.meter)
    spec_doc, sub_doc = docs.load(spec_path, ocr=reader), docs.load(submittal_path, ocr=reader)
    schedule_id = docs.doc_id_for(schedule_path)
    row = load_schedule(schedule_path, tag)

    reqs = structure_requirements(llm, spec_doc, row, schedule_id, checklist)
    if only:
        reqs = [r for r in reqs if r["req_id"] in set(only)]
    offers = extract_offers(llm, sub_doc, reqs)
    _flag_shared_evidence(reqs, offers)

    findings, rows = decide_all(reqs, offers, sub_doc)

    counts = {v.value: sum(1 for f in findings if f.status == v) for v in Verdict}
    res = ToolResult(tool="check_submittal", findings=findings,
                     result={"tag": tag, "spec": spec_doc.doc_id, "submittal": sub_doc.doc_id, "summary": counts,
                             "overall": "reject" if counts["deviates"] else
                                        ("review" if counts["unclear"] or counts["missing"] else "approve"),
                             "rows": rows, "unread_scanned_pages": sub_doc.scanned_pages,
                             "provider_switches": list(llm.switched)},
                     run=RunInfo(models=llm.meter.models(), latency_ms=int((time.time() - t0) * 1000),
                                 steps=list(llm.meter.steps)))
    return res.finalize()
