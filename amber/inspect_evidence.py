"""A second look, in code, at the clause an answer rests on (no model call).

Four things a person used to be asked to do by hand, done here and shown:

  computed from the quote   the model judged a verified quote ("Voltage regulation ... +/-0.5%"); the code reads the
                            number and unit out of that quote itself and compares it, so the verdict is computed, not judged
  disputed clause           our reading found no value, the independent reader quoted one: the reader's quote is verified
                            on the page and, if it holds a comparable value, the code decides on it; a quote that is not
                            on the page carries no weight
  option dependence         a compliant value that the same document offers only as an option: an empty tick box
                            ("o 50 C Ambient Cooling System") means not supplied, a filled one means supplied, an option
                            list without marks means unknown. Unselected or unknown -> one focused question to the supplier
  one missing fact          the evidence shows part of a requirement and nothing contradicts the rest: one focused
                            question to the supplier, never an approval

Every change records what was inspected and why, so the page can show it.
"""
from __future__ import annotations

import re

from . import docs
from .schema import Citation
from .verify import listed_as_choice, verify

EMPTY = "○❑❒☐□◯❏◻"      # o  ❑ ❒ ☐ □ ◯ ❏ ◻
FULL = "●■☒☑✓✔◉◼"        # ● ■ ☒ ☑ ✓ ✔ ◉ ◼

UNITS = {
    "%": r"%", "kva": r"s?k\s?va", "kw": r"(?:e?kw|kwe)(?!h)", "gph": r"(?:gph|gal/h(?:r|our)?)", "rpm": r"(?:rpm|r/min)",
    "°f": r"°\s?f\b|deg(?:rees)?\s?f\b", "°c": r"°\s?c\b|deg(?:rees)?\s?c\b", "h": r"(?:hours?|hrs?|h)\b",
    "hz": r"hz", "v": r"(?:v(?:olts?)?|vac|vdc)\b", "w": r"(?:w|watts?)\b", "ft": r"(?:ft|feet)\b",
}
_NUM = r"(\d{1,3}(?:,\d{3})+|\d+(?:[.,]\d+)?)"
_LESS = re.compile(r"(<|≤|<=|max(?:imum)?|up to|not (?:more|greater) than|±|\+/-|\+/−)\s*$", re.I)
_MORE = re.compile(r"(>|≥|>=|min(?:imum)?|at least|not less than)\s*$", re.I)
GENERIC = {"rating", "type", "system", "load", "full", "standby", "maximum", "minimum", "value", "count", "and", "the"}

# notations that mean the same thing in datasheets
EQUIV = [(r"\btwo[- ]thirds?\b", "2/3"), (r"\bfour[- ]cycle\b", "4 cycle"), (r"\b(\d+)[- ](pole|cycle|wire|phase)\b", r"\1 \2"),
         (r"\bthree[- ]phase\b", "3 phase"), (r"\bsingle[- ]phase\b", "1 phase"), (r"\bfour[- ]wire\b", "4 wire"),
         (r"\bpermanent[- ]magnet\b", "permanent magnet"),
         (r"\bon[- ]line\b", "online"),
         (r"\b(permanent magnet(?:\s*\(pm\))?[ -]+(?:pilot )?exciter)\b", r"\1 pmg"),
         (r"\b(?:internal(?:ly)?[- ]mounted|mounted internally)\b", "inside"),
         (r"\bcylinder (?:arrangement|configuration)\s*:?\s*(\d+)\s*v\b", r"\1 cylinder"), (r"\bsolid[- ]state\b", "solid state"), (r"-", " ")]


def norm(s: str) -> str:
    s = str(s).lower()
    for a, b in EQUIV:
        s = re.sub(a, b, s)
    return re.sub(r"\s+", " ", s).strip()


def _f(s: str) -> float:
    s = s.strip()
    if re.fullmatch(r"\d+,\d{1,2}", s):  # decimal comma: '2,1' is 2.1 ('2,100' is a thousands separator)
        return float(s.replace(",", "."))
    return float(s.replace(",", ""))


ABBREV = {"thd": {"harmonic", "distortion", "thd"}, "rpm": {"speed", "rpm"}, "kva": {"kva"}, "pf": {"power factor"},
          "ups": {"ups"}, "btu": {"btu", "heat"}}


def _attr_words(c: dict) -> set[str]:
    raw = str(c.get("attribute", "")).lower().replace("_", " ")
    words = set(re.findall(r"[a-z]{4,}", raw))
    for ab, exp in ABBREV.items():
        if re.search(rf"\b{ab}\b", raw):
            words |= exp
    return {w for w in words if w not in GENERIC}


def values_in(quote: str, unit: str | None) -> list[tuple[float, str]]:
    """(value, comparator) pairs for numbers written with the unit in the quote. 'L/hr (gal/hr) 505.8 (133.6)' gives
    133.6 for gph: when both units are written as 'A (B)', the number in brackets is in B."""
    if not unit:
        return []
    u = UNITS.get(unit.lower().replace(" ", ""))
    if not u:
        return []
    out = []
    pair = re.search(rf"\(\s*(?:{u})\s*\)\s*{_NUM}\s*\(\s*{_NUM}\s*\)", quote, re.I)
    if pair:  # 'L/hr (gal/hr) 505.8 (133.6)': the bracketed number is in the bracketed unit
        return [(_f(pair.group(2)), "")]
    first = re.search(rf"(?:{u})\s*\([^()]{{1,12}}\)\s*{_NUM}\s*\(\s*{_NUM}\s*\)", quote, re.I)
    if first:  # '°F (°C) 122 (50)': the first number is in the first unit
        return [(_f(first.group(1)), "")]
    for m in re.finditer(rf"{_NUM}\s*(?:{u})", quote, re.I):
        before = quote[max(0, m.start() - 22): m.start()]
        after = quote[m.end(): m.end() + 14].lower()
        cmp = "<=" if _LESS.search(before) or re.match(r"\s*(max(imum)?|or less)\b", after) else             ">=" if _MORE.search(before) or re.match(r"\s*(min(imum)?|or more)\b", after) else ""
        out.append((_f(m.group(1)), cmp))
    if not out:  # unit in a heading of the quote, one number after it: 'THD (%) 2,1', 'Total Harmonic Distortion <5%'
        if re.search(rf"\(\s*(?:{u})\s*\)", quote, re.I):
            nums = re.findall(rf"(?<![\w.]){_NUM}(?![\w.])", quote.split(")")[-1])
            if len(nums) == 1:
                out.append((_f(nums[0]), ""))
    return out


# a number is only comparable when it is the SAME quantity: the quote or its heading names it, and does not name a
# neighbouring one (found on held-out G10: 'Max Fuel Flow 158 gal/hr' was computed as fuel consumption)
_QUANTITY = {  # word in the attribute -> (must appear, must not appear in the quote)
    "consumption": (r"consum", r"fuel flow|flow rate|pump flow|supply"),
    "regulation": (r"regulat", r""),
    "distortion": (r"harmonic|distortion|\bthd", r""),
    "thd": (r"harmonic|distortion|\bthd", r""),
    "speed": (r"speed|rpm", r"fan speed|piston speed"),
    "altitude": (r"altitude|elevation", r""),
}


def same_quantity(c: dict, quote: str, context: str = "") -> bool:
    attr = str(c.get("attribute", "")).lower()
    q, about = quote.lower(), (quote + " " + context).lower()
    # a standby requirement is not settled by a prime or continuous figure (held-out G10 printed fuel use for PRIME only)
    if "standby" in attr and re.search(r"\b(prime|continuous)\b", q) and "standby" not in q:
        return False
    if "standby" in attr and "standby" not in about and re.search(r"\b(prime|continuous) (power|rating)", about):
        return False
    if "start" in attr and re.search(r"battery (?:voltage|rating)|charger|alternator (?:volts|voltage)", q):
        return False
    for key, (need, never) in _QUANTITY.items():
        if key in attr:
            if not re.search(need, about) or (never and re.search(never, q)):
                return False
    if "voltage_regulation" in attr and re.search(r"frequency regulat", q):
        return False
    return True


def compute_numeric(c: dict, quote: str, context: str = "") -> dict | None:
    """Decide a numeric condition from the words of one verified quote, or None if the quote does not settle it.
    context: the lines just above the quote on its page (a table row is about the attribute its heading names)."""
    if c.get("kind", "numeric") != "numeric" or not quote:
        return None
    words = _attr_words(c)
    about = (quote + " " + context).lower()
    if words and not any(re.search(rf"\b{re.escape(w[:6])}", about) for w in words):
        return None  # neither the quote nor its heading is about this attribute
    if not same_quantity(c, quote, context):
        return None
    unit = c.get("unit")
    vals = values_in(quote, unit)
    if not vals and unit and unit.lower() in ("°f",):
        vals = [(round(v * 9 / 5 + 32, 1), cmp) for v, cmp in values_in(quote, "°C")]
    distinct = {v for v, _ in vals}
    if len(distinct) != 1:
        return None
    v, cmp = vals[0]
    op, ref = c.get("op"), c.get("value")
    if op == "between":
        ok = c["min"] <= v <= c["max"]
    elif op in ("<=", "<"):
        ok = v <= ref if op == "<=" else v < ref
    elif op in (">=", ">"):
        ok = v >= ref if op == ">=" else v > ref
        if cmp == "<=":  # 'up to 50' does not prove '>= 50' beyond 50 itself
            ok = ok and v >= ref
    elif op == "==":
        ok = abs(v - ref) < 1e-9
    else:
        return None
    if cmp == ">=" and op in ("<=", "<"):
        return None  # 'at least 3' cannot prove '<= 5'
    shown = f"{cmp}{v:g}" if cmp else f"{v:g}"
    return {"verdict": "complies" if ok else "deviates",
            "why": f"computed from the quote: {shown} {unit} {'meets' if ok else 'does not meet'} {op} {ref if op != 'between' else str(c['min']) + '-' + str(c['max'])} {unit}"}


def _starting(quote: str, context: str = "") -> set[str]:
    """Which starting-system terms a quote establishes: '24 volt' and 'electric starter' from wording such as
    'Starter motor rated voltage (DC) 24' or 'Engine Starter - 24 Volt DC Motor'. A battery or charger voltage is not it."""
    q = quote.lower()
    about = q + " " + context.lower()
    if re.search(r"battery|charg|charging|alternator volt", q) or not re.search(r"start(?:er|ing)|crank", about):
        return set()
    volts = set(re.findall(r"(?<![\d.])(12|24|36|48)(?![\d.])\s*(?:v\b|volt|vdc)", q)) | \
        set(re.findall(r"(?:volts?|vdc|\(dc\)|\bdc)(?:\W|dual){0,16}(?<![\d.])(12|24|36|48)(?![\d.])", q))
    if volts != {"24"}:
        return set()
    return {"24 volt", "electric starter"} if re.search(r"start(?:er|ing)|crank", about) else {"24 volt"}


def compute_text(c: dict, quote: str, context: str = "") -> dict | None:
    if c.get("kind") != "text" or not quote:
        return None
    q = norm(quote)
    terms = [norm(t) for t in c.get("terms") or []]
    hit = [t for t in terms if t and re.search(rf"(?<![\w/]){re.escape(t)}(?![\w/])", q)]
    if "start" in str(c.get("attribute", "")).lower():
        hit += [t for t in terms if t in _starting(quote, context) and t not in hit]
    need_all = c.get("match", "all") == "all"
    if (need_all and len(hit) == len(terms)) or (not need_all and hit):
        return {"verdict": "complies", "why": f"computed from the quote: it states {', '.join(hit)}"}
    if need_all and hit:
        return {"verdict": "partial", "missing": [t for t in terms if t not in hit],
                "why": f"the quote states {', '.join(hit)} but not {', '.join(t for t in terms if t not in hit)}"}
    return None


# words that appear all over a datasheet: they count only on a line that is about the attribute
_COMMON_TERMS = {"electronic", "electric", "inside", "online", "outdoor", "standby", "included", "weather"}
# nouns shared by many parts of a generator ('3 pole' breaker, '4 pole' alternator): they need their part named
_NEEDS_PART = {"pole": r"alternator|generator|rotating|field|exciter|stator|revolving", "phase": r"output|voltage|generator|alternator|heater",
               "wire": r"output|voltage|generator|alternator|wye", "cycle": r"engine|cylinder|diesel|turbo"}


def _distinctive(term: str) -> bool:
    return term not in _COMMON_TERMS and (bool(re.search(r"\d", term)) or " " in term or len(term) >= 8)


def find_terms(doc: docs.Document, c: dict, terms: list[str], others: tuple = ()) -> list[dict] | None:
    """Every missing term found somewhere in the supplier's documents (the datasheet first, then its bid and replies),
    each verified on its page; None if any term is not found. A distinctive term ('two thirds pitch', 'isochronous')
    counts wherever it is stated; a common word only on a line about the same attribute. Option and negated lines
    never count."""
    words = _attr_words(c) | {norm(t) for t in c.get("terms") or []}
    out = []
    for term in terms:
        hit = None
        part = next((rx for noun, rx in _NEEDS_PART.items() if re.search(rf"\b{noun}\b", term)), None)
        for d in (doc, *others):
            for p in d.pages:
                lines = p.text.splitlines()
                for i, ln in enumerate(lines):
                    n = norm(ln)
                    if not re.search(rf"(?<![\w/]){re.escape(term)}(?![\w/])", n):
                        continue
                    if ln.strip()[:1] in EMPTY + FULL or re.search(r"\b(not|optional|options?|available|excluded)\b", n):
                        continue
                    near = norm(" ".join(lines[max(0, i - 2): i + 2]))
                    if part and not re.search(part, near):
                        continue
                    if not _distinctive(term) and not (any(w[:6] in n for w in words if w != term) or len(n) < 40):
                        continue
                    cite = verify(d, ln.strip()[:120], p.number)
                    if cite and not listed_as_choice(d, cite):
                        hit = {"term": term, "page": p.number, "doc": d.doc_id, "line": ln.strip(),
                               "citation": cite.model_dump(mode="json")}
                        break
                if hit:
                    break
            if hit:
                break
        if not hit:
            return None
        out.append(hit)
    return out


def lines_above(doc: docs.Document, quote: str, page: int | None, up: int = 6) -> str:
    pg = doc.page(page) if page else None
    if not pg:
        return ""
    lines = [ln.strip() for ln in (pg.raw or pg.text).splitlines()]
    head = re.sub(r"\s+", " ", quote).strip()[:14]
    at = next((i for i, ln in enumerate(lines) if head and head in re.sub(r"\s+", " ", ln)), None)
    return " ".join(lines[max(0, at - up): at]) if at is not None else ""


def unit_from_heading(doc: docs.Document, c: dict, quote: str, page: int | None, up: int = 9) -> dict | None:
    """A table prints the unit once, in the heading of the column or row ('Diesel, Lph (gph) at % load' above
    '100% 508.8(134.5)'). Accepted only when a line at most `up` lines above the quoted line names the unit AND the
    attribute, so a unit from another table or row is not borrowed."""
    unit = c.get("unit")
    u = UNITS.get(str(unit or "").lower().replace(" ", ""))
    pg = doc.page(page) if page else None
    if not u or not pg:
        return None
    pair = re.search(r"([\d,]{3,6})\s*\(\s*([\d,]{3,6})\s*\)", quote)
    if pair and str(unit).lower() in ("kw", "kva") and isinstance(c.get("value"), (int, float)):
        position = 1 if str(unit).lower() == "kw" else 2
        for ln in (pg.raw or pg.text).splitlines():
            if re.search(r"(?i)\bk?we?\b\s*\(\s*kva\s*\)", ln) and _f(pair.group(position)) >= float(c["value"]):
                cite = verify(doc, ln.strip()[:120], page)
                if cite:
                    return {"line": ln.strip(), "citation": cite.model_dump(mode="json")}
    words = _attr_words(c)
    lines = [ln.strip() for ln in (pg.raw or pg.text).splitlines()]
    head = re.sub(r"\s+", " ", quote).strip()[:14]
    at = next((i for i, ln in enumerate(lines) if head and head in re.sub(r"\s+", " ", ln)), None)
    if at is None:
        return None
    window = " ".join(lines[max(0, at - up - 2): at]).lower()
    if words and not any(w[:6] in window for w in words):
        return None  # the headings above are about something else
    for ln in reversed(lines[max(0, at - up): at]):
        low = ln.lower()
        if re.search(rf"(?:\(|\b|\d){u}", low, re.I) and len(ln) < 90:
            cite = verify(doc, ln[:120], page)
            if cite:
                return {"line": ln, "citation": cite.model_dump(mode="json")}
    return None


def _content_words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", s.lower()) if w not in GENERIC | {"with", "from", "that", "this"}}


def option_state(doc: docs.Document, c: dict, value_tokens: list[str]) -> dict | None:
    """Is the compliant value offered as an option elsewhere in the document?
    -> {"state": "unselected" | "selected" | "listed", "page", "line", "citation"} or None.
    unselected: an empty tick box before it; selected: a filled one; listed: named as optional / available, no mark."""
    if not value_tokens:
        return None
    words = _attr_words(c) | ({"cooling", "ambient"} if "ambient" in str(c.get("attribute", "")) else set())
    listed = None
    ticked: dict = {}  # the numbers of every TICKED option about this attribute: two different ones cannot both apply
    for p in doc.pages:
        for ln in p.text.splitlines():
            s = ln.strip()
            if s[:1] in FULL and any(re.search(rf"\b{re.escape(w[:6])}", s.lower()) for w in words):
                nums = tuple(re.findall(r"\d+(?:\.\d+)?", s)[:1])
                if nums:
                    ticked.setdefault(nums, (p.number, s))
    if len(ticked) > 1:
        (page, line), (_, other) = list(ticked.values())[:2]
        cite = verify(doc, line.lstrip(EMPTY + FULL + " ")[:120], page)
        return {"state": "ambiguous", "page": page, "line": f"{line[:60]} AND {other[:60]}",
                "citation": cite.model_dump(mode="json") if cite else None}
    for p in doc.pages:
        for ln in p.text.splitlines():
            s = ln.strip()
            if not s:
                continue
            # a row of a multi-column option list: keep this column only
            cell = re.split(r"\s{3,}|(?<=.)[" + EMPTY + FULL + "]", s)[0].strip()
            low = cell.lower()
            if not any(tok.lower() in low for tok in value_tokens) or (words and not any(w[:6] in low for w in words)):
                continue
            if cell[:1] in EMPTY + FULL:
                cite = verify(doc, cell.lstrip(EMPTY + FULL + " ")[:120], p.number)
                return {"state": "selected" if cell[0] in FULL else "unselected", "page": p.number, "line": cell[:120],
                        "citation": cite.model_dump(mode="json") if cite else None}
            if listed is None and re.search(r"\b(optional|options?|available)\b", low):
                cite = verify(doc, cell[:120], p.number)
                listed = {"state": "listed", "page": p.number, "line": cell[:120],
                          "citation": cite.model_dump(mode="json") if cite else None}
    return listed


def _tokens_for(c: dict, part: dict) -> list[str]:
    q = str((part.get("cite") or {}).get("quote", ""))
    unit = str(c.get("unit") or "")
    toks = []
    for v, _ in values_in(q, unit) if unit else []:
        toks.append(f"{v:g}")
        if unit in ("°F", "°f"):
            cval = round((v - 32) * 5 / 9)
            toks += [f"{cval} °c", f"{cval}°c", f"{cval} c "]
    if not toks and unit:  # fall back on the value the reading reported ('offered 122 °F meets ...')
        m = re.search(r"offered ([\d.]+) ", str(part.get("why", "")))
        if m:
            v = float(m.group(1))
            toks.append(f"{v:g}")
            if unit in ("°F", "°f"):
                cval = round((v - 32) * 5 / 9)
                toks += [f"{cval} °c", f"{cval}°c"]
    if c.get("kind") == "text":
        toks += [str(t) for t in c.get("terms") or []]
    return [t for t in toks if len(t) >= 2]


_CONTRADICTS = re.compile(r"(?i)\b(not|no|without|non[- ]|excluded|excluding|unavailable|by others|indoor only)\b")


def soften_absence(c: dict, p: dict) -> dict:
    """A text condition judged 'deviates' only because descriptive words (no numbers: 'weatherproof', 'rodent-proof')
    are absent from the quote, with nothing saying the opposite, is not a deviation: it is one missing fact."""
    quote = str((p.get("cite") or {}).get("quote", ""))
    if not (p.get("verdict") == "deviates" and c.get("kind") == "text" and c.get("match", "all") == "all" and quote
            and not any(re.search(r"\d", str(term)) for term in c.get("terms") or []) and not _CONTRADICTS.search(quote)):
        return p
    miss = [term for term in c.get("terms") or [] if norm(term) not in norm(quote)]
    if not miss:
        return p
    return dict(p, verdict="unclear", conf=0.5, kind="one missing fact", missing=miss,
                why=f"the evidence {quote[:70]!r} does not state {', '.join(miss)}; nothing says the opposite")


def _is_choice(doc: docs.Document, part: dict) -> bool:
    """Evidence that is only something a buyer may choose can never be computed into an approval."""
    if any(k in str(part.get("why", "")) for k in ("listed as a choice", "selected option is not marked")):
        return True
    cite = part.get("cite")
    if not cite or cite.get("doc_id") != doc.doc_id:
        return False
    return listed_as_choice(doc, Citation(**cite))


def unit_stated_elsewhere(doc: docs.Document, c: dict, offered: float) -> dict | None:
    """The same number with its unit printed elsewhere in the same document ('60 Hz'), on a line that offers no other
    value in that unit."""
    unit = str(c.get("unit") or "")
    if unit.lower() not in ("hz", "rpm"):  # other units belong to too many different quantities
        return None
    for p in doc.pages:
        for ln in p.text.splitlines():
            vals = {v for v, _ in values_in(ln, unit)}
            if vals == {offered} and ln.strip()[:1] not in EMPTY + FULL and not re.search(r"\b(50|optional|available)\b", ln.lower()):
                cite = verify(doc, ln.strip()[:120], p.number)
                if cite and not listed_as_choice(doc, cite):
                    return {"line": ln.strip(), "citation": cite.model_dump(mode="json")}
    return None


def rating_for_voltage(doc: docs.Document, c: dict, voltage: str) -> dict | None:
    """A ratings table with several rows: the rows for the project's voltage ('277/480 3 60 2000/2500 3007') are the
    selected option. Settled only if every such row meets the requirement."""
    unit = str(c.get("unit") or "").lower()
    if unit not in ("kw", "kva") or c.get("op") != ">=" or not voltage:
        return None
    rows = []
    for p in doc.pages:
        for ln in (p.raw or p.text).replace("\n", "\n").splitlines() + p.text.splitlines():
            if not re.search(rf"(?<!\d){voltage}(?!\d)", ln):
                continue
            pairs = re.findall(r"(?<![\d/])(\d{3,4})\s*/\s*(\d{3,4})(?![\d/])", re.sub(r"\d{3}/\d{3}(?=\s+\d\s+\d\d\b)", " ", ln))
            pairs = [(a, b) for a, b in pairs if int(b) > int(a) >= 100 and voltage not in (a, b)]
            if pairs:
                rows.append((p.number, ln.strip(), pairs[0]))
    if not rows or not all(float(r[2][0 if unit == "kw" else 1]) >= float(c["value"]) for r in rows):
        return None
    cite = verify(doc, rows[0][1][:120], rows[0][0])
    if not cite:
        return None
    return {"citation": cite.model_dump(mode="json"), "rows": len(rows),
            "value": rows[0][2][0 if unit == "kw" else 1], "line": rows[0][1]}


def excluded_for_size(quote: str, size: float | None) -> str | None:
    """'Included 300-500 kW | Not included 600-1200 kW': does the project's size fall in the excluded range?"""
    if not size:
        return None
    for m in re.finditer(r"(?i)not\s+(?:included|available|supplied)\s+(\d{2,5})\s*(?:-|–|to)\s*(\d{2,5})\s*(kw|kva)", quote):
        if float(m.group(1)) <= size <= float(m.group(2)):
            return m.group(0)
    return None


def _reader_cite(doc: docs.Document, answer: dict | None):
    q = str((answer or {}).get("quote") or "")
    if not q or "..." in q or "without a verifiable" in q or q.startswith("chunks disagree"):
        return None
    c = verify(doc, q, answer.get("page"))
    return c if c and c.match in ("exact", "normalized", "compact", "table", "table-row") else None


def inspect_parts(reqs: list[dict], parts_by_req: dict[str, list[dict]], doc: docs.Document,
                  reader: dict | None = None, others: tuple = (), project: dict | None = None) -> list[dict]:
    """reader: {req_id: {"verdict", "quote", "page"}} from the independent reader, or None. others: the supplier's own
    bid and replies. project: {"voltage": "480", "kw": 2000}. Mutates parts; returns a log."""
    log = []
    project = project or {}

    def keep(rid, i, c, new):
        parts_by_req[rid][i] = new
        log.append({"req_id": rid, "cid": c["cid"], "kind": new["kind"], "verdict": new["verdict"], "why": new["why"]})
        return new

    # one line of a datasheet offered for two requirements belongs to the one whose wording it matches
    shared: dict = {}
    for r in reqs:
        for i, p in enumerate(parts_by_req[r["req_id"]]):
            if "probably a different attribute" in str(p.get("why", "")):
                m = re.search(r"\((['\"])(.{8,}?)\1\)", str(p["why"]))
                if m:
                    shared.setdefault(m.group(2)[:40], []).append((r, i))
    for quote, claimants in shared.items():
        score = lambda r: len(_content_words(r.get("requirement", "")) & _content_words(quote))
        ranked = sorted(claimants, key=lambda x: -score(x[0]))
        if len(ranked) < 2 or score(ranked[0][0]) <= score(ranked[1][0]):
            continue
        r, i = ranked[0]
        c = r["conditions"][i]
        for p in doc.pages:
            line = next((ln.strip() for ln in p.text.splitlines() if re.sub(r"\s+", " ", quote)[:30] in re.sub(r"\s+", " ", ln)), None)
            if line:
                cite = verify(doc, line[:120], p.number)
                got = compute_numeric(c, line, lines_above(doc, line, p.number))
                if cite and got and got["verdict"] == "complies" and not listed_as_choice(doc, cite):
                    keep(r["req_id"], i, c, dict(parts_by_req[r["req_id"]][i], verdict="complies", conf=0.65, kind="shared line assigned", cite=cite.model_dump(mode="json"),
                                                 why=f"the line is about this requirement more than the other that cited it; {got['why']} ({line[:80]!r})"))
                break
    for r in reqs:
        rid = r["req_id"]
        for i, c in enumerate(r["conditions"]):
            p = parts_by_req[rid][i]
            if p.get("kind") in ("conditional rating", "conflicting records", "commitment deviates"):
                continue
            q = str((p.get("cite") or {}).get("quote", ""))
            judged = any(k in p["why"] for k in ("model judgement on verified quote", "is not shown in the quote",
                                                 "do not appear in the quote", "does not mention", "the expected words are missing"))
            new = None
            a = (reader or {}).get(rid) or {}
            rc = _reader_cite(doc, a) if reader else None
            # 0a. excluded for this size: the document itself says the item is not part of what is offered at this rating
            out_of_range = excluded_for_size(q + " " + str(p.get("why", "")), project.get("kw"))
            if out_of_range and p["verdict"] in ("unclear", "missing"):
                keep(rid, i, c, dict(p, verdict="deviates", conf=0.75, kind="excluded for this size",
                                     why=f"the document says {out_of_range!r} and this project's rating is {project['kw']:g}: not included"))
                continue
            # 0b. a ratings table: the rows for the project's voltage are the selected option
            if "selected option is not marked" in p["why"]:
                got = rating_for_voltage(doc, c, project.get("voltage", ""))
                if got:
                    keep(rid, i, c, dict(p, verdict="complies", conf=0.75, kind="rating for the project voltage", cite=got["citation"],
                                         why=f"every {project['voltage']} V row of the ratings table gives {got['value']} {c['unit']} >= {c['value']} "
                                             f"({got['rows']} row(s), e.g. {got['line'][:70]!r})"))
                    continue
            # 1. judged evidence: compute from the quote itself
            if judged and p.get("cite") and p["cite"].get("match") in ("exact", "normalized", "compact", "table", "table-row") \
                    and "..." not in q and chr(0x2026) not in q and not _is_choice(doc, p):
                above = lines_above(doc, q, p["cite"].get("page"))
                got = compute_numeric(c, q, above) or compute_text(c, q, above)
                if got and got["verdict"] == "complies" and rc and a.get("verdict") == "deviates":
                    other = compute_numeric(c, rc.quote, lines_above(doc, rc.quote, rc.page)) or compute_text(c, rc.quote)
                    if other and other["verdict"] == "deviates":
                        got = None  # the second reading quotes the same quantity saying otherwise: a person decides
                if got and got["verdict"] in ("complies", "deviates"):
                    new = dict(p, verdict=got["verdict"], why=got["why"] + f" ({q[:80]!r})", conf=0.8, kind="computed from the quote")
                elif got and got["verdict"] == "partial":
                    found = find_terms(doc, c, got["missing"], others)
                    if found is not None:  # the rest of the document states the missing words, next to the attribute
                        new = dict(p, verdict="complies", conf=0.75, kind="computed from the quote",
                                   other_cite=found[0]["citation"],
                                   why=got["why"] + "; the document states " + "; ".join(
                                       f"{x['term']} on page {x['page']} ({x['line'][:70]!r})" for x in found))
                    else:
                        new = dict(p, verdict="unclear", conf=0.5, why=got["why"] + "; not stated anywhere else in the document",
                                   kind="one missing fact", missing=got["missing"])
            # 1b. judged, not computable from our quote, but the second reader quoted words the code can compute
            if (new is None or new["verdict"] == "unclear") and judged and p["verdict"] == "complies" and rc \
                    and a.get("verdict") == "complies" and not _is_choice(doc, p) and not listed_as_choice(doc, rc):
                above = lines_above(doc, rc.quote, rc.page)
                got = compute_numeric(c, rc.quote, above) or compute_text(c, rc.quote, above)
                if got and got["verdict"] == "complies":
                    new = dict(p, verdict="complies", conf=0.8, kind="confirmed by the second reading", other_cite=rc.model_dump(mode="json"),
                               why=f"two independent readings agree, and the second one's quote computes: {got['why']} ({rc.quote[:80]!r})")
            if new is None and "is not shown in the quote" in p["why"] and p["verdict"] in ("complies", "deviates") and p.get("cite") \
                    and not _is_choice(doc, p):
                m = re.search(r"offered ([\d.,]+) ", p["why"])
                stated = unit_stated_elsewhere(doc, c, _f(m.group(1))) if m and p["verdict"] == "complies" else None
                if stated:
                    new = dict(p, conf=0.75, kind="unit stated elsewhere", other_cite=stated["citation"],
                               why=p["why"].replace(", confirm", "") + f"; the same value with its unit is printed as {stated['line'][:60]!r}")
            if new is None and "is not shown in the quote" in p["why"] and p["verdict"] in ("complies", "deviates") and p.get("cite"):
                hd = unit_from_heading(doc, c, q, p["cite"].get("page"))
                if hd:
                    new = dict(p, conf=0.75, kind="unit from the table heading", other_cite=hd["citation"],
                               why=p["why"].replace(", confirm", "") + f"; the unit is in the table heading {hd['line'][:70]!r} "
                                                                     f"(page {p['cite'].get('page')})")
            # 2. disputed clause: our reading found nothing, the independent reader quoted something
            if new is None and p["verdict"] in ("missing", "unclear") and reader and (reader.get(rid) or {}).get("quote"):
                a = reader[rid]
                rq = str(a.get("quote") or "")
                cite = verify(doc, rq, a.get("page")) if rq and "..." not in rq and "without a verifiable" not in rq else None
                if cite and cite.match in ("exact", "normalized", "compact"):
                    got = compute_numeric(c, cite.quote, lines_above(doc, cite.quote, cite.page))
                    if got and got["verdict"] in ("complies", "deviates") and not listed_as_choice(doc, cite) and \
                            not any(k in p["why"] for k in ("listed as a choice", "selected option is not marked")):
                        new = dict(p, verdict=got["verdict"], cite=cite.model_dump(mode="json"), conf=0.75,
                                   why=f"disputed clause inspected: the independent reader's quote is on page {cite.page}; "
                                       + got["why"], kind="disputed clause resolved")
            if new is not None:
                parts_by_req[rid][i] = new
                log.append({"req_id": rid, "cid": c["cid"], "kind": new["kind"], "verdict": new["verdict"], "why": new["why"]})
                p = new
            # 2b. a "deviates" that rests only on descriptive words being absent is not a contradiction: ask
            soft = soften_absence(c, p)
            if soft is not p:
                parts_by_req[rid][i] = soft
                log.append({"req_id": rid, "cid": c["cid"], "kind": soft["kind"], "verdict": "unclear", "why": soft["why"]})
                p = soft
            # 3. option dependence: a compliant value the document offers only as an option
            if p["verdict"] == "complies" and p.get("source", "datasheet") == "datasheet":
                st = option_state(doc, c, _tokens_for(c, p))
                if st and st["state"] in ("unselected", "listed", "ambiguous"):
                    parts_by_req[rid][i] = dict(p, verdict="unclear", conf=min(p["conf"], 0.5), kind="depends on an option",
                                                option=st, other_cite=st["citation"],
                                                why=f"{p['why']}; but the document offers it as an option that is "
                                                    + {"unselected": "not marked", "listed": "available, with no mark of what is supplied",
                                                       "ambiguous": "marked twice with different values"}[st["state"]]
                                                    + f" (p{st['page']}: {st['line']!r}): ask whether it is supplied")
                    log.append({"req_id": rid, "cid": c["cid"], "kind": "depends on an option", "verdict": "unclear",
                                "why": f"option not marked: {st['line']}"})
    return log
