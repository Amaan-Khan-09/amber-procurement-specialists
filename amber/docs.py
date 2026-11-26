"""Load documents into numbered pages of text, so every claim can cite a page."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from . import layout as layout_reading

MIN_TEXT_CHARS = 40  # below this a page is treated as scanned (image only)
CACHE = Path(__file__).resolve().parents[1] / ".cache" / "ocr"


@dataclass
class Page:
    number: int  # 1-based
    text: str
    ocr: bool = False
    raw: str = ""  # the same text in the PDF's own order, which keeps columns apart (empty for scans and text files)
    layout: str = ""  # layout-aware reading (columns apart, table rows together); only when that reading is on


@dataclass
class Document:
    doc_id: str
    path: str
    pages: list[Page] = field(default_factory=list)
    commitment: bool = False  # a supplier's own bid or reply (read for what it commits to), not a datasheet
    sha256: str = ""

    @property
    def scanned_pages(self) -> list[int]:
        return [p.number for p in self.pages if not p.ocr and len(p.text.strip()) < MIN_TEXT_CHARS]

    def page(self, number: int) -> Page | None:
        return self.pages[number - 1] if 1 <= number <= len(self.pages) else None

    def text(self) -> str:
        return "\n".join(f"[page {p.number}]\n{p.text}" for p in self.pages)


def doc_id_for(path: str | Path) -> str:
    stem = Path(path).stem.lower()
    return re.sub(r"[^a-z0-9]+", "-", stem).strip("-")[:48]


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: str | Path, doc_id: str | None = None, ocr=None) -> Document:
    """Load a PDF, or a .txt/.md/.eml as one page.

    `ocr` is an optional callable(page_png_bytes) -> str used for scanned pages. Results are cached
    on disk by file hash and page number, so a document is only OCR'd once.
    """
    path = Path(path)
    doc = Document(doc_id=doc_id or doc_id_for(path), path=str(path), sha256=_sha(path))
    if path.suffix.lower() in {".txt", ".md", ".eml"}:
        doc.pages = [Page(1, path.read_text(encoding="utf-8", errors="replace"))]
        return doc
    pdf = pymupdf.open(path)
    for i, pg in enumerate(pdf, 1):
        text = pg.get_text("text", sort=True)
        page = Page(i, text, raw=pg.get_text("text"))
        if len(text.strip()) < MIN_TEXT_CHARS and ocr is not None:
            try:
                page.text, page.ocr = _ocr_cached(doc.sha256, i, pg, ocr), True
            except Exception:  # OCR unavailable: the page stays unread and is reported as such
                pass
        doc.pages.append(page)
    if layout_reading.enabled():
        texts = layout_reading.pages(path, doc.sha256, len(doc.pages))
        for page, text in zip(doc.pages, texts or []):
            if not page.ocr and len(page.text.strip()) >= MIN_TEXT_CHARS:
                page.layout = text
    return doc


def _ocr_cached(sha: str, number: int, pg: "pymupdf.Page", ocr) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    tag = getattr(ocr, "cache_tag", "ocr")  # which engine read it, so engines never mix silently
    f = CACHE / f"{sha[:16]}-p{number}-{tag}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))["text"]
    prefer = getattr(ocr, "prefer_cached", None)  # cache-only reader: any engine's earlier reading, never a new call
    if prefer is not None:
        for t in prefer:
            g = CACHE / f"{sha[:16]}-p{number}-{t}.json"
            if g.exists():
                return json.loads(g.read_text(encoding="utf-8"))["text"]
    png = pg.get_pixmap(dpi=200).tobytes("png")
    text = ocr(png) or ""
    f.write_text(json.dumps({"text": text}), encoding="utf-8")
    return text
