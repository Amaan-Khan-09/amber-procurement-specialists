"""Deterministic requirement checks. The model extracts values; this module decides.

A requirement is {"kind", "op", "value"/"min"/"max"/"options", "unit", "keywords"}; an offer is
{"values": [...], "unit", "selected": bool | None}. Units are converted with pint, so
"145 gph" vs "528 L/hr" or "122 °F" vs "50 °C" are compared correctly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import pint

from .schema import Verdict

U = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)
U.define("volt_ampere_reactive = volt * ampere = var = VAR")
U.define("gph = gallon / hour")
U.define("lph = liter / hour")

UNIT_ALIASES = {
    "kw": "kilowatt", "kwe": "kilowatt", "ekw": "kilowatt", "kwm": "kilowatt", "mw": "megawatt", "w": "watt",
    "kva": "kilovolt_ampere", "mva": "megavolt_ampere", "va": "volt_ampere", "skva": "kilovolt_ampere",
    "v": "volt", "vac": "volt", "vdc": "volt", "kv": "kilovolt", "a": "ampere", "amps": "ampere", "amp": "ampere",
    "ka": "kiloampere", "hz": "hertz", "rpm": "revolution / minute", "gph": "gph", "gal/hr": "gph",
    "gal/h": "gph", "l/hr": "lph", "l/h": "lph", "lph": "lph", "gal": "gallon", "gallons": "gallon",
    "l": "liter", "liters": "liter", "litres": "liter", "°f": "degF", "f": "degF", "degf": "degF",
    "°c": "degC", "c": "degC", "degc": "degC", "ft": "foot", "feet": "foot", "'": "foot", "m": "meter",
    "hp": "horsepower", "psi": "psi", "h": "hour", "hr": "hour", "hrs": "hour", "hours": "hour",
    "min": "minute", "s": "second", "sec": "second", "db": "dimensionless", "dba": "dimensionless",
    "%": "percent", "percent": "percent", "lb": "pound", "lbs": "pound", "kg": "kilogram",
    "in": "inch", "mm": "millimeter", "weeks": "week", "week": "week", "wk": "week", "days": "day",
}


def unit(u: str | None):
    if not u:
        return U.dimensionless
    key = u.strip().lower().replace(" ", "")
    return U(UNIT_ALIASES.get(key, u.strip()))


def qty(value, u: str | None):
    if isinstance(value, str):
        m = re.search(r"-?\d[\d,]*\.?\d*", value)
        if not m:
            raise ValueError(f"no number in {value!r}")
        value = float(m.group(0).replace(",", ""))
    return U.Quantity(float(value), unit(u))


@dataclass
class Decision:
    verdict: Verdict
    why: str
    exact: bool  # decided by a numeric/keyword rule (True) or left to judgement (False)


def _num_ok(req: dict, q) -> bool:
    op = req.get("op", ">=")
    ru = req.get("unit")
    if op == "between":
        return qty(req["min"], ru) <= q <= qty(req["max"], ru)
    target = qty(req["value"], ru)
    # compare in the requirement's units with a small tolerance, so 50 °C meets ">= 122 °F"
    a, t = q.to(target.units).magnitude, target.magnitude
    tol = max(1e-9, abs(t) * 0.001)
    if op == ">=":
        return a >= t - tol
    if op == "<=":
        return a <= t + tol
    if op == ">":
        return a > t + tol
    if op == "<":
        return a < t - tol
    if op == "==":
        return abs(a - t) <= max(tol, abs(t) * 0.005)
    raise ValueError(f"unknown op {op}")


def _squash(s: str) -> str:
    """Lowercase and drop spaces, hyphens and dots, so '12-V' ~ '12 v' and 'solid-state' ~ 'solid state'."""
    s = s.lower().translate(str.maketrans({"‑": "-", "–": "-", "—": "-"}))
    # voltage notation: 480Y/277, 480/277 and 277/480 V all name the same system
    s = re.sub(r"\b(\d{3,5})\s*y?\s*/\s*(\d{3,5})\b",
               lambda m: "/".join(sorted((m.group(1), m.group(2)), key=int)), s)
    return re.sub(r"[\s\-_.]+", "", s)


def _squash_keep_words(s: str) -> str:
    """Lowercase with hyphens as word breaks and voltage notation unified, but words kept apart."""
    s = s.lower().translate(str.maketrans({"‑": " ", "–": " ", "—": " ", "-": " "}))
    return re.sub(r"\b(\d{3,5})\s*y?\s*/\s*(\d{3,5})\b",
                  lambda m: "".join(sorted((m.group(1), m.group(2)), key=int)), s)


def terms_of(req: dict) -> tuple[list[str], str]:
    if req.get("terms"):
        return list(req["terms"]), req.get("match", "all")
    if req.get("options"):
        return list(req["options"]), "any"
    return list(req.get("keywords") or []), "all"


def _text_ok(req: dict, offered: str) -> bool:
    terms, how = terms_of(req)
    if not terms:
        return False
    o = _squash(offered)
    hits = [_squash(t) in o for t in terms]
    return any(hits) if how == "any" else all(hits)


def decide(req: dict, offer: dict | None, evidence: str = "") -> Decision:
    """Decide one requirement against what the submittal offers.

    `evidence` is the verified submittal quote; text requirements are matched against the offered
    values plus that quote (a single offered value), since datasheets often state a feature in the
    sentence around the value.
    """
    if not offer or not offer.get("values"):
        return Decision(Verdict.missing, "not stated in the submittal", True)
    values = [v for v in offer["values"] if v not in (None, "")]
    if not values:
        return Decision(Verdict.missing, "not stated in the submittal", True)
    kind = req.get("kind", "numeric")
    if kind != "numeric":
        terms, how = terms_of(req)
        if how == "all" or len(values) == 1:
            # several features of one product, not alternatives: judge them together with the quote
            values = ["; ".join(str(v) for v in values) + (f" {evidence}" if evidence else "")]
    else:
        values, err = _single_numbers(values, offer.get("unit") or req.get("unit"))
        if err:
            return Decision(Verdict.unclear, err, False)
    if kind == "numeric":
        fr, fo = _family(req.get("unit")), _family(offer.get("unit") or req.get("unit"))
        if fr and fo and fr != fo:
            return Decision(Verdict.unclear, f"submittal states {offer.get('unit')}, requirement is in "
                                             f"{req.get('unit')}; real (kW) and apparent (kVA) power differ", False)
    try:
        if kind == "numeric":
            results = [_num_ok(req, qty(v, offer.get("unit") or req.get("unit"))) for v in values]
            shown = ", ".join(f"{v} {offer.get('unit') or ''}".strip() for v in values)
        else:
            results = [_text_ok(req, str(v)) for v in values]
            shown = "; ".join(str(v) for v in values)
    except (pint.errors.DimensionalityError, pint.errors.UndefinedUnitError, ValueError) as e:
        return Decision(Verdict.unclear, f"could not compare units: {e}", False)

    need = _describe(req)
    if len(values) > 1 and offer.get("selected") is not True:
        if all(results):
            return Decision(Verdict.complies, f"all offered options ({shown}) meet {need}", True)
        if not any(results):
            return Decision(Verdict.deviates, f"no offered option ({shown}) meets {need}", True)
        return Decision(Verdict.unclear, f"options {shown} offered, only some meet {need}; "
                                         "the selected option is not marked", True)
    ok = results[0] if len(values) == 1 else all(results)
    if ok:
        return Decision(Verdict.complies, f"offered {shown} meets {need}", True)
    return Decision(Verdict.deviates, f"offered {shown} does not meet {need}", True)


_NUM = re.compile(r"-?\d[\d,]*\.?\d*")


def _single_numbers(values: list, u: str | None) -> tuple[list, str | None]:
    """Each value must be one number. '528.3 (139.6)' is ambiguous unless the unit marks one of them."""
    out = []
    for v in values:
        if not isinstance(v, str):
            out.append(v)
            continue
        nums = _NUM.findall(v)
        if len(nums) <= 1:
            out.append(v)
            continue
        if u:  # a number written right before the unit wins: "139.6 gph"
            m = re.search(r"(-?\d[\d,]*\.?\d*)\s*\(?\s*" + re.escape(u.strip()), v, re.I)
            if m:
                out.append(m.group(1))
                continue
        return [], f"value {v!r} holds several numbers and none is marked as {u}; not guessing"
    return out, None


UNIT_WORDS = {"kva": ["kva"], "kw": ["kw", "kwe", "ekw"], "w": ["watt", " w", "w "], "v": ["v", "volt"], "a": ["amp", " a "],
              "hz": ["hz"], "rpm": ["rpm"], "gph": ["gph", "gal/hr", "gal./hr", "gal/h"], "l/hr": ["l/hr", "lph", "l/h"],
              "°f": ["°f", "deg f", "degf", "(f)", "f)"], "°c": ["°c", "deg c", "degc", "(c)"], "%": ["%", "percent"],
              "h": ["hour", "hr", " h"], "hp": ["hp", "horsepower"], "ft": ["ft", "feet", "'"], "psi": ["psi"],
              "ka": ["ka"], "db": ["db"], "gal": ["gal"], "l": ["liter", "litre", " l"]}


def unit_in_text(unit: str | None, text: str) -> bool:
    """Is the unit (or a common spelling of it) written in `text`? Dimensionless / unknown units pass."""
    if not unit:
        return True
    key = unit.strip().lower()
    words = UNIT_WORDS.get(key)
    if words is None:
        return True
    t = " " + re.sub(r"\s+", " ", text.lower()) + " "
    return any(w in t for w in words)


def numbers_in(text: str) -> list[float]:
    out = []
    for m in re.finditer(r"-?\d[\d,]*\.?\d*", text):
        try:
            out.append(float(m.group(0).replace(",", "").rstrip(".")))
        except ValueError:
            pass
    return out


def values_in_quote(values: list, quote: str) -> list:
    """Reported numeric values that do NOT occur as numbers in the quote (a real quote can still not
    support the claim: 'Ambient design, F 104' does not support a reported 122)."""
    have = numbers_in(quote)
    bad = []
    for v in values:
        nums = numbers_in(str(v))
        if nums and not any(abs(nums[0] - h) <= 1e-9 + abs(h) * 1e-6 for h in have):
            bad.append(v)
    return bad


def _family(u: str | None) -> str | None:
    """pint gives kW and kVA the same dimension; procurement must not. Returns 'W', 'VA' or None."""
    if not u:
        return None
    k = u.strip().lower().replace(" ", "")
    if k in {"kva", "mva", "va", "skva"}:
        return "VA"
    if k in {"kw", "kwe", "ekw", "kwm", "mw", "w"}:
        return "W"
    return None


def _describe(req: dict) -> str:
    if req.get("kind", "numeric") == "numeric":
        if req.get("op") == "between":
            return f"{req['min']}–{req['max']} {req.get('unit') or ''}".strip()
        return f"{req.get('op', '>=')} {req.get('value')} {req.get('unit') or ''}".strip()
    terms, how = terms_of(req)
    return ("one of: " if how == "any" else "all of: ") + ", ".join(terms)
