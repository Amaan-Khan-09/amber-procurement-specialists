"""discover_vendors and prequalify_vendors: who could supply this, and may we buy from them?

discover_vendors (code only, no model calls). From the vendor master (data/vendors/supplier_directory.csv), the
spec's list of acceptable manufacturers (verified quote) and the checks of each manufacturer's datasheet, it lists
every vendor that could supply the requirement, sets aside those that cannot (with the record that says why) and ranks
the rest on points a buyer can audit: product fit on five key ratings (with the datasheet quotes), manufacturer named
by the spec, bid received and its lead time, service distance and on-time history. Nothing comes from model memory:
a vendor that is not in a record we hold is not suggested.

prequalify_vendors (model reads, code decides). Each criterion has a source (the spec paragraph or the owner's
pre-qualification policy, cited). The model reads the supplier's packet and reports a value and the exact words for
each criterion; code verifies the words on the page, takes the value only if it is in those words, and decides:
meets, fails or needs_verification. A criterion is never "met" on a claim that cannot be checked from the documents
(the federal exclusion list is checked by the owner; a self-certification is recorded, not trusted). Readings are
saved, so a decision can be replayed with no model call.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import date
from pathlib import Path

from . import docs
from .llm import LLM, LLMError
from .verify import verify

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "data" / "vendors" / "supplier_directory.csv"
POLICY = ROOT / "data" / "vendors" / "prequal_policy_ALPHA.pdf"
PACKETS = ROOT / "data" / "vendors" / "packets"
SPEC = ROOT / "data" / "specs" / "project_alpha" / "26_32_13_engine_generators_ALPHA.pdf"
READINGS = ROOT / "examples" / "prequal"
SCREEN = ["R01", "R02", "R09", "R10", "R12"]  # the five ratings a buyer screens first (as in find_products)

ACCEPTABLE = ["Caterpillar", "Cummins", "Detroit Diesel", "Kohler", "Stewart & Stevenson", "Waukesha-Pearce"]

CRITERIA = [
    {"id": "P1", "source": "spec", "locator": "1.4.A", "anchor": "Manufacturers: Provide products complying with these specifications",
     "text": "Manufacturer is one of those the spec names", "kind": "manufacturer", "ask": "the manufacturer of the equipment offered"},
    {"id": "P2", "source": "spec", "locator": "1.4.G", "anchor": "minimum of 10 years",
     "text": "Manufacturer has produced engine-alternator sets for at least 10 years", "kind": "numeric", "op": ">=", "value": 10,
     "ask": "how many years the manufacturer has produced engine-generator sets"},
    {"id": "Q1", "source": "policy", "locator": "PQ-01 Q1", "anchor": "Commercial general liability insurance of at least $2,000,000 per occurrence",
     "text": "General liability insurance >= $2,000,000 per occurrence", "kind": "numeric", "op": ">=", "value": 2_000_000,
     "ask": "commercial general liability insurance, amount per occurrence"},
    {"id": "Q2", "source": "policy", "locator": "PQ-01 Q2", "anchor": "must remain valid through the equipment need date",
     "text": "Insurance certificate valid through the need date", "kind": "date", "op": ">=", "value": "need_date",
     "ask": "the expiry date of the general liability insurance certificate"},
    {"id": "Q3", "source": "policy", "locator": "PQ-01 Q3", "anchor": "Experience modification rate (EMR) of 1.00 or lower",
     "text": "EMR (three-year average) <= 1.00", "kind": "numeric", "op": "<=", "value": 1.0,
     "ask": "the experience modification rate (EMR), three-year average"},
    {"id": "Q4", "source": "policy", "locator": "PQ-01 Q4", "anchor": "A current letter from the manufacturer authorizing the supplier",
     "text": "Manufacturer's authorization letter attached", "kind": "attached",
     "ask": "whether a manufacturer authorization letter is attached (copy the sentence)"},
    {"id": "Q5", "source": "policy", "locator": "PQ-01 Q5", "anchor": "Emergency service response within 4 hours at the site",
     "text": "Named service branch, 24/7 emergency response within 4 hours", "kind": "service",
     "ask": "the emergency service arrangement: the branch named and the response time (copy the sentence)"},
    {"id": "Q6", "source": "policy", "locator": "PQ-01 Q6", "anchor": "At least three completed projects with generator sets of 1500 kW",
     "text": ">= 3 completed projects with sets of 1500 kW or larger in the last 5 years", "kind": "projects", "min": 3, "kw": 1500, "years": 5,
     "ask": "every completed project listed: name, year, set size in kW (one entry per table row, copy the row)"},
    {"id": "Q7", "source": "policy", "locator": "PQ-01 Q7", "anchor": "The supplier must not be excluded from federal procurement",
     "text": "Not excluded from federal procurement (owner checks SAM.gov)", "kind": "owner_check",
     "ask": "any statement about debarment, suspension or exclusion (copy the sentence)"},
]

PREQUAL_SYSTEM = """You read a supplier's pre-qualification documents for a construction project. For each criterion id,
report what the documents state. Copy the exact words from the document as the quote (one row or one sentence, no
paraphrase), give its page number, and give the value as written. If the documents do not state it, use null.
For a list of projects, return one entry per row. Return JSON only:
{"C1": {"value": "...", "quote": "...", "page": 1}, "Q6": {"rows": [{"project": "...", "year": "...", "kw": "...", "quote": "...", "page": 1}]}}"""


def _num(s) -> float | None:
    m = re.search(r"\d[\d,]*(?:\.\d+)?", str(s or ""))
    return float(m.group(0).replace(",", "")) if m else None


def _date(s) -> date | None:
    m = re.search(r"(20\d\d)-(\d\d)-(\d\d)", str(s or ""))
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def load_directory(path: Path = DIRECTORY) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for i, r in enumerate(rows, start=2):
        r["_row"] = i  # spreadsheet row, for citing the record
    return rows


def _dir_cite(r: dict, fields: list[str]) -> dict:
    return {"doc_id": "supplier-directory", "page": r["_row"], "locator": f"vendor master row {r['_row']} ({r['vendor_id']})",
            "quote": "; ".join(f"{f}={r.get(f, '')}" for f in fields), "match": "record"}


def _spec_cite(c: dict) -> dict | None:
    doc = docs.load(SPEC if c["source"] == "spec" else POLICY)
    cite = verify(doc, c["anchor"], locator=c["locator"])
    return cite.model_dump(mode="json") if cite else None


# ---------------------------------------------------------------- discovery

def discover_vendors(requirement: dict, product_fit: dict[str, dict], bids: dict[str, dict] | None = None,
                     directory: list[dict] | None = None) -> dict:
    """requirement: {"tag", "item", "kw", "class"}. product_fit: manufacturer -> {"product", "complies", "deviates",
    "open", "quotes", "provisional"} from the datasheet checks. bids: vendor_id -> {"bid", "lead_max_weeks", "citation"}."""
    directory = directory or load_directory()
    bids = bids or {}
    spec_doc = docs.load(SPEC)
    listed = verify(spec_doc, "Manufacturers: Provide products complying with these specifications and produced by one of the following", locator="1.4.A")
    ranked, excluded = [], []
    for r in directory:
        cites = [_dir_cite(r, ["role", "manufacturers", "product_classes", "max_genset_kw", "sells_new"])]
        classes = r["product_classes"].split(";")
        why_out = None
        if requirement["class"] not in classes:
            why_out = f"does not supply {requirement['class']}s (product classes: {r['product_classes']})"
        elif r["sells_new"] != "yes":
            why_out = f"a {r['role']} company: does not sell new equipment"
        elif r["max_genset_kw"] and float(r["max_genset_kw"]) < requirement["kw"]:
            why_out = f"largest set supplied is {r['max_genset_kw']} kW; {requirement['kw']:g} kW is required"
        if why_out:
            excluded.append({"vendor_id": r["vendor_id"], "name": r["name"], "why": why_out, "citations": cites})
            continue
        mfrs = r["manufacturers"].split(";")
        on_list = [m for m in mfrs if any(m.lower() in a.lower() or a.lower() in m.lower() for a in ACCEPTABLE)]
        fit = next((product_fit[m] for m in mfrs if m in product_fit), None)
        points, reasons = 0.0, []
        if on_list:
            points += 2
            reasons.append(f"+2 {on_list[0]} is named by the spec (1.4.A)")
        else:
            reasons.append(f"+0 {mfrs[0]} is not named by the spec (1.4.A): only as an approved equal, an engineer decides")
        if fit:
            p = fit["complies"] - 2 * fit["deviates"]
            points += p
            reasons.append(f"{p:+g} {fit['product']}: {fit['complies']} of {len(SCREEN)} key ratings met"
                           + (f", {fit['deviates']} not met" if fit["deviates"] else "")
                           + (f", open: {', '.join(fit['open'])}" if fit["open"] else "")
                           + (" (provisional: the exact model is not confirmed)" if fit.get("provisional") else ""))
            cites += fit.get("quotes", [])[:3]
        else:
            reasons.append("+0 no datasheet of this manufacturer's product in the library: ask for one")
        b = bids.get(r["vendor_id"])
        if b:
            points += 1
            reasons.append(f"+1 bid received ({b['bid']})")
            if b.get("lead_max_weeks"):
                lp = round(max(0.0, (74 - b["lead_max_weeks"]) / 10), 1)  # 0 at the slowest bid, +2 at 54 weeks
                points += lp
                reasons.append(f"{lp:+g} quoted lead time up to {b['lead_max_weeks']:g} weeks")
            if b.get("citation"):
                cites.append(b["citation"])
        if r["branch_miles_to_site"] and float(r["branch_miles_to_site"]) <= 150:
            points += 1
            reasons.append(f"+1 service branch {r['service_branch']} {r['branch_state']}, {r['branch_miles_to_site']} miles from site")
        else:
            reasons.append(f"+0 service branch {r['service_branch']} {r['branch_state']} is {r['branch_miles_to_site']} miles from site")
        if r["on_time_24mo"]:
            ot = float(r["on_time_24mo"])
            points += round(2 * ot - 1, 2)
            reasons.append(f"{2 * ot - 1:+.2f} on-time deliveries {ot:.0%} over 24 months (vendor master)")
        else:
            reasons.append("+0 no delivery history with us")
        cites.append(_dir_cite(r, ["service_branch", "branch_miles_to_site", "on_time_24mo", "record_updated"]))
        ranked.append({"vendor_id": r["vendor_id"], "name": r["name"], "manufacturers": mfrs, "points": round(points, 2),
                       "reasons": reasons, "product": fit["product"] if fit else None, "on_spec_list": bool(on_list),
                       "needs_engineer": not on_list, "citations": cites})
    ranked.sort(key=lambda v: -v["points"])
    for i, v in enumerate(ranked, 1):
        v["rank"] = i
    return {"requirement": requirement, "ranked": ranked, "excluded": excluded,
            "spec_citation": listed.model_dump(mode="json") if listed else None,
            "note": "Vendors come only from the vendor master; products only from datasheets we hold. Points are listed "
                    "so a buyer can disagree with any of them."}


# ---------------------------------------------------------------- pre-qualification

def _reading_file(doc: docs.Document) -> Path:
    return READINGS / f"{doc.doc_id}-{doc.sha256[:10]}.json"


def read_packet(doc: docs.Document, llm: LLM | None, criteria: list[dict] = CRITERIA, live: bool = True) -> dict:
    """The model's reading of a packet (saved; replayed when the same document is read again)."""
    f = _reading_file(doc)
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    if not live or llm is None:
        return {"_not_read": "no saved reading and model calls are off"}
    text = "\n\n".join(f"[page {p.number}]\n{p.text}" for p in doc.pages)[:14000]
    asks = "\n".join(f"{c['id']}: {c['ask']}" for c in criteria)
    try:
        out = llm.json(PREQUAL_SYSTEM, f"Criteria:\n{asks}\n\nDocuments:\n{text}", max_tokens=2500)
    except LLMError as e:
        return {"_not_read": f"model call failed ({str(e)[:80]})"}
    READINGS.mkdir(parents=True, exist_ok=True)
    rec = {"doc_id": doc.doc_id, "sha256": doc.sha256, "reading": out, "model": getattr(llm, "model", "")}
    f.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    return rec


def _decide(c: dict, item, doc: docs.Document, need_date: date, as_of: date, dir_row: dict | None) -> dict:
    out = {"criterion": c["id"], "text": c["text"], "status": "needs_verification", "citations": [], "why": ""}
    if c["kind"] == "projects":
        rows = (item or {}).get("rows") or []
        ok_rows, seen = [], []
        for r in rows:
            cite = verify(doc, r.get("quote", ""), r.get("page"))
            if not cite:
                continue
            kw, yr = _num(r.get("kw")), _num(r.get("year"))
            if kw is None or str(int(kw)) not in cite.quote.replace(",", ""):
                continue
            seen.append(cite)
            if kw >= c["kw"] and yr and yr >= as_of.year - c["years"]:
                ok_rows.append(cite)
        out["citations"] = [x.model_dump(mode="json") for x in seen]
        if not seen:
            out["why"] = "no project rows could be verified on the page"
        elif len(ok_rows) >= c["min"]:
            out.update(status="meets", why=f"{len(ok_rows)} of {len(seen)} listed projects are {c['kw']} kW or larger "
                                           f"within {c['years']} years (rows verified on the page, counted in code)")
        else:
            out.update(status="fails", why=f"only {len(ok_rows)} of {len(seen)} listed projects are {c['kw']} kW or larger")
        return out
    item = item or {}
    q, v = str(item.get("quote") or ""), item.get("value")
    cite = verify(doc, q, item.get("page")) if q else None
    if c["kind"] == "owner_check":
        out["why"] = ("the owner checks the federal exclusion list (SAM.gov) before award; "
                      + ("the supplier's self-certification is recorded" if cite else "no self-certification found"))
        out["citations"] = [cite.model_dump(mode="json")] if cite else []
        out["route"] = "engineer"
        return out
    if not cite:
        out["why"] = "not stated in the documents received" if not q else f"reported words not found on the page ({q[:60]!r})"
        return out
    out["citations"] = [cite.model_dump(mode="json")]
    text = cite.quote
    if c["kind"] == "manufacturer":
        hit = next((a for a in ACCEPTABLE if a.lower().split()[0] in text.lower()), None)
        out.update(status="meets" if hit else "needs_verification",
                   why=f"{hit} is named by the spec" if hit else "the manufacturer is not named by the spec: only as an approved equal")
        if not hit:
            out["route"] = "engineer"
    elif c["kind"] == "numeric":
        n = _num(v)
        if n is None or not re.search(re.escape(str(v).strip().split()[0]).replace(r"\,", ",?"), text) and _num(text) != n:
            out["why"] = f"the value {v!r} is not in its own quote {text!r}"
        else:
            ok = n >= c["value"] if c["op"] == ">=" else n <= c["value"]
            out.update(status="meets" if ok else "fails", why=f"{v} {'meets' if ok else 'does not meet'} {c['op']} {c['value']:,g}")
    elif c["kind"] == "date":
        d = _date(v) or _date(text)
        if not d or d.isoformat() not in text:
            out["why"] = f"no date in the quote {text!r}"
        elif d >= need_date:
            out.update(status="meets", why=f"expires {d}, after the need date {need_date}")
        else:
            out.update(why=f"expires {d}, before the need date {need_date}: a renewal certificate is needed before award")
    elif c["kind"] == "attached":
        neg = re.search(r"(?i)on request|not attached|to follow|will be provided|upon award", text)
        if re.search(r"(?i)\battached\b", text) and not neg:
            out.update(status="meets", why="the letter is attached")
        else:
            out["why"] = f"not attached ({text[:70]!r}): ask for the letter"
    elif c["kind"] == "service":
        branch = re.search(r"(?i)branch:?\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)*),?\s*([A-Z]{2})\b", text)
        hours = re.search(r"(?i)within\s*(\d+)\s*hours|(\d+)[- ]hour", text)
        hrs = _num(hours.group(0)) if hours else None
        if branch and hrs is not None and hrs <= 4:
            out.update(status="meets", why=f"branch {branch.group(1)}, {branch.group(2)}; response within {hrs:g} hours")
            if dir_row and dir_row.get("service_branch") and dir_row["service_branch"].lower() != branch.group(1).lower():
                out["why"] += (f"; the vendor master lists {dir_row['service_branch']} ({dir_row['record_updated']}): "
                               "update the record")
                out["citations"].append(_dir_cite(dir_row, ["service_branch", "branch_miles_to_site", "record_updated"]))
        else:
            out["why"] = ("no service branch is named" if not branch else f"response time not shown as 4 hours or less")
            if dir_row and dir_row.get("branch_miles_to_site"):
                out["why"] += (f"; the vendor master lists {dir_row['service_branch']} {dir_row['branch_state']}, "
                               f"{dir_row['branch_miles_to_site']} miles from site (record of {dir_row['record_updated']}): "
                               "conflicting records, ask the supplier to name the branch")
                out["citations"].append(_dir_cite(dir_row, ["service_branch", "branch_miles_to_site", "record_updated"]))
    return out


def prequalify(vendor: dict, documents: list[str], need_date: date, as_of: date, llm: LLM | None = None,
               live: bool = True, manufacturer_hint: dict | None = None, dir_row: dict | None = None,
               criteria: list[dict] = CRITERIA) -> dict:
    """vendor: {"vendor_id", "name"}. documents: the packet and any later replies, oldest first (a later document's
    verified answer replaces an open or failed one). manufacturer_hint: {"name", "citation"} from the product link,
    used for P1 when no packet was received."""
    results = {c["id"]: {"criterion": c["id"], "text": c["text"], "status": "needs_verification",
                         "why": "no pre-qualification packet received", "citations": []} for c in criteria}
    read = []
    for path in documents:
        doc = docs.load(path)
        rec = read_packet(doc, llm, criteria, live)
        read.append({"doc": doc.doc_id, "file": Path(path).name, "replayed": "reading" in rec and not live or None,
                     "note": rec.get("_not_read")})
        reading = rec.get("reading") or {}
        for c in criteria:
            if c["id"] not in reading:
                continue
            r = _decide(c, reading.get(c["id"]), doc, need_date, as_of, dir_row)
            prev = results[c["id"]]
            if r["status"] != "needs_verification" or prev["why"] == "no pre-qualification packet received" or not prev["citations"]:
                if prev["status"] == "meets" and r["status"] != "meets":
                    continue
                results[c["id"]] = r
    if manufacturer_hint and results["P1"]["status"] == "needs_verification" and not documents:
        hit = next((a for a in ACCEPTABLE if a.lower().split()[0] in manufacturer_hint["name"].lower()), None)
        if hit:
            results["P1"] = {"criterion": "P1", "text": results["P1"]["text"], "status": "meets",
                             "why": f"{hit} (from the bid's product, via the product link); no packet received",
                             "citations": [manufacturer_hint["citation"]] if manufacturer_hint.get("citation") else []}
    for c in criteria:
        r = results[c["id"]]
        r["source"] = {"source": c["source"], "locator": c["locator"], "citation": _spec_cite(c)}
        r.setdefault("route", "decide" if r["status"] in ("meets", "fails") else "ask_supplier")
    st = [r["status"] for r in results.values()]
    supplier_open = [k for k, r in results.items() if r["status"] == "needs_verification" and r["route"] == "ask_supplier"]
    if "fails" in st:
        overall = "fails"
    elif supplier_open:
        overall = "needs verification"
    else:
        overall = "qualified pending the owner's checks"
    return {"vendor_id": vendor["vendor_id"], "name": vendor["name"], "overall": overall,
            "fails": [k for k, r in results.items() if r["status"] == "fails"], "to_verify": supplier_open,
            "owner_checks": [k for k, r in results.items() if r["route"] == "engineer" and r["status"] == "needs_verification"],
            "criteria": results, "documents": read}


def packet_for(vendor_id: str) -> list[str]:
    p = PACKETS / f"{vendor_id}_prequal.pdf"
    return [str(p)] if p.exists() else []


def doc_hash(paths: list[str]) -> str:
    return hashlib.sha256("|".join(docs.load(p).sha256 for p in paths).encode()).hexdigest()[:12]
