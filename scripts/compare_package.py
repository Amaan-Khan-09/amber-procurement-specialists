"""The same 22 package cases (eval/answer_keys/package_GEN.json) answered four ways, with the same saved readings:

  datasheet only            the datasheet alone, routing of commit 9cd1b4e
  datasheet only + look     the datasheet alone with the second look at the clause (today)
  combined (baseline)       datasheet + bid, routing of commit 9cd1b4e
  improved (now)            datasheet + bid, second look, supersession and conflict rules

usage: python scripts/compare_package.py   -> prints the table, writes eval/handoff_set/package_compare.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import eval_handoffs as E  # noqa: E402
from amber import case as C, docs, linking  # noqa: E402

VARIANTS = {"datasheet only": (False, False), "datasheet only + look": (False, True),
            "combined (baseline)": (True, False), "improved (now)": (True, True)}


def main() -> None:
    cf = C.CaseFile("GEN", C.CASES["GEN"], root=ROOT / "runs" / "eval_cases")
    cfg = C.CASES["GEN"]
    key = json.loads((E.KEYS / "package_GEN.json").read_text(encoding="utf-8"))
    pkg = json.loads((ROOT / cfg["saved_package"]).read_text(encoding="utf-8"))["result"]["parts"]["level_bids"]
    links = linking.link_products(pkg["products"], sorted(str(p) for p in (ROOT / "data/submittals").glob("*.pdf")))
    reqs = cf._reqs()
    seconds, readers = C.second_readings(), C.second_answers()
    out: dict = {v: [] for v in VARIANTS}
    for bid in sorted({r["bid"] for r in key["requirements"]}):
        case_id = key["bidders"][bid]["datasheet_case"]
        name = links[bid]["datasheet"] or links[bid]["candidates"][-1]["file"]
        d_doc = docs.load(ROOT / "data" / "submittals" / name)
        d_off = C.offers_from_run(json.loads((ROOT / "examples" / f"{case_id}.json").read_text(encoding="utf-8")))
        bid_run = json.loads((ROOT / "examples" / "commitments" / f"{bid}_bid.json").read_text(encoding="utf-8"))
        b_doc = docs.load(ROOT / bid_run["source_document"])
        b_doc.commitment = True
        b_off = C.offers_from_run(bid_run)
        for v, (combined, look) in VARIANTS.items():
            res = C.reconcile_supplier(reqs, d_doc, d_off, [b_doc] if combined else [], [b_off] if combined else [],
                                       seconds.get(case_id), readers.get(case_id), inspect=look)
            found = {f["data"]["req_id"]: f for f in res["findings"]}
            for r in key["requirements"]:
                if r["bid"] != bid:
                    continue
                f = found[r["req_id"]]
                got = {"answer": f["status"], "route": f["route"]["route"], "kind": f["route"]["kind"]}
                o, sev = E.outcome3(r, got)
                out[v].append({"id": f"PKG/{bid}/{r['req_id']}", "bid": bid, "req_id": r["req_id"], "expected": r["expected"],
                               "expected_route": r["expected_route"], **got, "outcome": o, "severity": sev,
                               "why": f["why"][:300]})
    summary = {}
    for v, rows in out.items():
        summary[v] = {"n": len(rows),
                      "right action": sum(E.ACTION.get(r["answer"], "ask") == E.ACTION[r["expected"]] for r in rows),
                      "to an engineer": sum(r["route"] == "engineer" for r in rows),
                      "correct decisions": sum(r["outcome"] == "correct decision" for r in rows),
                      "questions": sum(r["route"] == "ask_supplier" for r in rows),
                      "wrong decisions": sum(r["outcome"] == "incorrect decision" for r in rows),
                      "missed escalations": sum(r["outcome"] == "missed escalation" for r in rows)}
    cols = list(next(iter(summary.values())))
    print(f"{'variant':26}" + "".join(f"{c:>20}" for c in cols))
    for v, s in summary.items():
        print(f"{v:26}" + "".join(f"{s[c]:>20}" for c in cols))
    for v in VARIANTS:
        print(v, "not right:", [r["id"][4:] for r in out[v] if E.ACTION.get(r["answer"], "ask") != E.ACTION[r["expected"]]])
    (E.OUT / "package_compare.json").write_text(json.dumps({"summary": summary, "rows": out}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
