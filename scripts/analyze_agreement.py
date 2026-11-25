"""Does agreement between two independent readers predict a right answer?

For every requirement that both our pipeline (gpt-oss-120b + code) and the blind reviewer (a different model family,
scripts/cross_check_keys.py) answered, compare with the answer key:
  - pipeline vs key, reviewer vs key, pipeline vs reviewer
  - the pipeline's accuracy when the reviewer agrees with it, and when it does not
  - the same, split by whether the pipeline handed the answer to a person

usage: python scripts/analyze_agreement.py [--reviewer qwen3.8-27b]
The pipeline column is the CURRENT decision code replayed over the saved model readings (scripts/replay_decisions.py).
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import replay_decisions as rd  # noqa: E402

OUT = ROOT / "eval" / "cross_checks"


def collect(reviewer: str) -> list[dict]:
    rev = json.loads((OUT / f"{reviewer}.json").read_text(encoding="utf-8"))
    rows = []
    for cid, r in rev.items():
        case, _, res = rd.replay(cid)
        labels = {l["req_id"]: l["expected"] for l in case["labels"]}
        for f in res.findings:
            rid = f.data["req_id"]
            if rid in labels and rid in r["answers"]:
                rows.append({"case": cid, "req": rid, "key": labels[rid], "pipeline": f.status.value, "human": f.needs_human,
                             "conf": f.confidence, "reviewer": r["answers"][rid]["verdict"], "why": f.why})
    return rows


def pct(a: int, b: int) -> str:
    return f"{a}/{b} ({a / b:.0%})" if b else "-"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reviewer", default="qwen3.8-27b")
    a = ap.parse_args()
    rows = collect(a.reviewer)
    n = len(rows)
    print(f"requirements answered by all three: {n} ({', '.join(sorted({r['case'] for r in rows}))})")
    print("pipeline vs key  :", pct(sum(r["pipeline"] == r["key"] for r in rows), n))
    print("reviewer vs key  :", pct(sum(r["reviewer"] == r["key"] for r in rows), n))
    print("pipeline vs reviewer:", pct(sum(r["pipeline"] == r["reviewer"] for r in rows), n))
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        agree = r["pipeline"] == r["reviewer"]
        tier = "automatic" if not r["human"] else "handed to a person"
        groups[f"{tier} | reviewer {'agrees' if agree else 'disagrees'}"].append(r)
    print(f"\n{'group':52} {'n':>4}  pipeline right")
    for g in sorted(groups):
        print(f"{g:52} {len(groups[g]):>4}  {pct(sum(x['pipeline'] == x['key'] for x in groups[g]), len(groups[g]))}")
    print("\nhanded to a person, by the pipeline's verdict, when the reviewer agrees:")
    for v in ("complies", "deviates", "missing", "unclear"):
        sub = [r for r in rows if r["human"] and r["pipeline"] == v and r["reviewer"] == v]
        print(f"  {v:9} n={len(sub):>3}  right {pct(sum(x['key'] == v for x in sub), len(sub))}")
    ag = [r for r in rows if r["human"] and r["pipeline"] == r["reviewer"] and r["pipeline"] != "unclear"]
    print(f"\nconcrete answers (not 'unclear') handed to a person that the reviewer independently confirms: {len(ag)}"
          f"  -> right {pct(sum(x['key'] == x['pipeline'] for x in ag), len(ag))}")
    for r in ag:
        if r["key"] != r["pipeline"]:
            print(f"    both models say {r['pipeline']}, key says {r['key']}: {r['case']} {r['req']} | {r['why'][:90]}")
    (OUT / f"agreement_{a.reviewer}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
