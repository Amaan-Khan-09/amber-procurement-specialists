"""Pick the few pages of a long document most likely to answer a question (BM25 + domain glossary).

Keeps model calls small: a 100-page submittal becomes 3-4 relevant pages per requirement group.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from .docs import Document

# General electrical/mechanical vocabulary, so a requirement worded one way finds a datasheet
# worded another way. Domain knowledge only; it says nothing about any particular document.
GLOSSARY = {
    "standby": ["standby", "esp", "emergency", "rating", "ekw", "kwe", "kw", "kva"],
    "prime": ["prime", "prp", "continuous"],
    "voltage": ["voltage", "volts", "480", "277", "480y", "v"],
    "frequency": ["hz", "frequency", "60"],
    "fuel": ["fuel", "consumption", "gph", "l/hr", "gal/hr", "lph", "100%"],
    "tank": ["tank", "subbase", "sub-base", "base", "ul142", "ul2085", "gallons", "runtime", "hours"],
    "emissions": ["epa", "tier", "nsps", "emission", "certified", "stationary"],
    "governor": ["governor", "isochronous", "speed", "electronic", "ecm"],
    "insulation": ["insulation", "class", "h", "f", "rise"],
    "harmonic": ["thd", "harmonic", "distortion", "waveform", "tif"],
    "regulation": ["regulation", "voltage", "±", "steady", "state"],
    "excitation": ["pmg", "permanent", "magnet", "excitation", "exciter", "aref"],
    "motor": ["motor", "starting", "skva", "kva", "dip", "mskva"],
    "cooling": ["radiator", "cooling", "ambient", "°c", "°f", "50°c", "122°f", "unit-mounted"],
    "enclosure": ["enclosure", "weather", "sound", "attenuated", "housing", "silencer", "level"],
    "heater": ["heater", "jacket", "coolant", "block", "watt", "w"],
    "breaker": ["breaker", "circuit", "trip", "lsig", "lsi", "solid-state", "electronic"],
    "battery": ["battery", "batteries", "24", "vdc", "starter", "starting", "charger"],
    "speed": ["rpm", "speed", "1800"],
    "engine": ["engine", "cylinder", "cylinders", "cycle", "turbocharged", "aftercooled", "v12", "v16"],
    "alternator": ["alternator", "generator", "brushless", "pole", "pitch", "4-pole", "2/3"],
}

_TOKEN = re.compile(r"[a-z0-9°±/.%-]+")


def tokens(s: str) -> list[str]:
    s = re.sub(r"\b(\d{3,5})\s*y?\s*/\s*(\d{3,5})\b",  # 480Y/277 == 277/480
               lambda m: "/".join(sorted((m.group(1), m.group(2)), key=int)), s.lower())
    return [t.strip(".-/") for t in _TOKEN.findall(s) if t.strip(".-/")]


def expand(query: str) -> list[str]:
    q = tokens(query)
    out = list(q)
    for key, words in GLOSSARY.items():
        if key in q or any(w in q for w in words[:2]):
            out += words
    return out


def passages(doc: Document, size: int = 900, overlap: int = 250) -> list[tuple[int, str]]:
    """Overlapping windows of each page's text, split on line boundaries: (page, text)."""
    out = []
    for p in doc.pages:
        lines = [re.sub(r"[ \t]{2,}", "  ", l).strip() for l in p.text.splitlines()]
        buf = ""
        for line in (l for l in lines if l):
            if len(buf) + len(line) > size and buf:
                out.append((p.number, buf))
                buf = buf[-overlap:]
            buf += line + "\n"
        if buf.strip():
            out.append((p.number, buf))
    return out


def rank_passages(doc: Document, query: str, k: int = 3, k1: float = 1.4, b: float = 0.75,
                  _cache: dict = {}) -> list[tuple[int, str]]:
    """Best k passages for the query, best first."""
    key = (doc.sha256, id(doc))
    if key not in _cache:
        ps = passages(doc)
        toks = [tokens(t) for _, t in ps]
        df = Counter()
        for t in toks:
            df.update(set(t))
        _cache[key] = (ps, toks, df, sum(len(t) for t in toks) / max(1, len(toks)))
    ps, toks, df, avg = _cache[key]
    n = len(ps)
    q = Counter(expand(query))
    scored = []
    for i, t in enumerate(toks):
        tf = Counter(t)
        s = sum(qw * math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5)) * tf[term] * (k1 + 1)
                / (tf[term] + k1 * (1 - b + b * len(t) / avg)) for term, qw in q.items() if term in tf)
        if s > 0:
            scored.append((s, i))
    scored.sort(reverse=True)
    return [ps[i] for _, i in scored[:k]]


def rank_pages(doc: Document, query: str, k: int = 3, k1: float = 1.4, b: float = 0.75) -> list[int]:
    """Return up to k page numbers, best first. Pages with no text are skipped."""
    pages = [(p.number, tokens(p.text)) for p in doc.pages if p.text.strip()]
    if not pages:
        return []
    n = len(pages)
    avg = sum(len(t) for _, t in pages) / n
    df = Counter()
    for _, t in pages:
        df.update(set(t))
    q = Counter(expand(query))
    scores = []
    for num, t in pages:
        tf = Counter(t)
        s = 0.0
        for term, qw in q.items():
            if term not in tf:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            s += qw * idf * tf[term] * (k1 + 1) / (tf[term] + k1 * (1 - b + b * len(t) / avg))
        scores.append((s, num))
    scores.sort(reverse=True)
    return [num for s, num in scores[:k] if s > 0]
