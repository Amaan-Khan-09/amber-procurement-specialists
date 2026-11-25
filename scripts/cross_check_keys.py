"""Blind cross-check of the answer keys by a model of a different family.

A reviewer who never saw our labels or our pipeline labels each requirement from the datasheet alone, using the same four
verdicts as eval/answer_keys/README.md (the reading itself lives in amber/crossread.py). We then compare. Disagreements are
not "errors" of either side: they are the cells a human should look at first (eval/cross_checks/REVIEW.md, built by
scripts/build_review_packet.py). Nothing here changes a label.

usage: python scripts/cross_check_keys.py [--model qwen/qwen3.8-27b] [--cases G2,G4,...] [--max-pages 20]
Datasheets with scanned pages, or more pages than --max-pages (a free tier reads about a chunk a minute), are skipped.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from amber import crossread, docs  # noqa: E402
from amber.llm import LLM, Meter  # noqa: E402
from amber.ocr import reader_from_env  # noqa: E402

KEYS, EXAMPLES, OUT = ROOT / "eval" / "answer_keys", ROOT / "examples", ROOT / "eval" / "cross_checks"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=crossread.DEFAULT_MODEL)
    ap.add_argument("--cases", default="G2,G4,G5,G6,G7,G8,U1")
    ap.add_argument("--max-pages", type=int, default=20)
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    store = OUT / f"{a.model.split('/')[-1]}.json"
    results = json.loads(store.read_text(encoding="utf-8")) if store.exists() else {}
    llm = LLM(provider="groq", model=a.model)
    for cid in a.cases.split(","):
        if cid in results:
            print(f"{cid}: already reviewed, skipped")
            continue
        case = json.loads((KEYS / f"{cid}.json").read_text(encoding="utf-8"))
        run = json.loads((EXAMPLES / f"{cid}.json").read_text(encoding="utf-8"))
        claims = {f["data"]["req_id"]: f["claim"] for f in run["findings"] if "req_id" in (f.get("data") or {})}
        doc = docs.load(ROOT / case["submittal"], ocr=reader_from_env(meter=Meter()))
        if len(doc.pages) > a.max_pages or doc.scanned_pages:
            print(f"skip {cid}: {len(doc.pages)} pages, {len(doc.scanned_pages)} scanned")
            continue
        answers = crossread.review(llm, doc, [(l["req_id"], claims[l["req_id"]]) for l in case["labels"]], label=cid)
        results[cid] = {"case": cid, "doc_id": doc.doc_id, "model": a.model, "pages": len(doc.pages), "answers": answers}
        store.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    pairs = []
    print(f"\n{'case':5} {'labels':>6} {'agree':>6} {'%':>5}")
    for cid, r in results.items():
        key = json.loads((KEYS / f"{cid}.json").read_text(encoding="utf-8"))
        ps = [(l["expected"], r["answers"][l["req_id"]]["verdict"]) for l in key["labels"]]
        pairs += ps
        print(f"{cid:5} {len(ps):>6} {sum(x == y for x, y in ps):>6} {sum(x == y for x, y in ps) / len(ps):>5.0%}")
    if pairs:
        print(f"ALL   {len(pairs):>6} {sum(x == y for x, y in pairs):>6} {sum(x == y for x, y in pairs) / len(pairs):>5.0%}  kappa={crossread.kappa(pairs):.2f}")
    print("model tokens:", [(m.name, m.tokens_in, m.tokens_out) for m in llm.meter.models()])


if __name__ == "__main__":
    main()
