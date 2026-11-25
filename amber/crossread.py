"""Independent reader: a second model of a different family reads the WHOLE datasheet blind and answers every requirement.

Why a whole-document read: a second model that only sees the pipeline's quoted evidence shares its blind spots (a derating
footnote elsewhere, an option that is not marked as supplied), and agreement with it did not predict a right answer. A
reader that sees the whole datasheet did: on 142 labelled requirements, when it agreed with an answer the pipeline had
handed to a person, that answer was right 84 % of the time (41 of 49); when it did not, 38 % (19 of 50).
So the page shows the reader's verdict next to each answer and puts the contested ones first. It never changes a verdict.

The reader sees the datasheet in page chunks small enough for a free tier's per-minute limit and answers every requirement
for each chunk; the answers are merged with fixed rules (see merge()). A quote it gives must be found on the page it cites,
otherwise its "complies" / "deviates" is downgraded to "unclear".

Stored reviews live in eval/cross_checks/*.json (committed, for the documents we tested) and .cache/cross_read/ (made on
your machine with scripts/cross_read.py).
"""
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Callable

from . import docs
from .llm import LLM, LLMError
from .verify import verify

ROOT = Path(__file__).resolve().parents[1]
STORES = (ROOT / "eval" / "cross_checks", ROOT / ".cache" / "cross_read")
CHUNK_CHARS = 6500
PACE_SECONDS = 50  # a free tier allows about 6-8k tokens a minute
VERDICTS = ["complies", "deviates", "missing", "unclear"]
DEFAULT_MODEL = "qwen/qwen3.8-27b"

SYSTEM = """You are reviewing a supplier's datasheet against specification requirements for a procurement team.
For EACH requirement, decide from the datasheet pages given ONLY (no outside knowledge of the product) which is true:
- "complies": these pages clearly state something that meets the requirement.
- "deviates": these pages clearly state something that does NOT meet it.
- "mentioned": the topic appears (for example a feature listed as an option that is not marked as supplied, a model code, a
  claim without a number) but you cannot tell from these pages whether the requirement is met.
- "absent": these pages say nothing about it.
Rules: a datasheet that offers several options (voltages, alternators, tanks, heaters, breakers) complies only if the
SELECTED option is marked; unmarked options are "mentioned". Check units (kW vs kVA, C vs F, L/h vs gph; 1 gph = 3.785 L/h).
The requirement asks for STANDBY ratings. Do not guess: if you would have to know the product from memory, answer "mentioned"
or "absent".
For "complies" and "deviates" give the page number and an exact quote (under 25 words) copied from the pages.
Reply with JSON only: {"answers": [{"req_id": "R01", "verdict": "complies|deviates|mentioned|absent", "page": 1, "quote": "..."}]}
with one entry for every requirement, in order."""


def chunks(doc: docs.Document) -> list[list[docs.Page]]:
    out, cur, size = [], [], 0
    for p in doc.pages:
        if cur and size + len(p.text) > CHUNK_CHARS:
            out.append(cur)
            cur, size = [], 0
        cur.append(p)
        size += len(p.text)
    return out + ([cur] if cur else [])


def merge(doc: docs.Document, per_req: dict[str, list[dict]]) -> dict[str, dict]:
    """Fixed rules: a verifiable 'complies' or 'deviates' in any chunk stands (both kinds across chunks -> unclear); only
    'mentioned', or a statement without a verifiable quote -> unclear; no chunk mentions it -> missing."""
    merged = {}
    for rid, answers in per_req.items():
        concrete, downgraded = [], False
        for a in answers:
            if a["verdict"] in ("complies", "deviates"):
                c = verify(doc, str(a.get("quote") or ""), a.get("page")) if a.get("quote") else None
                if c:
                    concrete.append((a["verdict"], c.page, a["quote"]))
                else:
                    downgraded = True
        kinds = {v for v, _, _ in concrete}
        if len(kinds) == 1:
            v, page, quote = concrete[0]
        elif len(kinds) > 1:
            v, page, quote = "unclear", None, "chunks disagree: " + "; ".join(f"{k} p{p}" for k, p, _ in concrete)
        elif downgraded or any(a["verdict"] == "mentioned" for a in answers):
            v, page, quote = "unclear", None, "mentioned or stated without a verifiable quote"
        else:
            v, page, quote = "missing", None, ""
        merged[rid] = {"verdict": v, "page": page, "quote": quote}
    return merged


def review(llm: LLM, doc: docs.Document, reqs: list[tuple[str, str]], label: str = "datasheet",
           log: Callable[[str], None] = print) -> dict[str, dict]:
    """Read the whole datasheet blind and answer every (req_id, requirement text). Raises if a chunk cannot be read, so a
    partial review is never stored."""
    per_req: dict[str, list[dict]] = {rid: [] for rid, _ in reqs}
    listing = "\n".join(f"{rid}: {c}" for rid, c in reqs)
    groups, last = chunks(doc), 0.0
    for i, group in enumerate(groups, 1):
        text = "\n\n".join(f"[page {p.number}]\n{p.text.strip()}" for p in group)
        wait = PACE_SECONDS - (time.time() - last)
        if last and wait > 0:
            time.sleep(wait)
        last, reply = time.time(), None
        for attempt in range(3):
            try:
                reply = llm.json(SYSTEM, f"Requirements:\n{listing}\n\nDatasheet pages:\n{text}", max_tokens=3000,
                                 purpose=f"independent reader: {label} chunk {i}")
                break
            except LLMError as e:
                log(f"  chunk {i} attempt {attempt + 1}: {str(e)[:100]}")
                time.sleep(65)
        if reply is None:
            raise LLMError(f"could not read chunk {i} of {label}; no partial review is stored")
        for a in reply.get("answers", []):
            if a.get("req_id") in per_req and a.get("verdict") in ("complies", "deviates", "mentioned", "absent"):
                per_req[a["req_id"]].append(dict(a, chunk=i))
        log(f"  {label}: chunk {i}/{len(groups)} read ({len(group)} pages)")
    return merge(doc, per_req)


def stored_reviews(doc_id: str) -> dict | None:
    """The saved independent review of this datasheet, if any: {"model", "answers": {req_id: {verdict, page, quote}}}."""
    for store in STORES:
        if not store.exists():
            continue
        for f in sorted(store.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            if not isinstance(data, dict):
                continue
            for entry in data.values():
                if isinstance(entry, dict) and entry.get("doc_id") == doc_id and "answers" in entry:
                    return {"model": entry.get("model") or f.stem, "answers": entry["answers"], "file": f.name}
    return None


def annotations(result: dict) -> dict[str, dict]:
    """{finding id: {"verdict", "agrees", "model"}} for every answer of this check (or every bidder's check in a package
    review) that a saved independent review covers. Verdicts are never changed."""
    out: dict[str, dict] = {}

    def one(doc_id: str, findings: list[dict], prefix: str = "") -> None:
        rev = stored_reviews(doc_id)
        if not rev:
            return
        for f in findings:
            rid = (f.get("data") or {}).get("req_id")
            if rid in rev["answers"] and f["id"].startswith(prefix):
                v = rev["answers"][rid]["verdict"]
                out[f["id"]] = {"verdict": v, "agrees": v == f["status"], "model": rev["model"],
                                "page": rev["answers"][rid].get("page"), "quote": rev["answers"][rid].get("quote") or ""}

    R = result.get("result") or {}
    if result.get("tool") == "check_submittal" and R.get("submittal"):
        one(R["submittal"], result.get("findings") or [])
    elif result.get("tool") == "run_package_review":
        for b, s in ((R.get("parts") or {}).get("submittals") or {}).items():
            if (s or {}).get("submittal"):
                one(s["submittal"], result.get("findings") or [], prefix=f"submittal:{b}/")
    return out


def kappa(pairs: list[tuple[str, str]]) -> float:
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[v] * cb[v] for v in VERDICTS) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0
