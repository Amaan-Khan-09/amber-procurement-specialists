"""Score a person's blind review: agreement with the key, every disagreement, and every version re-scored with the
person's labels where they differ. The answer keys are never edited by this script.

usage: python scripts/apply_blind_review.py <filled review.csv>  -> eval/review/result.json
"""
import copy
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import eval_handoffs as E  # noqa: E402

ROUTES = {"decide", "ask_supplier", "engineer"}


def apply(filled: list[dict], mapping: dict, results: list[dict]) -> dict:
    by = {m["id"]: int(n) for n, m in mapping.items()}
    rows = {int(r["item"]): r for r in filled}
    checked = disagreements = 0
    notes, corrected = [], copy.deepcopy(results)
    names = sorted({(r.get("reviewer") or "").strip() for r in filled if (r.get("reviewer") or "").strip()})
    for r in corrected:
        row = rows.get(by.get(r["id"], -1))
        if not row:
            continue
        ans, route = (row.get("your_answer") or "").strip().lower(), (row.get("your_route") or "").strip().lower()
        if not ans:
            continue
        if ans not in E.ACTION or (route and route not in ROUTES):
            notes.append(f"item {row['item']}: unreadable answer {ans!r} / route {route!r}; ignored")
            continue
        checked += 1
        new_route = route or r["expected_route"]
        if ans != r["expected"] or new_route != r["expected_route"]:
            disagreements += 1
            notes.append(f"{r['id']}: key {r['expected']}/{r['expected_route']} -> reviewer {ans}/{new_route}: {row.get('comment', '')[:160]}")
        r["expected"], r["expected_route"] = ans, new_route
        for v in E.ORDER:
            if v in r:
                o, s = E.outcome3(r, r[v])
                r[v].update(outcome=o, severity=s)
    like = lambda rs: [x for x in rs if x["group"] in ("datasheet", "package", "link", "bid scope", "decision")]
    return {"reviewer": names, "rows_in_sheet": len(filled), "rows_checked": checked, "disagreements": disagreements,
            "notes": notes,
            "as_labelled": E.table(like(results), "As labelled", quiet=True),
            "with_reviewer_labels": E.table(like(corrected), "With the reviewer's labels", quiet=True),
            "fresh_as_labelled": E.table([x for x in results if x["group"] == "fresh set 6"], "", quiet=True),
            "fresh_with_reviewer_labels": E.table([x for x in corrected if x["group"] == "fresh set 6"], "", quiet=True)}


def main() -> None:
    with open(sys.argv[1], encoding="utf-8-sig", newline="") as fh:
        filled = list(csv.DictReader(fh))
    mapping = json.loads((ROOT / "eval/review/mapping.json").read_text(encoding="utf-8"))["items"]
    results = json.loads((ROOT / "eval/handoff_set/results.json").read_text(encoding="utf-8"))["results"]
    out = apply(filled, mapping, results)
    (ROOT / "eval/review/result.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"reviewer {out['reviewer'] or '(no name given)'}: {out['rows_checked']} of {out['rows_in_sheet']} rows checked, "
          f"{out['disagreements']} disagreements")
    for n in out["notes"]:
        print("  ", n)
    if out["rows_checked"]:
        print(f"\n{'metric':32}" + "".join(f"{v + ' key':>10}{v + ' rev':>10}" for v in ("v2", "v3", "v4")))
        for k in E.METRICS:
            print(f"{k:32}" + "".join(f"{out['as_labelled'][v][k]:>10}{out['with_reviewer_labels'][v][k]:>10}" for v in ("v2", "v3", "v4")))


if __name__ == "__main__":
    main()
