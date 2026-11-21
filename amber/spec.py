"""Split a CSI-format specification (PART 1/2/3, 2.1, A., 1., a., 1)) into numbered clauses.

Works on any spec PDF, not just ours: repeated page headers/footers are found statistically and
removed, and outline markers are recognised whether they sit on their own line or inline.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from .docs import Document

# outline levels, outermost first
LEVELS = [
    ("part", re.compile(r"^PART\s+(\d)\b")),
    ("article", re.compile(r"^(\d\.\d{1,2})\s+(?=[A-Z])")),
    ("upper", re.compile(r"^([A-Z])\.\s")),
    ("num", re.compile(r"^(\d{1,2})\.\s")),
    ("lower", re.compile(r"^([a-z])\.\s")),
    ("paren", re.compile(r"^(\d{1,2})\)\s")),
]


@dataclass
class Clause:
    locator: str  # e.g. "2.1.C.1"
    title: str  # e.g. "System Capacity" (text before the first colon, if short)
    text: str
    page: int
    part: int | None

    def cite_label(self) -> str:
        return f"{self.locator} ({self.title})" if self.title else self.locator


def _boilerplate(doc: Document) -> set[str]:
    """Lines that repeat on at least half the pages (headers, footers), with digits masked."""
    if len(doc.pages) < 3:
        return set()
    seen = Counter()
    for p in doc.pages:
        for line in {re.sub(r"\d+", "#", l.strip()) for l in p.text.splitlines() if l.strip()}:
            seen[line] += 1
    return {l for l, n in seen.items() if n >= max(3, len(doc.pages) // 2)}


def _lines(doc: Document):
    skip = _boilerplate(doc)
    for p in doc.pages:
        pending = ""
        for raw in p.text.splitlines():
            line = raw.strip()
            if not line or re.sub(r"\d+", "#", line) in skip:
                continue
            # a marker alone on its line ("A.") belongs to the next line
            if re.fullmatch(r"(?:PART\s+\d|\d\.\d{1,2}|[A-Z]\.|\d{1,2}\.|[a-z]\.|\d{1,2}\))", line):
                pending = line + " "
                continue
            yield p.number, pending + line
            pending = ""


def _marker(line: str):
    for depth, (name, rx) in enumerate(LEVELS):
        m = rx.match(line)
        if m:
            return depth, m.group(1)
    return None


def _ordinal(key: str) -> int:
    return int(key) if key.isdigit() else ord(key.lower()) - ord("a") + 1


def _plausible(depth: int, key: str, path: dict[int, str]) -> bool:
    """A list marker must start a list (1, A, a) or continue it (next item, or one skipped where an
    option was deleted). Stops "Division\\n22. Engine..." from becoming a clause numbered 22."""
    if depth < 2:
        return True
    n = _ordinal(key)
    if n == 1:
        return True
    prev = path.get(depth)
    return prev is not None and 1 <= n - _ordinal(prev) <= 2


def parse(doc: Document) -> list[Clause]:
    clauses: list[Clause] = []
    path: dict[int, str] = {}
    part: int | None = None
    cur: dict | None = None

    def close():
        if cur and cur["text"].strip():
            text = re.sub(r"\s+", " ", cur["text"]).strip()
            m = re.match(r"^\S+\s+([^:.]{2,60}):", text)
            clauses.append(Clause(cur["loc"], m.group(1).strip() if m else "", text, cur["page"], cur["part"]))

    for page, line in _lines(doc):
        mk = _marker(line)
        if mk and not _plausible(mk[0], mk[1], path):
            mk = None
        if mk:
            depth, key = mk
            if depth == 0:
                part = int(key)
            # a deeper marker can't appear before its parent level exists, except articles
            path[depth] = key
            for d in list(path):
                if d > depth:
                    del path[d]
            close()
            loc = ".".join(path[d] for d in sorted(path) if d >= 1) or f"PART {part}"
            cur = {"loc": loc, "text": line, "page": page, "part": part}
        elif cur is not None:
            cur["text"] += " " + line
    close()
    return clauses


def products(clauses: list[Clause]) -> list[Clause]:
    """PART 2 clauses: the ones a submittal is checked against."""
    return [c for c in clauses if c.part == 2]
