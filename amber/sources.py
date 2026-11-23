"""Show a cited source the way a reviewer wants to see it: the page of the original document, with the quoted words
highlighted. Used by the web page, so a person can check any answer against the document in one click.

Only documents under the data folder can be shown, found by their doc_id (the same id the citations carry).
Nothing is written to the documents: highlights are drawn on an in-memory copy of the page.
"""
from __future__ import annotations

import base64
import csv
import re
from pathlib import Path

import pymupdf

from .docs import MIN_TEXT_CHARS, doc_id_for

EXTS = {".pdf", ".txt", ".md", ".eml", ".csv"}


def index(data_root: Path, exclude: set[str] = frozenset()) -> dict[str, Path]:
    """doc_id -> file, for every document under the data folder (minus excluded relative paths)."""
    out: dict[str, Path] = {}
    for p in sorted(data_root.rglob("*")):
        if p.is_file() and p.suffix.lower() in EXTS:
            rel = p.relative_to(data_root).as_posix()
            if rel in exclude:
                continue
            out.setdefault(doc_id_for(p), p)
    return out


def _pieces(quote: str) -> list[str]:
    """Ways to find a quote on a page, most specific first: the whole quote, then its natural segments
    (table cells, lines, sentences), then short word windows (for quotes the PDF splits across columns)."""
    q = re.sub(r"\s+", " ", quote).strip()
    out = [q[:300]] if q else []
    plain = re.sub(r"[‐‑‒–—−]", "-", q)  # typographic hyphens as the PDF prints them
    for v in (plain, re.sub(r"(\w)- (\w)", r"\1\2", plain), re.sub(r"(\w)- (\w)", r"\1-\2", plain)):
        if v != q:
            out.append(v[:300])
    quote = plain
    segs = [s.strip(" .,:;") for s in re.split(r"\s*[|\n•;]\s*|(?<=[.!?])\s+", quote)]
    out += [s for s in segs if len(s) >= 6 and s != q]
    words = q.split()
    if len(words) > 4:
        out += [" ".join(words[i:i + 4]) for i in range(0, len(words) - 3, 2)]
    seen, uniq = set(), []
    for s in out:
        if s.lower() not in seen:
            seen.add(s.lower())
            uniq.append(s)
    return uniq


def find_rects(page: "pymupdf.Page", quote: str) -> list["pymupdf.Rect"]:
    pieces = _pieces(quote)
    if not pieces:
        return []
    hits = page.search_for(pieces[0])
    if hits:
        return hits
    rects: list = []

    def add(hits):
        for r in hits:
            if not any(r.intersects(x) for x in rects):
                rects.append(r)

    for s in pieces[1:]:
        add(page.search_for(s))
    if rects:
        return rects
    # a table quote: label and value sit in separate cells. Mark word pairs, then distinctive single words or
    # numbers, but only where they are rare on the page, so the mark still points at the right place.
    words = [w.strip(".,:;()") for w in re.sub(r"[‐-—−]", "-", quote).split()]
    words = [w for w in words if w]
    for i in range(len(words) - 1):
        add(page.search_for(f"{words[i]} {words[i + 1]}"))
    if rects:
        return rects
    for w in words:
        if len(w) >= 4 or any(ch.isdigit() for ch in w):
            hits = page.search_for(w)
            if 0 < len(hits) <= 3:
                add(hits)
    return rects


def render_pdf(path: Path, page_no: int, quote: str = "", zoom: float = 1.6) -> dict:
    with pymupdf.open(path) as pdf:
        n = pdf.page_count
        page_no = min(max(1, page_no), n)
        page = pdf[page_no - 1]
        scanned = len(page.get_text("text").strip()) < MIN_TEXT_CHARS
        rects = find_rects(page, quote) if quote and not scanned else []
        for r in rects:
            page.add_highlight_annot(r)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), annots=True)
        h = page.rect.height or 1
        top = min((r.y0 for r in rects), default=None)
        return {"kind": "pdf", "pages": n, "page": page_no, "found": len(rects), "scanned": scanned,
                "top": None if top is None else round(top / h, 4),
                "image": "data:image/png;base64," + base64.b64encode(pix.tobytes("png")).decode()}


def _norm_find(text: str, needle: str) -> tuple[int, int] | None:
    """Find needle in text ignoring case and runs of whitespace; returns the span in the original text."""
    idx, chars = [], []
    prev_space = False
    for i, c in enumerate(text):
        if c.isspace():
            if prev_space:
                continue
            c, prev_space = " ", True
        else:
            prev_space = False
        idx.append(i)
        chars.append(c.lower())
    flat = "".join(chars)
    n = re.sub(r"\s+", " ", needle).strip().lower()
    k = flat.find(n) if n else -1
    if k < 0:
        return None
    return idx[k], idx[k + len(n) - 1] + 1


def text_view(path: Path, quote: str = "") -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    spans: list[tuple[int, int]] = []
    for piece in _pieces(quote):
        s = _norm_find(text, piece)
        if s and not any(a < s[1] and s[0] < b for a, b in spans):
            spans.append(s)
            if piece == _pieces(quote)[0]:
                break
    spans.sort()
    segs, pos = [], 0
    for a, b in spans:
        segs += [{"t": text[pos:a], "hl": False}, {"t": text[a:b], "hl": True}]
        pos = b
    segs.append({"t": text[pos:], "hl": False})
    return {"kind": "text", "pages": 1, "page": 1, "found": len(spans), "segments": [s for s in segs if s["t"]]}


def table_view(path: Path, quote: str = "", locator: str = "") -> dict:
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    header, body = (rows[0], rows[1:]) if rows else ([], [])
    key = re.split(r"[\s/(]+", locator.strip())[0] if locator else ""
    q = re.sub(r"\s+", " ", quote).strip().lower()
    hl = [i for i, r in enumerate(body) if (key and r and r[0] == key)
          or (q and any(len(c) > 8 and c.strip().lower() in q for c in r))]
    links = {}
    if "url" in header:
        u = header.index("url")
        links = {i: body[i][u] for i in hl if u < len(body[i]) and body[i][u].startswith("http")}
    return {"kind": "table", "pages": 1, "page": 1, "found": len(hl), "header": header, "rows": body, "hl": hl,
            "links": links}


def show(path: Path, page_no: int = 1, quote: str = "", locator: str = "") -> dict:
    ext = path.suffix.lower()
    if ext == ".pdf":
        out = render_pdf(path, page_no, quote)
    elif ext == ".csv":
        out = table_view(path, quote, locator)
    else:
        out = text_view(path, quote)
    out["name"] = path.name
    return out
