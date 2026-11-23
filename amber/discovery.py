"""find_products: which products could meet the spec for this piece of equipment?

Product discovery without invention. Candidates come only from datasheets we actually hold (the library folder),
never from the model's memory, so every product named exists in a document a person can open. Each candidate is
screened on the few ratings a buyer checks first (for a generator: standby rating, voltage and frequency, emissions
tier, engine speed, cooling at site ambient), using the same verified check as check_submittal: every rating cites the
spec paragraph and the datasheet page with exact quotes.

A screen is not an approval: a product that passes is a candidate for a full submittal check, so every suggestion is
handed to a person. Screens are cached per (datasheet, spec, tag), so re-asking costs nothing.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from . import __version__, docs
from .llm import LLM
from .schema import Citation, Finding, RunInfo, ToolResult, Verdict
from .submittal import check_submittal, load_schedule

CACHE = Path(__file__).resolve().parents[1] / ".cache" / "discovery"

# The ratings a buyer screens on first, per spec section (ids from the requirement checklists).
SCREEN = {
    "26 32 13": ["R01", "R02", "R09", "R10", "R12"],  # rating, voltage/Hz, cooling at 122 F, EPA Tier 2, rpm
    "26 33 53": ["U01", "U02", "U03", "U04", "U13"],  # rating, rating at 40 C, voltage/Hz, double conversion, UL 1778
}
# Words that show a datasheet is the right kind of equipment (checked in code on its first pages).
CLASS_WORDS = {
    "26 32 13": ("generator set", "genset", "gen-set", "generator sets", "diesel generator"),
    "26 33 53": (" ups ", "ups ", "uninterruptible", "double conversion", "double-conversion"),
}
SCREEN_CAP = 0.65  # a screen on a few ratings never stands as an approval


def _kind(doc: docs.Document, section: str) -> bool:
    """The right kind of equipment: its own words outnumber every other class's on the first pages (a UPS brochure
    that mentions generator sets is still a UPS brochure)."""
    head = " ".join(p.text for p in doc.pages[:4]).lower()
    hits = {sec: sum(head.count(w) for w in ws) for sec, ws in CLASS_WORDS.items()}
    return hits[section] > 0 and all(hits[section] > n for sec, n in hits.items() if sec != section)


def _cache_file(sub: docs.Document, spec: docs.Document, tag: str, screen: list[str], provider: str) -> Path:
    key = json.dumps([sub.sha256, spec.sha256, tag, screen, provider, __version__])
    return CACHE / (hashlib.sha256(key.encode()).hexdigest()[:20] + ".json")


def find_products(spec_path: str, tag: str, schedule_path: str, library: list[str],
                  checklist: list[dict] | None = None, llm: LLM | None = None) -> ToolResult:
    t0 = time.time()
    llm = llm or LLM()
    row = load_schedule(schedule_path, tag)
    section = row.get("spec_section", "")
    screen = SCREEN.get(section)
    if not screen or not checklist:
        raise ValueError(f"no screening ratings defined for spec section {section!r} (tag {tag})")
    spec_doc = docs.load(spec_path)

    findings: list[Finding] = []
    skipped, ranked = [], []
    for path in library:
        sub = docs.load(path)
        if sum(len(p.text.strip()) for p in sub.pages[:4]) < docs.MIN_TEXT_CHARS:
            skipped.append({"product": sub.doc_id, "reason": "first pages are scanned images; not screened"})
            continue
        if not _kind(sub, section):
            skipped.append({"product": sub.doc_id, "reason": f"not a {row.get('item', 'matching')} datasheet"})
            continue
        cf = _cache_file(sub, spec_doc, tag, screen, llm.provider)
        if cf.exists():
            res, cached = json.loads(cf.read_text(encoding="utf-8")), True
        else:
            res, cached = check_submittal(spec_path, path, tag, schedule_path, checklist=checklist, llm=llm,
                                          only=screen).model_dump(mode="json"), False
            if not any(s.get("ok") is False for s in res["run"].get("steps", [])):  # cache only a clean screen
                CACHE.mkdir(parents=True, exist_ok=True)
                cf.write_text(json.dumps(res), encoding="utf-8")
        per = [{"req_id": f["data"]["req_id"], "requirement": f["claim"], "status": f["status"],
                "confidence": f["confidence"], "why": f["why"]} for f in res["findings"]]
        n = {v.value: sum(1 for p in per if p["status"] == v.value) for v in Verdict}
        if n["deviates"]:
            status, verdict = Verdict.deviates, "does not fit"
        elif n["complies"] == len(screen):
            status, verdict = Verdict.complies, "likely fits"
        else:
            status, verdict = Verdict.unclear, "needs a closer look"
        sub_cites = [c for f in res["findings"] for c in f["citations"]
                     if c["doc_id"] == sub.doc_id][:8]
        conf = min([p["confidence"] for p in per] + [SCREEN_CAP])
        failed = [p["req_id"] for p in per if p["status"] == "deviates"]
        open_ = [p["req_id"] for p in per if p["status"] in ("unclear", "missing")]
        why = (f"screened on {len(screen)} key ratings: {n['complies']} met"
               + (f", does not meet {', '.join(failed)}" if failed else "")
               + (f", not shown or unclear: {', '.join(open_)}" if open_ else "")
               + ("; a screen, not an approval: run check_submittal for the full spec" if status == Verdict.complies else ""))
        ranked.append((0 if status == Verdict.complies else 1 if status == Verdict.unclear else 2, -n["complies"], sub.doc_id))
        findings.append(Finding(
            id=f"F-{sub.doc_id}", claim=f"{sub.doc_id}: {verdict} for {tag} ({row.get('item', '')})", status=status,
            confidence=round(conf, 3), citations=[Citation(**c) for c in sub_cites], needs_human=True, why=why,
            data={"product": sub.doc_id, "file": Path(path).name, "verdict": verdict, "screen": per,
                  "cached": cached, "spec_citations": [c for f in res["findings"] for c in f["citations"]
                                                       if c["doc_id"] == spec_doc.doc_id][:len(screen)]}))
    order = {doc: i for i, (_, _, doc) in enumerate(sorted(ranked))}
    findings.sort(key=lambda f: order.get(f.data["product"], 99))
    result = {"tag": tag, "item": row.get("item"), "spec": spec_doc.doc_id, "screen": screen,
              "candidates": [{"product": f.data["product"], "verdict": f.data["verdict"]} for f in findings],
              "skipped": skipped,
              "note": "Candidates come only from datasheets in the library; nothing is suggested from model memory."}
    res = ToolResult(tool="find_products", findings=findings, result=result,
                     run=RunInfo(models=llm.meter.models(), latency_ms=int((time.time() - t0) * 1000),
                                 steps=list(llm.meter.steps)))
    return res.finalize()
