"""link_records: which documents are about the same thing, and how sure are we?

A purchase is spread over many records: the bid names a product, a datasheet describes it, the bid form's scope items
point at spec paragraphs, the equipment schedule gives tags and need dates, the PO log and the lead-time reports cover
the same equipment class. Every link is made in code, with the evidence for it (the line where each record names the
other), and a link that could go two ways is reported as AMBIGUOUS with every candidate, never silently picked.

Product links, strongest first:
  primary   the bid's model designation is the datasheet's own main model (the one its first pages name most)
  exact     the designation appears as a whole word in the datasheet
  alias     another record equates it with a designation that appears (B2's bid: "C2000D6 (model DQKAB)")
  variant   only a longer designation appears (C2000D6 -> C2000D6E): a different model until the supplier says so
One primary or exact candidate -> linked. Otherwise, two or more alias/variant candidates -> ambiguous (ask the
supplier); none -> no datasheet (ask for it). Code only, no model calls.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from . import docs
from .package import model_tokens
from .verify import verify

_LINE_MAX = 160


def _squash(s: str) -> str:
    return re.sub(r"[\s\-]", "", s).lower()


_WORD = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")


def _forms(text: str) -> list[str]:
    """Every designation-like word in the text, hyphens removed, plus each hyphen-separated part."""
    out = []
    for w in _WORD.findall(text):
        lw = w.lower()
        out.append(lw.replace("-", ""))
        if "-" in lw:
            out += lw.split("-")
    return out


def _occurrences(text: str, token: str) -> tuple[int, Counter]:
    """(whole-word hits, longer designations that start with the token and add at most 3 characters)"""
    t = _squash(token)
    forms = _forms(text)
    exact = sum(1 for f in forms if f == t)
    longer = Counter(f for f in forms if f != t and f.startswith(t) and len(f) - len(t) <= 3)
    return exact, longer


def primary_model(doc: docs.Document) -> str | None:
    """The model a datasheet is about: the designation its first two pages name most often (at least twice)."""
    head = " ".join(p.text for p in doc.pages[:2])
    counts = Counter(t.upper() for t in model_tokens(head) if len(t) >= 4)
    best = counts.most_common(1)
    return best[0][0] if best and best[0][1] >= 2 else None


def _cite_line(doc: docs.Document, token: str) -> dict | None:
    sq = _squash(token)
    for pg in doc.pages:
        if sq in _squash(pg.text):
            line = next((ln.strip() for ln in pg.text.splitlines() if sq in _squash(ln)), "")
            c = verify(doc, line[:_LINE_MAX], page=pg.number) if line else None
            if c:
                return c.model_dump(mode="json")
    return None


def aliases(products: dict[str, str]) -> list[dict]:
    """Designations one record equates, e.g. 'Cummins C2000D6 (model DQKAB)' -> C2000D6 = DQKAB."""
    out = []
    for b, prod in products.items():
        m = re.search(r"([A-Za-z0-9-]{4,})\s*\(\s*model\s+([A-Za-z0-9-]{4,})\s*\)", prod or "", re.I)
        if m:
            out.append({"a": m.group(1).upper(), "b": m.group(2).upper(), "source": b, "text": m.group(0)})
    return out


def link_products(products: dict[str, str], library: list[str], product_citations: dict | None = None) -> dict:
    """products: bid -> product text from the bid. library: datasheet paths. -> per bid: status, candidates, evidence."""
    lib = [docs.load(p) for p in library]
    texts = {d.doc_id: " ".join(p.text for p in d.pages) for d in lib}
    prim = {d.doc_id: primary_model(d) for d in lib}
    eq = aliases(products)
    out = {}
    for b, prod in products.items():
        tokens = [t.upper() for t in model_tokens(prod)]
        cands: dict[str, dict] = {}
        for d in lib:
            for t in tokens:
                exact, longer = _occurrences(texts[d.doc_id], t)
                kind = None
                if exact and prim[d.doc_id] and _squash(prim[d.doc_id]) == _squash(t):
                    kind = "primary"
                elif exact:
                    kind = "exact"
                elif longer:
                    kind = "variant"
                for al in eq:
                    other = al["b"] if _squash(al["a"]) == _squash(t) else al["a"] if _squash(al["b"]) == _squash(t) else None
                    if other and kind is None and _occurrences(texts[d.doc_id], other)[0]:
                        kind = "alias"
                        t_used, via = other, al
                        break
                else:
                    t_used, via = t, None
                if kind is None:
                    continue
                rank = {"primary": 0, "exact": 1, "alias": 2, "variant": 3}[kind]
                prev = cands.get(d.doc_id)
                if prev and prev["rank"] <= rank:
                    continue
                shown = t_used if kind != "variant" else longer.most_common(1)[0][0].upper()
                cands[d.doc_id] = {
                    "doc_id": d.doc_id, "file": Path(d.path).name, "kind": kind, "rank": rank, "token": t,
                    "found": shown, "hits": exact if kind in ("primary", "exact") else None,
                    "datasheet_model": prim[d.doc_id], "citation": _cite_line(d, shown),
                    "via": ({"bid": via["source"], "text": via["text"]} if via else None)}
        ranked = sorted(cands.values(), key=lambda c: (c["rank"], -(c["hits"] or 0)))
        strong = [c for c in ranked if c["kind"] in ("primary", "exact")]
        primaries = [c for c in strong if c["kind"] == "primary"]
        if len(primaries) == 1 or len(strong) == 1:
            chosen = primaries[0] if len(primaries) == 1 else strong[0]
            status = "linked"
            why = (f"{chosen['found']} is {'the main model of' if chosen['kind'] == 'primary' else 'named in'} {chosen['file']}"
                   + "".join(f"; {c['file']} {'also mentions it but is about ' + str(c['datasheet_model']) if c['kind'] in ('primary', 'exact') else 'has only ' + c['found'] + ' (a ' + c['kind'] + ', not the same model)'}"
                             for c in ranked if c is not chosen))
        elif not ranked:
            chosen, status, why = None, "none", f"no datasheet in the library names {', '.join(tokens) or prod}: ask the supplier for it"
        else:
            chosen, status = None, "ambiguous"
            why = (f"no datasheet names {', '.join(tokens)} exactly; candidates: "
                   + "; ".join(f"{c['file']} ({c['kind']}: {c['found']}" + (f", per {c['via']['bid']}'s bid '{c['via']['text']}'" if c.get("via") else "") + ")"
                               for c in ranked)
                   + ". Only the supplier can say which model is offered.")
        out[b] = {"product": prod, "tokens": tokens, "status": status, "datasheet": chosen["file"] if chosen else None,
                  "doc_id": chosen["doc_id"] if chosen else None, "candidates": ranked, "why": why,
                  "bid_citation": (product_citations or {}).get(b),
                  "route": "decide" if status == "linked" else "ask_supplier"}
    return out


_REF = re.compile(r"(\d+\.\d+(?:\.[A-Z])?(?:\.\d+)?)")


_GENERIC = {"with", "from", "each", "full", "load", "standby", "hours", "inside", "unit", "type", "rating", "system"}


def _content(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", s.lower()) if w not in _GENERIC}


def link_scope_to_requirements(scope: list[dict], form_text: str, requirements: list[dict]) -> dict:
    """The bid form's 'Spec reference' column points each scope item at a spec paragraph; the requirement checklist
    gives each requirement's paragraph. A link needs the same paragraph (or the same named sub-paragraph) AND shared
    content words. A paragraph number that matches with nothing in common is reported as a conflicting reference."""
    links, conflicts = [], []
    lines = form_text.splitlines()
    for s in scope:
        row = next((ln for ln in lines if re.match(rf"^\s*{re.escape(s['id'])}(?![0-9])", ln)), "")
        refs = [r for r in _REF.findall(row) if r != "2.1"]
        names = [n for n in re.findall(r"\(([^)]+)\)", row) if len(n) > 6]
        for r in requirements:
            loc, anchor = r.get("spec_locator", ""), r.get("spec_anchor", "")
            base = loc.split(" ")[0]
            num = re.match(r"\s*(\d+)\.", anchor)
            full = base + (f".{num.group(1)}" if num and not re.search(r"\.\d+$", base) else "")
            named = [n for n in names if n.lower() in loc.lower()]
            numbered = (not names) and any(x in (base, full) for x in refs)
            if not (named or numbered):
                continue
            shared = _content(s["item"]) & _content(r.get("requirement", "") + " " + loc + " " + anchor)
            rec = {"scope_id": s["id"], "scope_item": s["item"], "req_id": r["req_id"], "spec_locator": loc,
                   "form_line": row.strip()[:140]}
            if shared:
                links.append(dict(rec, why=f"bid form {s['id']} cites {(named[0] if named else full)!r}, which is "
                                           f"{r['req_id']}'s paragraph {loc}; both are about {', '.join(sorted(shared)[:3])}"))
            else:
                conflicts.append(dict(rec, why=f"bid form {s['id']} ({s['item']}) cites paragraph {full or base}, but in "
                                               f"the spec that paragraph is {r['req_id']} ({r.get('requirement', '')[:60]}): "
                                               "the reference is wrong in one of the two documents; not linked"))
    return {"links": links, "conflicts": conflicts}
