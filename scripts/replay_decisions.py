"""Replay the code's decision stage on saved runs, with no model and no tokens.

The model only reads: it reports, per condition, a value, a unit and a quote. Everything after that (verifying the
quote, comparing numbers, guards, confidence, hand-off) is code. A saved run keeps what the model reported, so the
same code can be run again over it. This lets a change to the decision code be measured on every labelled case in
seconds, and shows exactly which verdicts it changes and whether each change is right.

usage:
  python scripts/replay_decisions.py                      score the current code over every saved run
  python scripts/replay_decisions.py --out before.json    also store the verdicts
  python scripts/replay_decisions.py --vs before.json     list every verdict that changed since, right or wrong
Reads examples/<case>.json (committed) and the answer keys. Held-out cases are used only to MEASURE, never to choose
a rule: rules are written from the failure patterns, and a fresh held-out set is run once at the end.
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from amber import docs, submittal  # noqa: E402
from amber.llm import Meter  # noqa: E402
from amber.ocr import reader_from_env  # noqa: E402
from amber.schema import RunInfo, ToolResult  # noqa: E402

KEYS, EXAMPLES = ROOT / "eval" / "answer_keys", ROOT / "examples"
SCHEDULE = ROOT / "data" / "schedules" / "equipment_schedule.csv"


class _NoModel:
    model = "none"  # a replay must never need one: requirements come from the committed cache


def cases() -> list[str]:
    out = []
    for f in sorted(KEYS.glob("*.json")):
        if re.fullmatch(r"[GU]\d+\.json", f.name) and (EXAMPLES / f.name).exists():
            out.append(f.stem)
    return out


def offers_from_run(run: dict) -> dict[str, dict]:
    """What the model reported for each condition, as kept in the saved findings."""
    offers: dict[str, dict] = {}
    for f in run["findings"]:
        for d in (f.get("data") or {}).get("conditions", []):
            o, cid = d.get("offered") or {}, d["cid"]
            if str(d.get("why", "")).startswith("not checked ("):
                offers[cid] = {"cid": cid, "not_checked": d["why"]}
                continue
            offers[cid] = {"cid": cid, "stated": bool(o.get("quote") or o.get("values")), "values": o.get("values") or [],
                           "unit": o.get("unit"), "selected": o.get("selected"), "quote": o.get("quote"),
                           "page": o.get("page"), "meets": o.get("meets")}
    return offers


def replay(case_id: str):
    case = json.loads((KEYS / f"{case_id}.json").read_text(encoding="utf-8"))
    run = json.loads((EXAMPLES / f"{case_id}.json").read_text(encoding="utf-8"))
    checklist = json.loads((KEYS / case.get("checklist", "genset_requirements.json")).read_text(encoding="utf-8"))["requirements"]
    reader = reader_from_env(meter=Meter())
    spec_doc, sub_doc = docs.load(ROOT / case["spec"], ocr=reader), docs.load(ROOT / case["submittal"], ocr=reader)
    row = submittal.load_schedule(str(SCHEDULE), case["tag"])
    reqs = submittal.structure_requirements(_NoModel(), spec_doc, row, docs.doc_id_for(SCHEDULE), checklist)
    offers = offers_from_run(run)
    submittal._flag_shared_evidence(reqs, offers)
    findings, _ = submittal.decide_all(reqs, offers, sub_doc)
    res = ToolResult(tool="check_submittal", findings=findings, result={}, run=RunInfo(models=[], latency_ms=0)).finalize()
    return case, run, res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", help="comma-separated, default all saved cases")
    ap.add_argument("--out", help="store the verdicts here")
    ap.add_argument("--vs", help="compare with verdicts stored earlier")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    ids = a.cases.split(",") if a.cases else cases()
    before = json.loads(Path(a.vs).read_text(encoding="utf-8")) if a.vs else None
    stored, T = {}, Counter()
    print(f"{'case':5} {'split':8} {'correct':>9} {'false+':>6} {'false-':>6} {'auto ok':>8} {'handoff':>8} {'= saved':>8}")
    for cid in ids:
        case, run, res = replay(cid)
        labels = {l["req_id"]: l["expected"] for l in case["labels"]}
        saved = {f["data"]["req_id"]: f for f in run["findings"] if "req_id" in (f.get("data") or {})}
        stored[cid] = {}
        n = ok = fa = fr = auto = auto_ok = hand = same = 0
        for f in res.findings:
            rid = f.data["req_id"]
            L = labels.get(rid)
            stored[cid][rid] = [f.status.value, round(f.confidence, 3), f.needs_human]
            if L is None:
                continue
            n += 1; ok += f.status.value == L
            fa += f.status.value == "complies" and L in ("deviates", "missing")
            fr += f.status.value == "deviates" and L == "complies"
            hand += f.needs_human
            if not f.needs_human:
                auto += 1; auto_ok += f.status.value == L
            s = saved.get(rid)
            same += bool(s) and s["status"] == f.status.value and s["needs_human"] == f.needs_human
            if before and cid in before and rid in before[cid] and before[cid][rid][0] != f.status.value:
                o = before[cid][rid]
                mark = "IMPROVED" if f.status.value == L else ("REGRESSED" if o[0] == L else "changed (both wrong)")
                print(f"    {cid} {rid:4} label={L:9} {o[0]:9} -> {f.status.value:9} {mark}  [{f.why[:100]}]")
        print(f"{cid:5} {case['split']:8} {ok:>4}/{n:<4} {fa:>6} {fr:>6} {auto_ok:>3}/{auto:<4} {hand / n:>7.0%} {same:>4}/{n:<3}")
        for k, v in (("n", n), ("ok", ok), ("fa", fa), ("fr", fr), ("auto", auto), ("auto_ok", auto_ok), ("hand", hand), ("same", same)):
            T[k] += v
    print(f"{'ALL':5} {'':8} {T['ok']:>4}/{T['n']:<4} {T['fa']:>6} {T['fr']:>6} {T['auto_ok']:>3}/{T['auto']:<4} {T['hand'] / T['n']:>7.0%} {T['same']:>4}/{T['n']:<3}")
    if a.out:
        Path(a.out).write_text(json.dumps(stored), encoding="utf-8")


if __name__ == "__main__":
    main()
