"""What is inside the share of answers that go to a person, and how often is each kind right?

Uses the CURRENT decision code replayed over every saved run (scripts/replay_decisions.py) and the answer keys.
usage: python scripts/handoff_breakdown.py   -> prints a table, writes eval/cross_checks/handoff_breakdown.json
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import replay_decisions as rd  # noqa: E402


def reason(f) -> str:
    w, st = f.why, f.status.value
    if not f.needs_human:
        return "decided by the agent alone"
    if st == "unclear":
        if "no value found, but the submittal mentions" in w:
            return "unclear: related words found, but no value"
        if "do not appear in the quote" in w or "quote not found" in w:
            return "unclear: a reported value was not in its own quote"
        if "disagree" in w and "model reading" in w:
            return "unclear: the model and the code disagree"
        if "evidence shows" in w and "does not mention" in w:
            return "unclear: only some of the required words found"
        return "unclear: other"
    if "model judgement on verified quote" in w:
        return f"{st}: the model's judgement of a verified quote"
    if "unit" in w and "not shown" in w:
        return f"{st}: number found, its unit not printed beside it"
    if "scanned page" in w:
        return f"{st}: read from a scanned page"
    return f"{st}: other"


def main() -> None:
    by = defaultdict(lambda: [0, 0])
    total = 0
    for cid in rd.cases():
        case, _, res = rd.replay(cid)
        labels = {l["req_id"]: l["expected"] for l in case["labels"]}
        for f in res.findings:
            rid = f.data["req_id"]
            if rid in labels:
                total += 1
                r = reason(f)
                by[r][0] += 1
                by[r][1] += f.status.value == labels[rid]
    print(f"{total} labelled answers, current decision code\n")
    print(f"{'what the answer is':58} {'n':>4} {'right':>6} {'% right':>8}")
    for k, (n, ok) in sorted(by.items(), key=lambda kv: -kv[1][0]):
        print(f"{k:58} {n:>4} {ok:>6} {ok / n:>8.0%}")
    h = sum(n for k, (n, _) in by.items() if k != "decided by the agent alone")
    print(f"\nneeds a person: {h}/{total} = {h / total:.0%}")
    (ROOT / "eval" / "cross_checks" / "handoff_breakdown.json").write_text(
        json.dumps({"total": total, "groups": {k: {"n": n, "right": ok} for k, (n, ok) in by.items()}}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
