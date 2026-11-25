"""Report the result of a human review of the answer keys (eval/cross_checks/human_review.csv, filled in by a person).

It changes no answer key. It reports:
  - how often the key, and the blind reviewer model, agree with the person
  - on the cells where key and model disagreed, who the person sided with
  - what the pipeline's accuracy is under the key as written, and under the key with the person's labels where they differ
    (so a reader sees both numbers, and nobody can say a label was changed to suit the agent)

usage: python scripts/apply_human_review.py [--csv eval/cross_checks/human_review.csv]
"""
import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

VERDICTS = {"complies", "deviates", "missing", "unclear"}
OUT = ROOT / "eval" / "cross_checks"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(OUT / "human_review.csv"))
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.csv, encoding="utf-8")))
    done = [r for r in rows if r["human_label"].strip().lower() in VERDICTS]
    if not done:
        sys.exit("no row has a human_label yet (complies / deviates / missing / unclear)")
    names = sorted({r["reviewer_name"].strip() for r in done if r["reviewer_name"].strip()})
    n = len(done)
    key_ok = sum(r["human_label"].strip().lower() == r["key"] for r in done)
    mod_ok = sum(r["human_label"].strip().lower() == r["model"] for r in done)
    print(f"reviewed by: {', '.join(names) or '(name missing)'} | cells labelled: {n} of {len(rows)}")
    print(f"person agrees with the key  : {key_ok}/{n} ({key_ok / n:.0%})")
    print(f"person agrees with the model: {mod_ok}/{n} ({mod_ok / n:.0%})")
    dis = [r for r in done if r["key"] != r["model"]]
    side = Counter("key" if r["human_label"].strip().lower() == r["key"] else "model" if r["human_label"].strip().lower() == r["model"] else "neither" for r in dis)
    print(f"cells where key and model disagreed ({len(dis)}): the person sided with the key {side['key']}, the model {side['model']}, neither {side['neither']}")
    agreed = [r for r in done if r["key"] == r["model"]]
    if agreed:
        print(f"cells where key and model agreed ({len(agreed)}): the person agreed with them on {sum(r['human_label'].strip().lower() == r['key'] for r in agreed)}")

    import replay_decisions as rd  # noqa: E402  (slow: replays the saved runs)
    override = {(r["case"], r["req_id"]): r["human_label"].strip().lower() for r in done}
    tot = defaultdict(lambda: [0, 0, 0, 0])  # n, right as written, right under the person's labels, cells changed
    for cid in sorted({r["case"] for r in done}):
        case, _, res = rd.replay(cid)
        labels = {l["req_id"]: l["expected"] for l in case["labels"]}
        t = tot[case["split"] + (f" set {case.get('heldout_set', 1)}" if case["split"] == "heldout" else "")]
        for f in res.findings:
            rid = f.data["req_id"]
            if rid not in labels:
                continue
            h = override.get((cid, rid), labels[rid])
            t[0] += 1
            t[1] += f.status.value == labels[rid]
            t[2] += f.status.value == h
            t[3] += h != labels[rid]
    print("\npipeline accuracy on the reviewed documents:")
    print(f"{'split':16} {'n':>4} {'key as written':>16} {'with the person''s labels':>26} {'cells changed':>14}")
    for k, (nn, a1, a2, ch) in sorted(tot.items()):
        print(f"{k:16} {nn:>4} {a1:>10} ({a1 / nn:.0%}) {a2:>14} ({a2 / nn:.0%}) {ch:>10}")
    (OUT / "human_review_results.json").write_text(json.dumps({"reviewers": names, "cells": n, "agree_key": key_ok, "agree_model": mod_ok,
                                                              "sided": dict(side)}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
