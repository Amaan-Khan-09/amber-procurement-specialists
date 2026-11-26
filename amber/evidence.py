"""The clause-by-clause evidence record: which document says what about each requirement, which one controls, and why.

For every requirement of one supplier's package, every piece of evidence is listed with the supplier, bid, equipment
tags, model, option state, document, revision and date, page and quote, what it says, and its role:

  controls     decides the answer          supports     agrees with the controlling evidence
  superseded   an earlier statement the supplier explicitly replaced
  conflicts    disagrees, and nothing says which one applies: the supplier is asked
  silent       the document says nothing usable about this condition

The rules (in code, tested in tests/test_evidence.py):
  1. A supplier's later document replaces an earlier one only when it SAYS so ("in place of", "replaces",
     "supersedes", "revised", "instead of") about the same item. Two of its documents that disagree without that
     stay a conflict, whatever their dates.
  2. A written commitment (bid, reply) controls what a datasheet leaves open or lists as an option.
  3. A commitment to less than the spec is a deviation, whatever the datasheet says.
  4. A datasheet that shows a deviation against a commitment that complies is a conflict.
  5. No proof is never compliance: with nothing usable, the answer stays open.
"""
from __future__ import annotations

import re

from . import docs

SUPERSEDES = re.compile(r"(?i)\b(in place of|in lieu of|instead of|replac(?:es|ing|ed? (?:the|our))|supersed\w*|revised|"
                        r"revision to|correct(?:s|ion)|amend\w*)\b")
_DATE = re.compile(r"(?im)\bDate:\s*(?:\w{3},\s*)?(\d{4}-\d{2}-\d{2}|\d{1,2}\s+\w{3,9}\s+\d{4})")
_REV = re.compile(r"\bRev(?:ision|\.)?\s*([A-Z]\b|\d{1,2}\b)\s*(\(?\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\)?)?")
_MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}


def doc_meta(doc: docs.Document, kind: str = "datasheet") -> dict:
    """Revision and date as the document prints them (empty when it prints none: never guessed)."""
    text = "\n".join(p.text for p in doc.pages)
    date = ""
    m = _DATE.search(text)
    if m:
        s = m.group(1)
        if re.match(r"\d{4}-", s):
            date = s
        else:
            d, mon, y = s.split()
            date = f"{y}-{_MONTHS.get(mon[:3].lower(), 0):02d}-{int(d):02d}"
    r = _REV.search(text)
    rev = (f"Rev {r.group(1)}" + (f" {r.group(2)}" if r and r.group(2) else "")) if r else ""
    return {"doc_id": doc.doc_id, "kind": kind, "date": date, "revision": rev}


def says_supersedes(doc: docs.Document, part: dict) -> str | None:
    """Does the sentence this evidence sits in say it replaces something earlier? -> the sentence, or None."""
    cite = part.get("cite") or {}
    pg = doc.page(cite.get("page") or 1)
    if not pg or not cite.get("quote"):
        return None
    q = re.sub(r"\s+", " ", cite["quote"]).strip()[:30]
    # sentences / numbered items, not whole pages: 'replaces' elsewhere in the document says nothing about this item
    for chunk in re.split(r"(?:\n\s*(?=\d+\.\s))|(?<=[.;])\s*\n|\n\s*\n", pg.text):
        flat = re.sub(r"\s+", " ", chunk)
        if q and q in flat and SUPERSEDES.search(flat):
            return flat.strip()[:220]
    return None


def resolve_commitments(commits: list[dict], documents: list[docs.Document], metas: list[dict], auto: float = 0.7) -> dict:
    """commits: one condition decided on each of the supplier's documents. -> {"effective": [parts still in force],
    "superseded": [(part, by, sentence)], "conflict": (a, b) or None}. Only firm statements (verified, above the
    hand-off line) can supersede or conflict; weaker mentions are kept as they are."""
    # a bid always comes before the replies to it (a document may print no date); replies are ordered by their date
    order = sorted(range(len(commits)), key=lambda i: (metas[i].get("kind") == "reply", metas[i].get("date") or "", i))
    firm = [i for i in order if commits[i].get("cite") and commits[i]["conf"] >= auto and commits[i]["verdict"] in ("complies", "deviates")]
    superseded, standing = [], []
    for i in firm:
        p = commits[i]
        clash = [j for j in standing if commits[j]["verdict"] != p["verdict"]]
        if clash:
            sentence = says_supersedes(documents[i], p)
            if sentence:
                for j in clash:
                    superseded.append((j, i, sentence))
                    standing.remove(j)
        standing.append(i)
    verdicts = {commits[j]["verdict"] for j in standing}
    conflict = None
    if len(verdicts) > 1:
        a = next(j for j in standing if commits[j]["verdict"] == "complies")
        b = next(j for j in standing if commits[j]["verdict"] == "deviates")
        conflict = (a, b)
    gone = {j for j, _, _ in superseded}
    return {"effective": [i for i in range(len(commits)) if i not in gone], "superseded": superseded, "conflict": conflict}


def record_for(req: dict, cond: dict, datasheet_part: dict, commits: list[dict], resolved: dict, final: dict,
               metas: list[dict], ds_meta: dict, context: dict) -> list[dict]:
    """The evidence rows for one condition. context: supplier, bid, tags, model."""
    gone = {j: (by, s) for j, by, s in resolved["superseded"]}
    conflict = set(resolved["conflict"] or ())
    final_quotes = {(final.get(k) or {}).get("quote") for k in ("cite", "other_cite", "third_cite") if final.get(k)}
    rows = []
    for idx, (part, meta) in enumerate([(datasheet_part, ds_meta)] + list(zip(commits, metas))):
        cite = part.get("cite") or {}
        silent = not cite
        j = idx - 1
        if silent:
            role, why = "silent", "says nothing usable about this"
        elif j in gone:
            by, sentence = gone[j]
            role, why = "superseded", f"replaced by {metas[by]['doc_id']}: {sentence!r}"
        elif j in conflict or (final.get("kind") == "conflicting records" and part["verdict"] != "unclear"):
            role, why = "conflicts", "disagrees with another document and nothing says which applies"
        elif cite.get("quote") in final_quotes and part["verdict"] == final["verdict"]:
            cross = final.get("kind") in ("conditional rating", "depends on an option", "one missing fact", "conflicting records")
            role, why = "controls", (final if cross else part).get("why", "")[:200]
        elif part["verdict"] == final["verdict"]:
            role, why = "supports", "agrees with the controlling evidence"
        elif final.get("kind") in ("depends on an option", "conditional rating", "one missing fact"):
            role, why = "controls" if cite.get("quote") in final_quotes else "supports", final.get("why", "")[:200]
        else:
            role, why = "supports", f"says {part['verdict']}, not firm enough to decide: {part.get('why', '')[:120]}"
        rows.append({"req_id": req["req_id"], "cid": cond["cid"], "attribute": cond.get("attribute"), **context,
                     "document": meta["doc_id"], "document_kind": meta["kind"], "revision": meta.get("revision", ""),
                     "date": meta.get("date", ""), "page": cite.get("page"), "quote": cite.get("quote", ""),
                     "says": "silent" if silent else part["verdict"], "role": role, "why": why})
    if final.get("option"):
        o = final["option"]
        rows.append({"req_id": req["req_id"], "cid": cond["cid"], "attribute": cond.get("attribute"), **context,
                     "document": ds_meta["doc_id"], "document_kind": "option list", "revision": ds_meta.get("revision", ""),
                     "date": ds_meta.get("date", ""), "page": o["page"], "quote": o["line"], "says": f"option {o['state']}",
                     "role": "controls", "why": "the value is only offered as an option that is not marked as supplied"})
    return rows
