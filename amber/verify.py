"""Quote verification: a citation is kept only if its quote is really on the cited page.

Match levels, strictest first:
  exact       whitespace-collapsed quote is a substring of the page
  normalized  same after case folding, unifying quotes/dashes and joining hyphenated line breaks
  compact     same after also removing all spaces (PDF tables often split or merge spaces)
  fuzzy       long quotes only (>= 25 chars): partial match score >= 92; never used for numbers
"""
from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz

from .docs import Document
from .schema import Citation

FUZZY_MIN_LEN = 25
FUZZY_MIN_SCORE = 92

_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "′": "'", "″": '"',
                         "–": "-", "—": "-", "‑": "-", "−": "-", " ": " "})


def collapse(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).translate(_QUOTES)
    s = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", s)  # join "turbo-\ncharged"
    s = collapse(s).lower()
    # a quote copied across a line break often keeps the hyphen and a space: "permanent- magnet"
    return re.sub(r"([a-z])- ([a-z])", r"\1\2", s)


def compact(s: str) -> str:
    return re.sub(r"\s+", "", normalize(s))


def _has_number(s: str) -> bool:
    return bool(re.search(r"\d", s))


_ELLIPSIS = re.compile(r"\s*(?:\.{3,}|\u2026)\s*")


def match_level(quote: str, page_text: str) -> str | None:
    if not quote.strip():
        return None
    if _ELLIPSIS.search(quote):
        # A quote shortened with "..." is accepted only if every piece is really on the page, in the same order.
        segs = [s.strip(" .,;:") for s in _ELLIPSIS.split(quote)]
        segs = [s for s in segs if len(s) >= 3]
        if len(segs) >= 2 or (len(segs) == 1 and len(segs[0]) >= 12):
            norm_page, pos = normalize(page_text), 0
            for sg in segs:
                if not match_level(sg, page_text):
                    return None
                i = norm_page.find(normalize(sg), pos)
                if i >= 0:
                    pos = i + len(normalize(sg))
                elif len(segs) > 1 and normalize(sg) in norm_page and normalize(sg) not in norm_page[pos:]:
                    return None  # the pieces are on the page, but not in this order
            return "segments"
        return None
    if collapse(quote) in collapse(page_text):
        return "exact"
    if normalize(quote) in normalize(page_text):
        return "normalized"
    cq = compact(quote)
    if len(cq) >= 4 and cq in compact(page_text):
        return "compact"
    q = normalize(quote)
    if len(q) >= FUZZY_MIN_LEN and not _has_number(q):
        if fuzz.partial_ratio(q, normalize(page_text)) >= FUZZY_MIN_SCORE:
            return "fuzzy"
    if _in_window(q, normalize(page_text)):
        return "table"
    if _in_window_words(quote, page_text):
        return "table"
    return None


def _in_window_words(quote: str, page: str, window: int = 220, min_words: int = 4) -> bool:
    """Two-column datasheets interleave their columns in extracted text ('Permanent-' / other column / 'Magnet
    Pilot Exciter'). A word-only quote is accepted if at least `min_words` distinct words of 3+ letters all occur
    within one short stretch of the page. Quotes with numbers never use this rule (see _in_window)."""
    if re.search(r"\d", quote):
        return False
    norm = lambda s: re.sub(r"[^a-z]+", " ", unicodedata.normalize("NFKC", s).lower())
    words = sorted({w for w in norm(quote).split() if len(w) >= 3})
    if len(words) < min_words:
        return False
    p = norm(page)
    rare = min(words, key=lambda w: len(re.findall(rf"\b{w}\b", p)) or 10**9)
    for m in re.finditer(rf"\b{rare}\b", p):
        span = p[max(0, m.start() - window):m.end() + window]
        if all(re.search(rf"\b{w}\b", span) for w in words):
            return True
    return False


def _in_window(q: str, page: str, window: int = 260) -> bool:
    """Table rows: every word and number of the quote occurs within one short stretch of the page.

    Numbers must match as whole tokens, so '2500' never matches '25000' and a wrong value fails.
    """
    toks = [t for t in re.findall(r"[a-z0-9][a-z0-9./%°±-]*", q) if len(t) > 1 or t.isdigit()]
    if len(toks) < 2 or not any(re.search(r"\d", t) for t in toks):
        return False
    rare = min(toks, key=lambda t: page.count(t) or 10**9)
    for m in re.finditer(re.escape(rare), page):
        lo, hi = max(0, m.start() - window), m.end() + window
        span = page[lo:hi]
        if all(re.search(r"(?<![a-z0-9.])" + re.escape(t) + r"(?![a-z0-9])", span) for t in toks):
            return True
    return False


def verify(doc: Document, quote: str, page: int | None = None, locator: str = "") -> Citation | None:
    """Return a Citation if `quote` is found in `doc`.

    The cited page is checked first, then its neighbours, then the whole document. If the quote
    sits on a different page than claimed, the citation is corrected to the real page.
    Returns None if the quote is nowhere in the document: the claim must then be dropped.
    """
    quote = quote if isinstance(quote, str) else ""
    try:
        page = int(str(page).strip().lstrip("pP").split()[0]) if page not in (None, "") else None
    except (ValueError, IndexError):
        page = None
    order: list[int] = []
    if page and doc.page(page):
        order += [page, page - 1, page + 1]
    order += [p.number for p in doc.pages]
    seen: set[int] = set()
    for n in order:
        if n in seen or not doc.page(n):
            continue
        seen.add(n)
        pg = doc.page(n)
        level = match_level(quote, pg.text)
        if level:
            return Citation(doc_id=doc.doc_id, page=n, locator=locator, quote=collapse(quote),
                            match=level, ocr=pg.ocr)
    return None


# how much a citation's match level should be trusted (used in confidence scoring)
MATCH_TRUST = {"exact": 1.0, "normalized": 0.97, "compact": 0.93, "table": 0.88, "fuzzy": 0.8, "clause": 0.9, "segments": 0.85}
