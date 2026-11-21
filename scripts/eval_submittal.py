"""Score check_submittal against the person-made answer keys.

usage: python scripts/eval_submittal.py [--run] [--split dev|heldout|all] [--provider groq|gemini|ollama]
  --run   run the agent on each labelled case first (otherwise uses saved runs/<case>.json)

Reports, per case and overall:
  accuracy            verdict == label
  false approvals     agent says complies, label says deviates/missing (the costliest mistake)
  false rejections    agent says deviates, label says complies
  page agreement      agent's submittal citation is on the labelled page (when both exist)
  fabrications        citations whose quote is NOT on the cited page when re-checked from scratch (target 0)
  handoff rate        share of findings sent to a person
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from amber import docs  # noqa: E402
from amber.verify import match_level  # noqa: E402

KEYS = ROOT / "eval/answer_keys"
RUNS = ROOT / "runs"
VERDICTS = ["complies", "deviates", "missing", "unclear"]


def labelled_cases(split: str) -> list[dict]:
    out = []
    for f in sorted(KEYS.glob("*.json")):
        if not re.fullmatch(r"G\d+\.json", f.name):  # Windows globs ignore case: genset_*.json
            continue
        c = json.loads(f.read_text(encoding="utf-8"))
        if split != "all" and c["split"] != split:
            continue
        if all(l.get("expected") in VERDICTS for l in c["labels"]):
            out.append(c)
        elif any(l.get("expected") for l in c["labels"]):
            print(f"skip {c['case_id']}: partly labelled")
        else:
            print(f"skip {c['case_id']}: not labelled yet")
    return out


def recheck_citations(run: dict, paths: dict[str, str]) -> int:
    """Count citations whose quote is not on the cited page (fresh check, independent of the agent)."""
    loaded, bad = {}, 0
    for f in run["findings"]:
        for c in f["citations"]:
            if c["doc_id"] not in paths:
                continue  # schedule citations are checked against the CSV when produced
            d = loaded.setdefault(c["doc_id"], docs.load(paths[c["doc_id"]]))
            pg = d.page(c["page"])
            if pg is None or match_level(c["quote"], pg.text) is None:
                bad += 1
    return bad


def score(case: dict, run: dict) -> dict:
    got = {f["data"]["req_id"]: f for f in run["findings"]}
    conf = Counter()
    n = ok = fa = fr = pages_both = pages_ok = 0
    for l in case["labels"]:
        f = got.get(l["req_id"])
        pred = f["status"] if f else "missing"
        conf[(l["expected"], pred)] += 1
        n += 1
        ok += pred == l["expected"]
        fa += pred == "complies" and l["expected"] in ("deviates", "missing")
        fr += pred == "deviates" and l["expected"] == "complies"
        sub_pages = {c["page"] for c in (f or {}).get("citations", []) if c["doc_id"] == docs.doc_id_for(case["submittal"])}
        if l.get("submittal_page") and sub_pages:
            pages_both += 1
            pages_ok += int(l["submittal_page"]) in sub_pages
    paths = {docs.doc_id_for(case["spec"]): str(ROOT / case["spec"]),
             docs.doc_id_for(case["submittal"]): str(ROOT / case["submittal"])}
    return {"case": case["case_id"], "split": case["split"], "n": n, "accuracy": ok / n,
            "false_approvals": fa, "false_rejections": fr,
            "page_agreement": (pages_ok / pages_both) if pages_both else None,
            "fabrications": recheck_citations(run, paths),
            "handoff_rate": sum(f["needs_human"] for f in run["findings"]) / max(1, len(run["findings"])),
            "cost_usd": sum(m["cost_usd"] for m in run["run"]["models"]),
            "latency_s": run["run"]["latency_ms"] / 1000, "confusion": conf}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--split", default="all")
    ap.add_argument("--provider")
    a = ap.parse_args()
    cases = labelled_cases(a.split)
    if not cases:
        print("No fully labelled cases yet. See eval/answer_keys/README.md.")
        return
    results = []
    for c in cases:
        run_file = RUNS / f"{c['case_id']}.json"
        if a.run or not run_file.exists():
            from amber.llm import LLM
            from amber.submittal import check_submittal
            checklist = json.loads((KEYS / "genset_requirements.json").read_text(encoding="utf-8"))["requirements"]
            res = check_submittal(str(ROOT / c["spec"]), str(ROOT / c["submittal"]), c["tag"],
                                  str(ROOT / "data/schedules/equipment_schedule.csv"), checklist=checklist,
                                  llm=LLM(provider=a.provider))
            RUNS.mkdir(exist_ok=True)
            run_file.write_text(res.model_dump_json(indent=2), encoding="utf-8")
        results.append(score(c, json.loads(run_file.read_text(encoding="utf-8"))))

    print(f"\n{'case':5} {'split':8} {'acc':>5} {'falseOK':>7} {'falseNO':>7} {'pages':>6} {'fabr':>4} {'human':>6} {'cost$':>8} {'secs':>6}")
    for r in results:
        pa = f"{r['page_agreement']:.0%}" if r["page_agreement"] is not None else "-"
        print(f"{r['case']:5} {r['split']:8} {r['accuracy']:5.0%} {r['false_approvals']:7} {r['false_rejections']:7} "
              f"{pa:>6} {r['fabrications']:4} {r['handoff_rate']:6.0%} {r['cost_usd']:8.4f} {r['latency_s']:6.0f}")
    total = Counter()
    for r in results:
        total.update(r["confusion"])
    print("\nconfusion (rows = label, cols = agent):")
    print(" " * 10 + "".join(f"{v:>10}" for v in VERDICTS))
    for t in VERDICTS:
        print(f"{t:10}" + "".join(f"{total[(t, p)]:10}" for p in VERDICTS))


if __name__ == "__main__":
    main()
