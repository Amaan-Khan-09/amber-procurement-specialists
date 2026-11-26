"""Public registries: who is this supplier legally, have they supplied this equipment before, and are they excluded?

Sources (all official US government sources):
  USAspending.gov API (Treasury, no key)        legal entity names and UEI identifiers of federal award recipients;
                                                 awards by product code (PSC 6115 = generators and generator sets)
  SAM.gov Exclusions API v4 (GSA, needs a key)   THE federal procurement exclusion list. It requires a personal API
                                                 key (free, from a SAM.gov account): set SAM_API_KEY. Without it the
                                                 check is reported as 'lookup unavailable', never as 'not excluded'.
  Consolidated Screening List (trade.gov, no key) export and sanctions screening lists of Commerce, State and Treasury
                                                 (OFAC SDN among them). Not the procurement exclusion list: reported as
                                                 a separate screen.

Every answer records the source, the endpoint, the lookup time (UTC), the legal entity and identifier found, how
confidently it matches the name we hold, and one status:
  confirmed      exactly one entity matches (or the list holds a record for it)
  no match       the source answered and nothing matches
  ambiguous      several different entities match the name: a person picks, with the candidates shown
  unavailable    the source could not be asked (no key, network or server failure): nothing is concluded
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from rapidfuzz import fuzz

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache" / "registries"
USA_RECIPIENT = "https://api.usaspending.gov/api/v2/recipient/"
USA_AWARDS = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
SAM_EXCLUSIONS = "https://api.sam.gov/entity-information/v4/exclusions"
CSL_CSV = "https://data.trade.gov/downloadable_consolidated_screening_list/v1/consolidated.csv"
UA = {"User-Agent": "amber-procurement-specialists (hackathon research tool)", "Content-Type": "application/json"}
_SUFFIX = re.compile(r"\b(inc|incorporated|llc|l\.l\.c|co|corp|corporation|company|ltd|limited|lp|llp|plc|the)\b\.?", re.I)
STRONG, POSSIBLE = 92, 85


class SourceError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _http(url: str, body: dict | None = None, timeout: float = 30) -> bytes:
    """One request; any failure becomes SourceError (a lookup that fails is 'unavailable', never 'no match')."""
    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                     headers=UA, method="POST" if body is not None else "GET")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise SourceError(f"{type(e).__name__}: {str(e)[:120]}") from e


def norm_name(s: str) -> str:
    s = re.sub(r"\(.*?\)", " ", str(s).lower())
    s = _SUFFIX.sub(" ", s)
    return re.sub(r"[^a-z0-9& ]+", " ", re.sub(r"\s+", " ", s)).split("  ")[0].strip()


def score(a: str, b: str) -> float:
    na, nb = norm_name(a), norm_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 100.0
    return float(min(fuzz.token_set_ratio(na, nb), fuzz.ratio(na, nb) + 10))


def _result(source: str, endpoint: str, query: str, status: str, **kw) -> dict:
    return {"source": source, "endpoint": endpoint, "query": query, "looked_up": _now(), "status": status, **kw}


# ------------------------------------------------------------------ legal entity (USAspending)

def lookup_entity(name: str, http=_http) -> dict:
    src = "USAspending.gov recipient search (U.S. Treasury)"
    try:
        data = json.loads(http(USA_RECIPIENT, {"keyword": norm_name(name) or name, "limit": 50}))
    except SourceError as e:
        return _result(src, USA_RECIPIENT, name, "unavailable", why=f"the source could not be reached ({e})")
    cands = {}
    for r in data.get("results") or []:
        sc = score(name, r.get("name", ""))
        if sc < POSSIBLE:
            continue
        key = r.get("uei") or r.get("name")
        if key not in cands or sc > cands[key]["match"]:
            cands[key] = {"legal_entity": r.get("name"), "uei": r.get("uei"), "match": round(sc, 1),
                          "federal_award_total": r.get("amount"), "level": r.get("recipient_level")}
    ranked = sorted(cands.values(), key=lambda c: -c["match"])
    if not ranked:
        return _result(src, USA_RECIPIENT, name, "no match", candidates=[],
                       why=f"the name search returned {data.get('page_metadata', {}).get('total', 0)} records; none matches the name")
    strong = [c for c in ranked if c["match"] >= STRONG]
    if len(strong) == 1 and (len(ranked) == 1 or ranked[1]["match"] < STRONG):
        c = strong[0]
        return _result(src, USA_RECIPIENT, name, "confirmed", legal_entity=c["legal_entity"], uei=c["uei"],
                       match=c["match"], candidates=ranked[:5], why=f"one entity matches ({c['match']:.0f}/100)")
    return _result(src, USA_RECIPIENT, name, "ambiguous", candidates=ranked[:8],
                   why=f"{len(ranked)} different entities match the name; a person picks the right one by address or UEI")


# ------------------------------------------------------------------ discovery from federal awards (USAspending)

def federal_suppliers(psc: str = "6115", states: tuple = ("VA", "MD", "DC", "PA", "WV", "NC"), since: str = "2021-10-01",
                      http=_http) -> dict:
    """Vendors with federal awards for this product code, performed near the site, grouped by legal entity."""
    src = f"USAspending.gov award search, product code {psc} (U.S. Treasury)"
    body = {"filters": {"award_type_codes": ["A", "B", "C", "D"], "psc_codes": [psc],
                        "time_period": [{"start_date": since, "end_date": datetime.now().strftime("%Y-%m-%d")}],
                        "place_of_performance_locations": [{"country": "USA", "state": s} for s in states]},
            "fields": ["Award ID", "Recipient Name", "Recipient UEI", "Award Amount", "Description", "Awarding Agency",
                       "Start Date", "Place of Performance State Code"],
            "limit": 100, "sort": "Award Amount", "order": "desc"}
    try:
        rows = json.loads(http(USA_AWARDS, body)).get("results") or []
    except SourceError as e:
        return _result(src, USA_AWARDS, f"PSC {psc} in {', '.join(states)}", "unavailable", vendors=[], why=str(e))
    by = {}
    for r in rows:
        k = r.get("Recipient UEI") or r.get("Recipient Name")
        v = by.setdefault(k, {"legal_entity": r.get("Recipient Name"), "uei": r.get("Recipient UEI"), "awards": 0,
                              "total": 0.0, "latest": "", "evidence": []})
        v["awards"] += 1
        v["total"] += float(r.get("Award Amount") or 0)
        v["latest"] = max(v["latest"], r.get("Start Date") or "")
        if len(v["evidence"]) < 2:
            v["evidence"].append({"award_id": r.get("Award ID"), "agency": r.get("Awarding Agency"), "date": r.get("Start Date"),
                                  "state": r.get("Place of Performance State Code"), "amount": r.get("Award Amount"),
                                  "description": str(r.get("Description") or "")[:140],
                                  "url": f"https://www.usaspending.gov/award/{r.get('generated_internal_id', '')}"})
    vendors = sorted(by.values(), key=lambda v: (-v["awards"], -v["total"]))
    return _result(src, USA_AWARDS, f"PSC {psc} performed in {', '.join(states)} since {since}", "confirmed" if vendors else "no match",
                   vendors=vendors, why=f"{len(rows)} awards, {len(vendors)} legal entities")


# ------------------------------------------------------------------ exclusions (SAM.gov v4, needs a key)

def sam_exclusions(name: str, uei: str | None = None, http=_http, key: str | None = None) -> dict:
    src = "SAM.gov Exclusions API v4 (GSA)"
    key = key if key is not None else os.getenv("SAM_API_KEY", "")
    if not key:
        return _result(src, SAM_EXCLUSIONS, uei or name, "unavailable",
                       why="SAM.gov requires a personal API key (free, from a SAM.gov account); set SAM_API_KEY. "
                           "Until then the federal exclusion check is NOT done, and the owner checks sam.gov by hand.")
    q = f"ueiSAM={uei}" if uei else "exclusionName=" + urllib.request.quote(name)
    try:
        data = json.loads(http(f"{SAM_EXCLUSIONS}?api_key={key}&{q}"))
    except SourceError as e:
        return _result(src, SAM_EXCLUSIONS, uei or name, "unavailable", why=f"the source could not be reached ({str(e).replace(key, '***')})")
    recs = data.get("excludedEntity") or data.get("exclusionDetails") or []
    hits = []
    for r in recs:
        ident = r.get("exclusionIdentification") or {}
        nm = ident.get("entityName") or " ".join(filter(None, [ident.get("firstName"), ident.get("lastName")]))
        sc = 100.0 if uei and ident.get("ueiSAM") == uei else score(name, nm)
        if sc >= POSSIBLE:
            hits.append({"legal_entity": nm, "uei": ident.get("ueiSAM"), "match": sc,
                         "exclusion_type": (r.get("exclusionDetails") or {}).get("exclusionType"),
                         "agency": (r.get("exclusionDetails") or {}).get("excludingAgencyName")})
    if not hits:
        return _result(src, SAM_EXCLUSIONS, uei or name, "no match", total_records=data.get("totalRecords"),
                       why="no active exclusion record matches")
    strong = [h for h in hits if h["match"] >= STRONG]
    status = "confirmed" if len(strong) == 1 else "ambiguous"
    return _result(src, SAM_EXCLUSIONS, uei or name, status, candidates=hits[:5],
                   why="an exclusion record matches: the supplier is excluded" if status == "confirmed"
                   else "several exclusion records resemble the name: a person checks identity")


# ------------------------------------------------------------------ export / sanctions screening (trade.gov CSL, no key)

_CSL_MEMO: dict = {}


def _csl_rows(http=_http, max_age_h: float = 24) -> tuple[list[dict], str]:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / "consolidated.csv"
    if http is not _http:  # a test passes its own source: never touch the real cache
        return list(csv.DictReader(io.StringIO(http(CSL_CSV).decode("utf-8", "replace")))), _now()
    if not f.exists() or time.time() - f.stat().st_mtime > max_age_h * 3600:
        f.write_bytes(http(CSL_CSV, timeout=90))
        _CSL_MEMO.clear()
    fetched = datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
    if fetched not in _CSL_MEMO:
        csv.field_size_limit(10_000_000)
        _CSL_MEMO.clear()
        _CSL_MEMO[fetched] = list(csv.DictReader(io.StringIO(f.read_text(encoding="utf-8", errors="replace"))))
    return _CSL_MEMO[fetched], fetched


def screening_list(name: str, http=_http) -> dict:
    src = "Consolidated Screening List (trade.gov: Commerce, State, Treasury export and sanctions lists)"
    try:
        rows, fetched = _csl_rows(http)
    except SourceError as e:
        return _result(src, CSL_CSV, name, "unavailable", why=f"the list could not be downloaded ({e})")
    hits = []
    for r in rows:
        names = [r.get("name", "")] + [a for a in (r.get("alt_names") or "").split(";") if a.strip()]
        best = max((score(name, n) for n in names), default=0)
        if best >= POSSIBLE:
            hits.append({"listed_name": r.get("name"), "list": r.get("source"), "match": round(best, 1),
                         "country": r.get("addresses", "")[:60], "id": r.get("_id") or r.get("id")})
    hits.sort(key=lambda h: -h["match"])
    if not hits:
        return _result(src, CSL_CSV, name, "no match", list_downloaded=fetched, records_searched=len(rows),
                       why=f"{len(rows)} listed parties searched; none matches")
    strong = [h for h in hits if h["match"] >= 97]
    return _result(src, CSL_CSV, name, "confirmed" if len(strong) == 1 else "ambiguous", list_downloaded=fetched,
                   candidates=hits[:5], why="a listed party matches the name" if len(strong) == 1 else
                   "listed parties resemble the name: a person checks identity before concluding anything")


def screen_supplier(name: str, http=_http, uei: str | None = None) -> dict:
    """All three checks for one supplier. uei: an identifier already known for it (from an award record): the identity
    is then settled by identifier, not by resemblance of names."""
    ent = lookup_entity(name, http=http)
    if uei and ent["status"] != "unavailable":
        hit = next((c for c in ent.get("candidates") or [] if c.get("uei") == uei), None)
        ent = dict(ent, status="confirmed", uei=uei, legal_entity=(hit or {}).get("legal_entity") or name, match=(hit or {}).get("match"),
                   why=f"identified by UEI {uei} taken from its federal award record" + ("" if hit else " (name search did not return it)"))
    uei = ent.get("uei") if ent["status"] == "confirmed" else None
    return {"name": name, "entity": ent, "sam_exclusions": sam_exclusions(name, uei, http=http),
            "screening_list": screening_list(name, http=http)}


# ------------------------------------------------------------------ discovery of real suppliers for one requirement

SIZE_WORDS = {2000: ["2000 KW", "2000KW", "2 MW", "2MW", "1500 KW", "2500 KW"],
              1000: ["1000 KW", "1000KW", "1 MW", "1MW", "750 KW", "1250 KW"]}
_SERVICE = re.compile(r"(?i)\b(inspect\w*|maint\w*|repair\w*|service\w*|upgrade|test\w*|install\w*|parts?)\b")
_RENTAL = re.compile(r"(?i)\b(lease|leasing|rent|rental)\b")


def kind_of_work(description: str) -> str:
    """What the award record says was bought: never more than the words say."""
    d = description or ""
    return "rental" if _RENTAL.search(d) else "service" if _SERVICE.search(d) else "supply"


def kw_in(description: str) -> float | None:
    found = []
    for n, unit in re.findall(r"(?i)(\d[\d,]*(?:\.\d+)?)\s*-?\s*(kw|mw)\b", description or ""):
        v = float(n.replace(",", ""))
        found.append(v * 1000 if unit.lower() == "mw" else v)
    return max(found) if found else None


def public_discovery(kw: float = 2000, since: str = "2019-01-01", http=_http) -> dict:
    """Legal entities whose federal award records mention generator work at this size (PSC 6115, nationwide), ranked by
    what the record establishes: supply of the size > rental > service. A record is not a pre-qualification."""
    src = "USAspending.gov award search, product code 6115 with size keywords (U.S. Treasury)"
    words = SIZE_WORDS.get(int(kw), [f"{kw:g} KW"])
    body = {"filters": {"award_type_codes": ["A", "B", "C", "D"], "psc_codes": ["6115"], "keywords": words,
                        "time_period": [{"start_date": since, "end_date": datetime.now().strftime("%Y-%m-%d")}]},
            "fields": ["Award ID", "Recipient Name", "Recipient UEI", "Award Amount", "Description", "Awarding Agency",
                       "Start Date", "Place of Performance State Code"], "limit": 100, "sort": "Award Amount", "order": "desc"}
    query = f"PSC 6115 awards since {since} mentioning {', '.join(words)}"
    try:
        rows = json.loads(http(USA_AWARDS, body)).get("results") or []
    except SourceError as e:
        return _result(src, USA_AWARDS, query, "unavailable", candidates=[], why=str(e))
    by: dict = {}
    for r in rows:
        desc = str(r.get("Description") or "")
        key = r.get("Recipient UEI") or r.get("Recipient Name")
        v = by.setdefault(key, {"legal_entity": r.get("Recipient Name"), "uei": r.get("Recipient UEI"), "evidence": []})
        v["evidence"].append({"award_id": r.get("Award ID"), "date": r.get("Start Date"), "agency": r.get("Awarding Agency"),
                              "state": r.get("Place of Performance State Code"), "amount": r.get("Award Amount"),
                              "description": desc[:200], "work": kind_of_work(desc), "kw": kw_in(desc),
                              "url": f"https://www.usaspending.gov/award/{r.get('generated_internal_id', '')}"})
    order = {"supply": 0, "rental": 1, "service": 2}
    for v in by.values():
        v["evidence"].sort(key=lambda e: (order[e["work"]], -(e["kw"] or 0), e["date"] or ""))
        best = v["evidence"][0]
        v["establishes"] = best["work"]
        v["largest_kw"] = max((e["kw"] or 0) for e in v["evidence"]) or None
        points = {"supply": 3, "rental": 1, "service": 0.5}[best["work"]]
        sized = bool(v["largest_kw"] and v["largest_kw"] >= 0.75 * kw)
        points += 2 if sized else 0
        points += min(len(v["evidence"]), 3) * 0.2
        v["points"] = round(points, 2)
        v["why"] = (f"{len(v['evidence'])} award record(s); best one is {best['work']}"
                    + (f" mentioning {v['largest_kw']:g} kW" if v["largest_kw"] else "")
                    + f" ({best['agency']}, {best['date']}, {best['state']}): {best['description'][:90]!r}")
        v["not_established"] = ("willingness to bid, manufacturer authorization, service coverage near the site, insurance, "
                                "safety record: all need pre-qualification")
    ranked = sorted(by.values(), key=lambda v: -v["points"])
    return _result(src, USA_AWARDS, query, "confirmed" if ranked else "no match", candidates=ranked,
                   why=f"{len(rows)} award records, {len(ranked)} legal entities")


SNAPSHOT = ROOT / "examples" / "registry" / "snapshot.json"


def refresh_snapshot(bidder_names: list[str], kw: float = 2000, top: int = 5, http=_http) -> dict:
    """Real lookups, saved with their times so the demo and tests replay them."""
    disc = public_discovery(kw, http=http)
    screens = {}
    for v in disc.get("candidates", [])[:top]:
        screens[v["legal_entity"]] = screen_supplier(v["legal_entity"], http=http, uei=v.get("uei"))
    for n in bidder_names:
        screens[n] = screen_supplier(n, http=http)
    snap = {"taken": _now(), "discovery": disc, "screens": screens}
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(snap, indent=1), encoding="utf-8")
    return snap


def snapshot() -> dict | None:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.exists() else None


# ------------------------------------------------------------------ a pre-qualification scorecard for a REAL supplier

NOT_CHECKABLE = [("Licensing", "state contractor or dealer licence: not looked up"),
                 ("Safety record", "EMR or OSHA history: needs the insurer's letter; not looked up"),
                 ("Finances", "financial standing: not looked up"),
                 ("Insurance", "certificate of insurance: only the supplier can provide it"),
                 ("Manufacturer authorization", "authorization letter: only the supplier or manufacturer can provide it"),
                 ("Service response", "branch and response time near the site: only the supplier can state it")]


def scorecard(candidate: dict, screen: dict | None) -> dict:
    """pass / flag / fail / not verified for each criterion, from public records only. Nothing is passed on the strength
    of an absence: 'not verified' says exactly what is missing."""
    screen = screen or {}
    ent, sam, csl = (screen.get(k) or {} for k in ("entity", "sam_exclusions", "screening_list"))
    rows = []

    def add(name, status, why, source="", looked_up="", url=""):
        rows.append({"criterion": name, "status": status, "why": why, "source": source, "looked_up": looked_up, "url": url})

    add("Legal entity identified", "pass" if ent.get("status") == "confirmed" else "flag" if ent.get("status") == "ambiguous" else "not verified",
        ent.get("why", "not looked up") + (f"; UEI {ent['uei']}" if ent.get("uei") else ""), ent.get("source", ""), ent.get("looked_up", ""))
    best = (candidate.get("evidence") or [{}])[0]
    kind = candidate.get("establishes")
    add("Has supplied equipment of this size", "pass" if kind == "supply" and candidate.get("largest_kw") else "flag",
        f"best federal award record shows {kind or 'nothing'}" + (f" mentioning {candidate['largest_kw']:g} kW" if candidate.get("largest_kw") else "")
        + f": {str(best.get('description', ''))[:110]!r}" + ("" if kind == "supply" else " (not a supply record)"),
        "USAspending.gov award record", best.get("date", ""), best.get("url", ""))
    add("Not excluded from federal procurement",
        "fail" if sam.get("status") == "confirmed" else "pass" if sam.get("status") == "no match" else "not verified",
        sam.get("why", "not looked up"), sam.get("source", "SAM.gov Exclusions"), sam.get("looked_up", ""))
    add("Export and sanctions screen (not the exclusion list)",
        "pass" if csl.get("status") == "no match" else "flag" if csl.get("status") in ("confirmed", "ambiguous") else "not verified",
        csl.get("why", "not looked up"), csl.get("source", ""), csl.get("looked_up", ""))
    for name, why in NOT_CHECKABLE:
        add(name, "not verified", why)
    st = [r["status"] for r in rows]
    overall = "fail" if "fail" in st else "flag" if ("flag" in st or "not verified" in st) else "pass"
    return {"legal_entity": candidate.get("legal_entity"), "uei": candidate.get("uei"), "overall": overall, "criteria": rows,
            "meaning": "flag: nothing disqualifying found, but it cannot be approved until the open criteria are evidenced"}


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Public-record check of a supplier (saved lookups unless --live).")
    ap.add_argument("name", nargs="?", help="legal entity name; default: every discovered candidate in the saved snapshot")
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args()
    snap = refresh_snapshot([]) if a.live and not a.name else snapshot() or {"discovery": {"candidates": []}, "screens": {}}
    cands = snap["discovery"].get("candidates", [])
    if a.name:
        cand = next((c for c in cands if norm_name(a.name) == norm_name(c["legal_entity"])), {"legal_entity": a.name})
        scr = screen_supplier(a.name, uei=cand.get("uei")) if a.live else snap["screens"].get(cand["legal_entity"])
        cands, screens = [cand], {cand["legal_entity"]: scr}
    else:
        screens = snap["screens"]
    for c in cands:
        if not screens.get(c["legal_entity"]):
            continue
        s = scorecard(c, screens[c["legal_entity"]])
        print(f"\n{s['legal_entity']}  (UEI {s['uei'] or '-'})  overall: {s['overall'].upper()}")
        for r in s["criteria"]:
            print(f"  {r['status']:13} {r['criterion']:52} {r['why'][:110]}")


if __name__ == "__main__":
    main()
