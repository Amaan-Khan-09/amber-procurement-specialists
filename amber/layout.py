"""Layout-aware reading of a datasheet: columns kept apart, table rows kept together, tick boxes kept.

The plain page text is sorted by position, so on a two-column datasheet a line holds words from both columns. This
reading comes from PyMuPDF4LLM's layout model (local, no network). It takes a few seconds a page, so it is made only
for short documents and cached by file hash. Off unless AMBER_READING=layout.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
from pathlib import Path

MAX_PAGES = 24  # longer packages keep the passage search over the plain text
CACHE = Path(__file__).resolve().parents[1] / ".cache" / "layout"


def enabled() -> bool:
    return os.getenv("AMBER_READING", "plain").lower() == "layout"


def clean(markdown: str) -> str:
    """Markdown decoration removed; a table row becomes 'cell | cell'. Words, numbers and tick boxes are untouched."""
    out = []
    for line in markdown.replace("<br>", " ").splitlines():
        line = re.sub(r"</?(?:sup|sub|u|b|i)>", "", line).replace("**", "")
        line = re.sub(r"(?<![A-Za-z0-9])_+|_+(?![A-Za-z0-9])", "", line).strip()
        if re.fullmatch(r"[|\s:-]*", line):
            continue  # blank lines and table rulers
        line = re.sub(r"^#+\s*|^-\s+(?=\S)", "", line)
        if line.startswith("|"):
            line = " | ".join(c.strip() for c in line.strip("|").split("|") if c.strip())
        out.append(re.sub(r"[ \t]{2,}", " ", line))
    return "\n".join(out)


def pages(path: str | Path, sha: str, n_pages: int) -> list[str] | None:
    """One text per page, or None when this reading is not available (too long, not a PDF, library failure)."""
    if n_pages > MAX_PAGES or not str(path).lower().endswith(".pdf"):
        return None
    cached = CACHE / f"{sha[:16]}.json"
    try:
        if cached.exists():
            return json.loads(cached.read_text(encoding="utf-8"))["pages"]
        import pymupdf4llm

        with contextlib.redirect_stdout(io.StringIO()):  # the library prints notices; a stdio server must stay silent
            chunks = pymupdf4llm.to_markdown(str(path), page_chunks=True, show_progress=False, use_ocr=False)
        out = [clean(c["text"]) for c in chunks]
        if len(out) != n_pages:
            return None
        CACHE.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps({"pages": out}, ensure_ascii=False), encoding="utf-8")
        return out
    except Exception:  # the plain text is always there; this reading is an improvement, not a requirement
        return None
