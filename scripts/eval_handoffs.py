"""Hand-off evaluation: the same fixed cases, the version before (commit 48b321c's routing) and the version now.

The fixed set (eval/handoff_set/cases.json, rebuilt from the answer keys by this script; the keys were written first):
  datasheet   184 requirement checks on 9 real datasheets (keys eval/answer_keys/G*.json, U1.json)
  package      22 requirements where a bidder's own bid says something (key package_GEN.json, written before the code)
  link          4 bid -> datasheet product links (package_GEN.json)
  bid scope    44 scope cells of the bid comparison (bids_genset.json)
  decision      2 decisions that must stay with a person (award, schedule mitigation)
  prequal      36 pre-qualification criteria x 4 bidders (prequal_GEN.json): a NEW specialist, reported separately
Categories: routine | missing_info | conflict | escalate.

Each case has an expected answer and an expected route (decide / ask_supplier / engineer). Each version gives an
answer and a route. The ACTION of an answer: complies/included -> accept; deviates -> reject; missing/unclear/silent/
qualified/ambiguous -> ask the supplier; excluded/alternate -> price it.
  correct autonomous    the agent acted alone (decided, or sent the question to the supplier) and the action is right
  incorrect autonomous  it acted alone and the action is wrong; CRITICAL if it accepts what fails or is not shown, or
                        rejects what complies; otherwise minor (an unneeded question, or a question where a rejection
                        was due: nothing is approved either way)
  justified hand-off    an engineer was asked and the case needs judgement, or the agent's own answer was wrong
  unnecessary hand-off  an engineer was asked although the agent's answer was right and no judgement was needed

usage: python scripts/eval_handoffs.py          prints both versions, writes eval/handoff_set/{cases,results}.json
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from amber import case as C, docs, linking, submittal, triage, vendors  # noqa: E402
from amber.package import same_product  # noqa: E402

KEYS = ROOT / "eval" / "answer_keys"
OUT = ROOT / "eval" / "handoff_set"
ESCALATE_NOTE = re.compile(r"(?i)derat|footnote|infer|margin|dip basis|different .*basis|reasonably")
ACTION = {"complies": "accept", "included": "accept", "meets": "accept", "linked": "accept",
          "deviates": "reject", "fails": "reject",
          "missing": "ask", "unclear": "ask", "silent": "ask", "qualified": "ask", "ambiguous": "ask",
          "needs_verification": "ask", "none": "ask",
          "excluded": "price", "alternate": "price", "escalate": "escalate"}


def outcome(exp: dict, got: dict) -> tuple[str, str | None]:
    e_act, g_act = ACTION[exp["expected"]], ACTION.get(got["answer"], "ask")
    if got["route"] == "engineer":
        if exp["expected_route"] == "engineer" or g_act != e_act:
            return "justified hand-off", None
        return "unnecessary hand-off", None
    if exp["expected_route"] == "engineer" and exp["expected"] == "escalate":
        return "incorrect autonomous", "critical"
    if g_act == e_act:
        return "correct autonomous", None
    critical = (g_act == "accept" and e_act in ("reject", "ask")) or (g_act == "reject" and e_act == "accept") \
        or (g_act == "price" and e_act == "accept") or (g_act == "accept" and e_act == "price")
    return "incorrect autonomous", "critical" if critical else "minor"


# ---------------------------------------------------------------- the fixed set

def build_cases() -> list[dict]:
    cases = []
    for f in sorted(KEYS.glob("*.json")):
        if not re.fullmatch(r"[GU]\d+\.json", f.name):
            continue
        k = json.loads(f.read_text(encoding="utf-8"))
        for l in k["labels"]:
            esc = bool(ESCALATE_NOTE.search(l.get("notes", "")))
            cat = "escalate" if esc else ("routine" if l["expected"] in ("complies", "deviates") else "missing_info")
            route = "engineer" if esc else ("decide" if l["expected"] in ("complies", "deviates") else "ask_supplier")
            cases.append({"id": f"{f.stem}/{l['req_id']}", "group": "datasheet", "case": f.stem, "req_id": l["req_id"],
                          "expected": l["expected"], "category": cat, "expected_route": route})
    pk = json.loads((KEYS / "package_GEN.json").read_text(encoding="utf-8"))
    for r in pk["requirements"]:
        cases.append({"id": f"PKG/{r['bid']}/{r['req_id']}", "group": "package", "bid": r["bid"], "req_id": r["req_id"],
                      "expected": r["expected"], "category": r["category"], "expected_route": r["expected_route"]})
    for l in pk["links"]:
        cases.append({"id": f"LINK/{l['bid']}", "group": "link", "bid": l["bid"], "expected": l["expected"],
                      "datasheet": l["datasheet"], "category": l["category"], "expected_route": l["expected_route"]})
    for d in pk["decisions"]:
        cases.append({"id": d["id"], "group": "decision", "expected": "escalate", "category": "escalate", "expected_route": "engineer"})
    bk = json.loads((KEYS / "bids_genset.json").read_text(encoding="utf-8"))
    for sid, row in bk["matrix"].items():
        for b, st in row.items():
            cat = {"silent": "missing_info", "qualified": "conflict"}.get(st, "routine")
            cases.append({"id": f"BID/{b}/{sid}", "group": "bid scope", "bid": b, "scope_id": sid, "expected": st,
                          "category": cat, "expected_route": "ask_supplier" if st in ("silent", "qualified") else "decide"})
    pq = json.loads((KEYS / "prequal_GEN.json").read_text(encoding="utf-8"))
    for vid, crit in pq["vendors"].items():
        for cid, v in crit.items():
            cat = "routine" if v["expected"] in ("meets", "fails") else ("escalate" if cid == "Q7" else "missing_info")
            if "onflict" in v.get("notes", ""):
                cat = "conflict"
            cases.append({"id": f"PQ/{vid}/{cid}", "group": "prequal", "vendor": vid, "criterion": cid, "expected": v["expected"],
                          "category": cat, "expected_route": "engineer" if cid == "Q7" else
                          ("decide" if v["expected"] in ("meets", "fails") else "ask_supplier")})
    return cases


# ---------------------------------------------------------------- the two versions

def _reqs(case_key: dict):
    ck = json.loads((KEYS / case_key.get("checklist", "genset_requirements.json")).read_text(encoding="utf-8"))["requirements"]
    spec = docs.load(ROOT / case_key["spec"])
    row = submittal.load_schedule(str(ROOT / "data/schedules/equipment_schedule.csv"), case_key["tag"])
    return submittal.structure_requirements(C._NoModel(), spec, row, docs.doc_id_for(ROOT / "data/schedules/equipment_schedule.csv"), ck)


def datasheet_answers() -> tuple[dict, dict]:
    """(before, now) per 'G7/R01' -> {answer, route}"""
    before, now = {}, {}
    seconds = C.second_readings()
    for f in sorted(KEYS.glob("*.json")):
        if not re.fullmatch(r"[GU]\d+\.json", f.name):
            continue
        k = json.loads(f.read_text(encoding="utf-8"))
        reqs = _reqs(k)
        run = json.loads((ROOT / "examples" / f.name).read_text(encoding="utf-8"))
        offers = C.offers_from_run(run)
        doc = docs.load(ROOT / k["submittal"])
        o = json.loads(json.dumps(offers))
        submittal._flag_shared_evidence(reqs, o)
        fs, _ = submittal.decide_all(reqs, o, doc)
        from amber.schema import RunInfo, ToolResult
        fs = ToolResult(tool="check_submittal", findings=fs, result={}, run=RunInfo(models=[], latency_ms=0)).finalize().findings
        for x in fs:
            before[f"{f.stem}/{x.data['req_id']}"] = {"answer": x.status.value, "route": "engineer" if x.needs_human else "decide"}
        res = C.reconcile_supplier(reqs, doc, offers, [], [], seconds.get(f.stem))
        for x in res["findings"]:
            now[f"{f.stem}/{x['data']['req_id']}"] = {"answer": x["status"], "route": x["route"]["route"], "kind": x["route"]["kind"]}
    return before, now


def run() -> dict:
    cases = build_cases()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cases.json").write_text(json.dumps({"built_from": "eval/answer_keys (written before the code scored here)",
                                                 "cases": cases}, indent=1), encoding="utf-8")
    ds_before, ds_now = datasheet_answers()
    cf = C.run_case("GEN", root=ROOT / "runs" / "eval_cases", fresh=True)
    rec, link, pq = cf.output("reconcile"), cf.output("link"), cf.output("prequalify")
    pkg = json.loads((ROOT / "examples/package_GEN.json").read_text(encoding="utf-8"))
    bl1 = json.loads((ROOT / "examples/BL1.json").read_text(encoding="utf-8"))
    cells = {(f["data"]["bid"], f["data"]["scope_id"]): f for f in bl1["findings"] if f["id"].startswith("F-B")}
    key_pk = json.loads((KEYS / "package_GEN.json").read_text(encoding="utf-8"))
    results = []
    for c in cases:
        g = c["group"]
        if g == "datasheet":
            b, n = ds_before[c["id"]], ds_now[c["id"]]
        elif g == "package":
            ds = {f["data"]["req_id"]: f for f in rec[c["bid"]]["datasheet_only"]}[c["req_id"]]
            nf = {f["data"]["req_id"]: f for f in rec[c["bid"]]["findings"]}[c["req_id"]]
            case_id = key_pk["bidders"][c["bid"]]["datasheet_case"]
            b = ds_before[f"{case_id}/{c['req_id']}"]
            n = {"answer": nf["status"], "route": nf["route"]["route"], "kind": nf["route"]["kind"]}
        elif g == "link":
            sub = ROOT / "data/submittals" / (C.CaseFile("GEN", C.CASES["GEN"], root=ROOT / "runs" / "eval_cases")._datasheet_for(c["bid"]) or "")
            sp = same_product(pkg["result"]["parts"]["level_bids"]["products"][c["bid"]], str(sub)) if sub.is_file() else {"status": "unknown"}
            b = {"answer": "linked" if sp["status"] == "match" else "ambiguous", "route": "decide" if sp["status"] == "match" else "engineer"}
            lk = link["products"][c["bid"]]
            n = {"answer": lk["status"], "route": lk["route"]}
            if lk["status"] == "linked" and c.get("datasheet") and lk["datasheet"] != c["datasheet"]:
                n["answer"] = "wrong link"
        elif g == "decision":
            b = n = {"answer": "escalate", "route": "engineer"}
        elif g == "bid scope":
            f = cells.get((c["bid"], c["scope_id"]))
            st = f["data"]["scope_status"] if f else "silent"
            b = {"answer": st, "route": "engineer" if f and f["needs_human"] else "decide"}
            r = triage.route_bid_cell(f) if f else {"route": "ask_supplier"}
            n = {"answer": st, "route": r["route"]}
        elif g == "prequal":
            bid = next(bb for bb, v in cf.memory["bidder_vendor"].items() if v == c["vendor"])
            cr = pq[bid]["criteria"][c["criterion"]]
            b = {"answer": "needs_verification", "route": "engineer"}  # before: no specialist, a person did it all
            n = {"answer": cr["status"], "route": cr["route"]}
        ob, sb = outcome(c, b)
        on, sn = outcome(c, n)
        results.append({**c, "before": {**b, "outcome": ob, "severity": sb}, "now": {**n, "outcome": on, "severity": sn}})
    return {"results": results}


def table(rows: list[dict], label: str) -> dict:
    out = {}
    for v in ("before", "now"):
        cnt = Counter(r[v]["outcome"] for r in rows)
        crit = sum(1 for r in rows if r[v]["severity"] == "critical")
        eng = sum(1 for r in rows if r[v]["route"] == "engineer")
        sup = sum(1 for r in rows if r[v]["route"] == "ask_supplier")
        right = sum(1 for r in rows if ACTION.get(r[v]["answer"], "ask") == ACTION[r["expected"]])
        out[v] = {"n": len(rows), "correct autonomous": cnt["correct autonomous"], "justified hand-off": cnt["justified hand-off"],
                  "unnecessary hand-off": cnt["unnecessary hand-off"], "incorrect autonomous": cnt["incorrect autonomous"],
                  "critical": crit, "to an engineer": eng, "to the supplier": sup, "right action": right}
    print(f"\n{label} ({len(rows)} cases)")
    print(f"  {'':22} {'before':>16} {'now':>16}")
    for k in ("correct autonomous", "justified hand-off", "unnecessary hand-off", "incorrect autonomous", "critical",
              "to an engineer", "to the supplier", "right action"):
        b, n = out["before"][k], out["now"][k]
        print(f"  {k:22} {b:>6} ({b / len(rows):>4.0%})    {n:>6} ({n / len(rows):>4.0%})")
    return out


def main() -> None:
    res = run()
    rows = res["results"]
    like = [r for r in rows if r["group"] != "prequal"]
    summary = {"like_for_like": table(like, "Like for like: every case both versions handle"),
               "by_group": {g: table([r for r in rows if r["group"] == g], f"  group: {g}") for g in
                            ("datasheet", "package", "link", "bid scope", "decision")},
               "by_category": {c: table([r for r in like if r["category"] == c], f"  category: {c}") for c in
                               ("routine", "missing_info", "conflict", "escalate")},
               "new_specialist_prequal": table([r for r in rows if r["group"] == "prequal"],
                                               "New specialist: pre-qualification (before = no specialist, a person does it all)")}
    changed = [r for r in like if (r["before"]["outcome"], r["before"]["route"]) != (r["now"]["outcome"], r["now"]["route"])]
    print(f"\n{len(changed)} like-for-like cases changed outcome or route; worst now:")
    for r in rows:
        if r["now"]["outcome"] == "incorrect autonomous":
            print(f"   {r['id']:16} expected {r['expected']:>18}/{r['expected_route']:12} now {r['now']['answer']:>10}/{r['now']['route']:12} "
                  f"{r['now']['severity']}  ({r['now'].get('kind', '')})")
    (OUT / "results.json").write_text(json.dumps({"summary": summary, "results": rows}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
