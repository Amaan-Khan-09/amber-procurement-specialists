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

Earlier versions are not re-run: their stored answers (eval/handoff_set/frozen/) are re-scored against today's keys.
usage: python scripts/eval_handoffs.py    prints the versions side by side, writes eval/handoff_set/{cases,results}.json
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from amber import case as C, docs, submittal, triage  # noqa: E402
from amber.llm import Meter  # noqa: E402
from amber.ocr import reader_from_env  # noqa: E402

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
            # sets 4 and 5 were fresh once; they have been inspected since and are regression material now
            grp = {4: "regression set 4", 5: "regression set 5", 6: "fresh set 6"}.get(k.get("heldout_set"), "datasheet")
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


VERSIONS = {"v1": "commit 48b321c: anything under 0.70 to one queue",
            "v2": "commit 9cd1b4e (original baseline): decided / supplier / engineer",
            "v3": "commit 1d14f3e: second look at the clause",
            "v4": "candidate: second look on the whole evidence record, second reading of large documents"}
ORDER = ("v1", "v2", "v3", "v4")
FROZEN = [OUT / "frozen" / "results_1d14f3e.json", OUT / "frozen" / "fresh6_1d14f3e.json"]


def outcome3(exp: dict, got: dict) -> tuple[str, str | None]:
    """Strict outcome. Only a DECISION can be a resolution. A question to the supplier is counted as a question
    (well-founded or not); a clarification counts as resolved only when a reply verifies it (scored separately)."""
    e_act, g_act = ACTION[exp["expected"]], ACTION.get(got["answer"], "ask")
    route = got["route"]
    if route == "engineer":
        if exp["expected_route"] == "engineer" or g_act != e_act:
            return "justified hand-off", None
        return "unnecessary hand-off", None
    if exp["expected_route"] == "engineer":  # the key says a person must look: acting alone or only asking is a miss
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


def frozen_answers() -> dict[str, dict]:
    """The stored answers of earlier versions, produced by their own code: only their SCORES are recomputed here, so a
    corrected label changes every version the same way."""
    out: dict = {}
    for f in FROZEN:
        if f.exists():
            for r in json.loads(f.read_text(encoding="utf-8"))["results"]:
                out[r["id"]] = {v: {k: r[v].get(k) for k in ("answer", "route", "kind")} for v in ("v1", "v2", "v3") if v in r}
    return out


def datasheet_answers() -> dict[str, dict]:
    """'G7/R01' -> {answer, route, kind, why} from today's code on the saved model readings."""
    out: dict = {}
    seconds, readers = C.second_readings(), C.second_answers()
    for f in sorted(KEYS.glob("*.json")):
        if not re.fullmatch(r"[GU]\d+\.json", f.name) or not (ROOT / "examples" / f.name).exists():
            continue
        k = json.loads(f.read_text(encoding="utf-8"))
        reqs = _reqs(k)
        run = json.loads((ROOT / "examples" / f.name).read_text(encoding="utf-8"))
        doc = docs.load(ROOT / k["submittal"], ocr=reader_from_env(meter=Meter()))
        res = C.reconcile_supplier(reqs, doc, C.offers_from_run(run), [], [], seconds.get(f.stem), readers.get(f.stem))
        for x in res["findings"]:
            out[f"{f.stem}/{x['data']['req_id']}"] = {"answer": x["status"], "route": x["route"]["route"],
                                                       "kind": x["route"]["kind"], "why": x["why"][:300]}
    return out


def run() -> dict:
    cases = build_cases()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cases.json").write_text(json.dumps({"built_from": "eval/answer_keys (written before the code scored here)",
                                                 "cases": cases}, indent=1), encoding="utf-8")
    old = frozen_answers()
    ds = datasheet_answers()
    cf = C.run_case("GEN", root=ROOT / "runs" / "eval_cases", fresh=True)
    rec, link, pq = cf.output("reconcile"), cf.output("link"), cf.output("prequalify")
    bl1 = json.loads((ROOT / "examples/BL1.json").read_text(encoding="utf-8"))
    cells = {(f["data"]["bid"], f["data"]["scope_id"]): f for f in bl1["findings"] if f["id"].startswith("F-B")}
    results, missing = [], []
    for c in cases:
        g = c["group"]
        if g in ("datasheet", "regression set 4", "regression set 5", "fresh set 6"):
            now = ds[c["id"]]
        elif g == "package":
            f4 = next(f for f in rec[c["bid"]]["findings"] if f["data"]["req_id"] == c["req_id"])
            now = {"answer": f4["status"], "route": f4["route"]["route"], "kind": f4["route"]["kind"], "why": f4["why"][:300]}
        elif g == "link":
            lk = link["products"][c["bid"]]
            now = {"answer": lk["status"], "route": lk["route"]}
            if lk["status"] == "linked" and c.get("datasheet") and lk["datasheet"] != c["datasheet"]:
                now["answer"] = "wrong link"
        elif g == "decision":
            now = {"answer": "escalate", "route": "engineer"}
        elif g == "bid scope":
            f = cells.get((c["bid"], c["scope_id"]))
            st = f["data"]["scope_status"] if f else "silent"
            now = {"answer": st, "route": (triage.route_bid_cell(f) if f else {"route": "ask_supplier"})["route"]}
        elif g == "prequal":
            bid = next(bb for bb, v in cf.memory["bidder_vendor"].items() if v == c["vendor"])
            cr = pq[bid]["criteria"][c["criterion"]]
            now = {"answer": cr["status"], "route": cr["route"]}
        if c["id"] not in old:
            missing.append(c["id"])
            continue
        row = dict(c)
        for v, x in {**old[c["id"]], "v4": now}.items():
            o, s = outcome3(c, x)
            row[v] = {**x, "outcome": o, "severity": s}
        results.append(row)
    if missing:
        print(f"WARNING: {len(missing)} cases have no stored earlier answers and are not scored: {missing[:5]}")
    return {"results": results}


METRICS = ["to an engineer", "supplier questions", "clarification requests", "unresolved", "correct decisions",
           "incorrect decisions (critical)", "incorrect decisions (minor)", "missed escalations",
           "well-founded questions", "questions not needed", "unnecessary hand-offs", "right action"]


def table(rows: list[dict], label: str, quiet: bool = False) -> dict:
    out = {}
    vs = [v for v in ORDER if rows and all(v in r for r in rows)]
    for v in vs:
        o = Counter(r[v]["outcome"] for r in rows)
        eng = sum(r[v]["route"] == "engineer" for r in rows)
        asked = sum(r[v]["route"] == "ask_supplier" for r in rows)
        out[v] = {"n": len(rows), "to an engineer": eng,
                  "clarification requests": sum(r[v]["outcome"].startswith("clarification") for r in rows),
                  "supplier questions": sum(r[v]["outcome"].startswith("supplier question") for r in rows),
                  # nothing here has a follow-up, so every question is still open: unresolved = engineer + questions
                  "unresolved": eng + asked,
                  "correct decisions": o["correct decision"],
                  "well-founded questions": sum(r[v]["outcome"].endswith("well-founded") for r in rows),
                  "incorrect decisions (critical)": sum(r[v]["outcome"] == "incorrect decision" and r[v]["severity"] == "critical" for r in rows),
                  "incorrect decisions (minor)": sum(r[v]["outcome"] == "incorrect decision" and r[v]["severity"] == "minor" for r in rows),
                  "questions not needed": sum(r[v]["outcome"].endswith("not needed") for r in rows),
                  "missed escalations": o["missed escalation"],
                  "unnecessary hand-offs": o["unnecessary hand-off"],
                  "right action": sum(ACTION.get(r[v]["answer"], "ask") == ACTION[r["expected"]] for r in rows)}
    if not quiet and rows:
        n = len(rows)
        print(f"\n{label} (n = {n})")
        print(f"  {'':32}" + "".join(f"{v:>14}" for v in vs))
        for k in METRICS:
            print(f"  {k:32}" + "".join(f"{out[v][k]:>7} ({out[v][k] / n:>4.0%})" for v in vs))
    return out


def main() -> None:
    res = run()
    rows = res["results"]
    pick = lambda g: [r for r in rows if r["group"] == g]
    like = [r for r in rows if r["group"] in ("datasheet", "package", "link", "bid scope", "decision")]
    summary = {"versions": VERSIONS, "like_for_like": table(like, "Fixed development set"),
               "by_group": {g: table(pick(g), g, quiet=True) for g in ("datasheet", "package", "link", "bid scope", "decision")},
               "by_category": {c: table([r for r in like if r["category"] == c], c, quiet=True) for c in
                               ("routine", "missing_info", "conflict", "escalate")},
               "regression_set4": table(pick("regression set 4"), "Regression: G9"),
               "regression_set5": table(pick("regression set 5"), "Regression: G10 + G11 (fresh last round, inspected since)"),
               "fresh_set6": table(pick("fresh set 6"), "FRESH set 6: labelled after the candidate was frozen"),
               "new_specialist_prequal": table(pick("prequal"), "pre-qualification", quiet=True)}
    for a_, b_ in (("v3", "v4"),):
        print(f"\nDevelopment cases whose outcome changed from {a_} to {b_}:")
        for r in like:
            if (r[a_]["outcome"], r[a_]["route"], r[a_]["answer"]) != (r[b_]["outcome"], r[b_]["route"], r[b_]["answer"]):
                print(f"   {r['id']:14} key {r['expected'][:6]:>6}/{r['expected_route'][:3]}  {r[a_]['answer'][:6]:>6}/{r[a_]['route'][:3]} -> "
                      f"{r[b_]['answer'][:6]:>6}/{r[b_]['route'][:3]}  {r[b_]['outcome']}  ({r[b_].get('kind', '')})")
    (OUT / "results.json").write_text(json.dumps({"summary": summary, "results": rows}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
