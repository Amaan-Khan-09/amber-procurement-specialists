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
            route = l.get("expected_route") or ("engineer" if esc else
                                                ("decide" if l["expected"] in ("complies", "deviates") else "ask_supplier"))
            if l.get("expected_route"):  # newer keys state the route; the category follows it
                cat = {"engineer": "escalate", "decide": "routine", "ask_supplier": "missing_info"}[route]
            if not (ROOT / "examples" / f.name).exists():
                continue  # labelled but not run yet
            grp = {4: "unseen datasheet", 5: "fresh unseen"}.get(k.get("heldout_set"), "datasheet")  # labelled, then run once
            cases.append({"id": f"{f.stem}/{l['req_id']}", "group": grp, "case": f.stem, "req_id": l["req_id"],
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


VERSIONS = {"v1": "routing at commit 48b321c (one queue: anything under 0.70 to a person)",
            "v2": "commit 9cd1b4e: decided / ask the supplier / engineer, supplier's own documents reconciled",
            "v3": "now: plus a second look in code at the clause (computed from the quote, disputed clause, option "
                  "dependence, one missing fact -> focused clarification)"}


def outcome3(exp: dict, got: dict) -> tuple[str, str | None]:
    """Strict outcome. Only a DECISION can be a resolution. A question to the supplier is counted as a question
    (well-founded or not); a clarification counts as resolved only when a reply verifies it (scored separately)."""
    e_act, g_act = ACTION[exp["expected"]], ACTION.get(got["answer"], "ask")
    route = got["route"]
    if route == "engineer":
        if exp["expected_route"] == "engineer" or g_act != e_act:
            return "justified hand-off", None
        return "unnecessary hand-off", None
    if exp["expected_route"] == "engineer" and exp["expected"] == "escalate":
        return "missed escalation", "missed escalation"
    if route == "ask_supplier" or g_act == "ask":
        label = "clarification" if got.get("kind") == "clarification" else "supplier question"
        if e_act == "ask":
            return f"{label}: well-founded", None
        return f"{label}: not needed", ("minor" if e_act in ("accept", "price") else "minor (a rejection was due)")
    if g_act == e_act:
        return "correct decision", None
    critical = (g_act == "accept" and e_act in ("reject", "ask")) or (g_act == "reject" and e_act == "accept") \
        or (g_act == "price" and e_act == "accept") or (g_act == "accept" and e_act == "price")
    return "incorrect decision", "critical" if critical else "minor"


def datasheet_answers() -> dict[str, dict]:
    """version -> {'G7/R01': {answer, route, kind}} on the same saved model readings."""
    out = {"v1": {}, "v2": {}, "v3": {}}
    seconds, readers = C.second_readings(), C.second_answers()
    from amber.schema import RunInfo, ToolResult
    for f in sorted(KEYS.glob("*.json")):
        if not re.fullmatch(r"[GU]\d+\.json", f.name) or not (ROOT / "examples" / f.name).exists():
            continue
        k = json.loads(f.read_text(encoding="utf-8"))
        reqs = _reqs(k)
        run = json.loads((ROOT / "examples" / f.name).read_text(encoding="utf-8"))
        offers = C.offers_from_run(run)
        doc = docs.load(ROOT / k["submittal"])
        o = json.loads(json.dumps(offers))
        submittal._flag_shared_evidence(reqs, o)
        fs, _ = submittal.decide_all(reqs, o, doc)
        fs = ToolResult(tool="check_submittal", findings=fs, result={}, run=RunInfo(models=[], latency_ms=0)).finalize().findings
        for x in fs:
            out["v1"][f"{f.stem}/{x.data['req_id']}"] = {"answer": x.status.value, "route": "engineer" if x.needs_human else "decide"}
        for v, ins in (("v2", False), ("v3", True)):
            res = C.reconcile_supplier(reqs, doc, offers, [], [], seconds.get(f.stem), readers.get(f.stem), inspect=ins)
            for x in res["findings"]:
                out[v][f"{f.stem}/{x['data']['req_id']}"] = {"answer": x["status"], "route": x["route"]["route"],
                                                              "kind": x["route"]["kind"], "why": x["why"][:300]}
    return out


def run() -> dict:
    cases = build_cases()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cases.json").write_text(json.dumps({"built_from": "eval/answer_keys (written before the code scored here)",
                                                 "cases": cases}, indent=1), encoding="utf-8")
    ds = datasheet_answers()
    cf = C.run_case("GEN", root=ROOT / "runs" / "eval_cases", fresh=True)
    rec, link, pq = cf.output("reconcile"), cf.output("link"), cf.output("prequalify")
    pkg = json.loads((ROOT / "examples/package_GEN.json").read_text(encoding="utf-8"))
    bl1 = json.loads((ROOT / "examples/BL1.json").read_text(encoding="utf-8"))
    cells = {(f["data"]["bid"], f["data"]["scope_id"]): f for f in bl1["findings"] if f["id"].startswith("F-B")}
    key_pk = json.loads((KEYS / "package_GEN.json").read_text(encoding="utf-8"))
    results = []
    for c in cases:
        g = c["group"]
        if g in ("datasheet", "unseen datasheet", "fresh unseen"):
            got = {v: ds[v][c["id"]] for v in ("v1", "v2", "v3")}
        elif g == "package":
            pick = lambda fs: next(f for f in fs if f["data"]["req_id"] == c["req_id"])
            case_id = key_pk["bidders"][c["bid"]]["datasheet_case"]
            f2, f3 = pick(rec[c["bid"]]["before_inspection"]), pick(rec[c["bid"]]["findings"])
            got = {"v1": ds["v1"][f"{case_id}/{c['req_id']}"],
                   "v2": {"answer": f2["status"], "route": f2["route"]["route"], "kind": f2["route"]["kind"]},
                   "v3": {"answer": f3["status"], "route": f3["route"]["route"], "kind": f3["route"]["kind"]}}
        elif g == "link":
            sub = ROOT / "data/submittals" / (C.CaseFile("GEN", C.CASES["GEN"], root=ROOT / "runs" / "eval_cases")._datasheet_for(c["bid"]) or "")
            sp = same_product(pkg["result"]["parts"]["level_bids"]["products"][c["bid"]], str(sub)) if sub.is_file() else {"status": "unknown"}
            lk = link["products"][c["bid"]]
            n = {"answer": lk["status"], "route": lk["route"]}
            if lk["status"] == "linked" and c.get("datasheet") and lk["datasheet"] != c["datasheet"]:
                n["answer"] = "wrong link"
            got = {"v1": {"answer": "linked" if sp["status"] == "match" else "ambiguous",
                          "route": "decide" if sp["status"] == "match" else "engineer"}, "v2": n, "v3": n}
        elif g == "decision":
            got = {v: {"answer": "escalate", "route": "engineer"} for v in ("v1", "v2", "v3")}
        elif g == "bid scope":
            f = cells.get((c["bid"], c["scope_id"]))
            st = f["data"]["scope_status"] if f else "silent"
            r = triage.route_bid_cell(f) if f else {"route": "ask_supplier"}
            got = {"v1": {"answer": st, "route": "engineer" if f and f["needs_human"] else "decide"},
                   "v2": {"answer": st, "route": r["route"]}, "v3": {"answer": st, "route": r["route"]}}
        elif g == "prequal":
            bid = next(bb for bb, v in cf.memory["bidder_vendor"].items() if v == c["vendor"])
            cr = pq[bid]["criteria"][c["criterion"]]
            n = {"answer": cr["status"], "route": cr["route"]}
            got = {"v1": {"answer": "needs_verification", "route": "engineer"}, "v2": n, "v3": n}
        row = dict(c)
        for v, x in got.items():
            o, s = outcome3(c, x)
            row[v] = {**x, "outcome": o, "severity": s}
        results.append(row)
    return {"results": results}


METRICS = ["to an engineer", "clarification requests", "supplier questions", "correct decisions",
           "well-founded questions", "incorrect decisions (critical)", "incorrect decisions (minor)",
           "questions not needed", "missed escalations", "unnecessary hand-offs", "right action"]


def table(rows: list[dict], label: str, quiet: bool = False) -> dict:
    out = {}
    for v in ("v1", "v2", "v3"):
        o = Counter(r[v]["outcome"] for r in rows)
        out[v] = {"n": len(rows),
                  "to an engineer": sum(r[v]["route"] == "engineer" for r in rows),
                  "clarification requests": sum(r[v]["outcome"].startswith("clarification") for r in rows),
                  "supplier questions": sum(r[v]["outcome"].startswith("supplier question") for r in rows),
                  "correct decisions": o["correct decision"],
                  "well-founded questions": sum(r[v]["outcome"].endswith("well-founded") for r in rows),
                  "incorrect decisions (critical)": sum(r[v]["outcome"] == "incorrect decision" and r[v]["severity"] == "critical" for r in rows),
                  "incorrect decisions (minor)": sum(r[v]["outcome"] == "incorrect decision" and r[v]["severity"] == "minor" for r in rows),
                  "questions not needed": sum(r[v]["outcome"].endswith("not needed") for r in rows),
                  "missed escalations": o["missed escalation"],
                  "unnecessary hand-offs": o["unnecessary hand-off"],
                  "right action": sum(ACTION.get(r[v]["answer"], "ask") == ACTION[r["expected"]] for r in rows)}
    if not quiet:
        n = len(rows)
        print(f"\n{label} (n = {n})")
        print(f"  {'':32} {'v1':>12} {'v2 (baseline)':>15} {'v3 (now)':>12}")
        for k in METRICS:
            print(f"  {k:32} " + " ".join(f"{out[v][k]:>5} ({out[v][k] / n:>4.0%})".rjust(w) for v, w in (("v1", 12), ("v2", 15), ("v3", 12))))
    return out


def main() -> None:
    res = run()
    rows = res["results"]
    like = [r for r in rows if r["group"] not in ("prequal", "unseen datasheet", "fresh unseen")]
    summary = {"versions": VERSIONS, "like_for_like": table(like, "Like for like: the fixed development set"),
               "by_group": {g: table([r for r in rows if r["group"] == g], f"  group: {g}", quiet=True) for g in
                            ("datasheet", "package", "link", "bid scope", "decision")},
               "by_category": {c: table([r for r in like if r["category"] == c], f"  category: {c}", quiet=True) for c in
                               ("routine", "missing_info", "conflict", "escalate")},
               "unseen_set4": table([r for r in rows if r["group"] == "unseen datasheet"], "G9 (inspected earlier; regression case for the 50 C option)"),
               "fresh_unseen_set5": table([r for r in rows if r["group"] == "fresh unseen"],
                                          "Fresh unseen, held-out set 5 (G10 + G11: labelled after the code was frozen, run once)")
                                    if any(r["group"] == "fresh unseen" for r in rows) else None,
               "new_specialist_prequal": table([r for r in rows if r["group"] == "prequal"], "pre-qualification", quiet=True)}
    print("\nEvery like-for-like case whose outcome changed from v2 to v3:")
    for r in like:
        if (r["v2"]["outcome"], r["v2"]["route"]) != (r["v3"]["outcome"], r["v3"]["route"]):
            print(f"   {r['id']:14} key {r['expected']:>9}/{r['expected_route']:12} v2 {r['v2']['answer']:>9}/{r['v2']['route']:12} -> "
                  f"v3 {r['v3']['answer']:>9}/{r['v3']['route']:12} {r['v3']['outcome']}  ({r['v3'].get('kind', '')})")
    (OUT / "results.json").write_text(json.dumps({"summary": summary, "results": rows}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
