"""Second reading of large documents: the independent reader (amber/crossread.py) on the pages that matter.

A 66- or 105-page package is too large to read whole on a free allowance, so those answers could never be confirmed
("absence not confirmed"). This reads, blind, only the requirements the first reading left open, on every page where the
code finds their distinctive words (up to the six densest pages per condition). The pages read are recorded: an
absence confirmed this way is confirmed on those pages, not on the whole document.

usage: python scripts/targeted_read.py G1 G3      -> eval/cross_checks/targeted_qwen3.8-27b.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from amber import crossread, docs, submittal  # noqa: E402
from amber.llm import LLM, Meter  # noqa: E402
from amber.ocr import reader_from_env  # noqa: E402

OUT = ROOT / "eval" / "cross_checks" / "targeted_qwen3.8-27b.json"
PER_CONDITION = 6


def open_requirements(case_id: str, reqs: list[dict], doc) -> list[str]:
    """Requirements whose saved reading, decided today, does not stand on its own."""
    from amber import case as C
    run = json.loads((ROOT / "examples" / f"{case_id}.json").read_text(encoding="utf-8"))
    res = C.reconcile_supplier(reqs, doc, C.offers_from_run(run), [], [], None, None, inspect=False)
    return [f["data"]["req_id"] for f in res["findings"] if f["route"]["route"] != "decide"]


def pages_for(doc, reqs: list[dict]) -> list[int]:
    pages: set[int] = set()
    for r in reqs:
        for c in r["conditions"]:
            m = submittal._mentioned(doc, c)
            if m:
                pages.update(m["ranked"][:PER_CONDITION])
    return sorted(pages)


def main() -> None:
    import eval_handoffs as E
    model = crossread.DEFAULT_MODEL
    store = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    llm = LLM(provider="groq", model=model)
    for cid in sys.argv[1:]:
        if cid in store:
            print(f"{cid}: already read, skipped")
            continue
        key = json.loads((ROOT / "eval" / "answer_keys" / f"{cid}.json").read_text(encoding="utf-8"))
        doc = docs.load(ROOT / key["submittal"], ocr=reader_from_env(meter=Meter()))
        reqs = E._reqs(key)
        want = set(open_requirements(cid, reqs, doc))
        chosen = [r for r in reqs if r["req_id"] in want]
        pages = pages_for(doc, chosen)
        part = docs.Document(doc_id=doc.doc_id, path=doc.path, pages=[doc.page(n) for n in pages], sha256=doc.sha256)
        print(f"{cid}: {len(chosen)} open requirements on {len(pages)} of {len(doc.pages)} pages", flush=True)
        answers = crossread.review(llm, part, [(r["req_id"], r["requirement"]) for r in chosen], label=cid,
                                   log=lambda m: print(m, flush=True))
        store[cid] = {"case": cid, "doc_id": doc.doc_id, "model": model, "pages_read": pages, "of_pages": len(doc.pages),
                      "answers": answers}
        OUT.write_text(json.dumps(store, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"{cid}: saved", flush=True)
    print("model tokens:", [(m.name, m.tokens_in, m.tokens_out) for m in llm.meter.models()])


if __name__ == "__main__":
    main()
