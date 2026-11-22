"""Benchmark a model on a fixed slice of dev case G2: time and verdict agreement with the answer key.

Uses the cached requirement structuring (data/requirements), so only the submittal-reading step runs, which is
exactly what offline mode does. Nothing is sent anywhere when --provider ollama.

usage: python scripts/bench_local.py --provider ollama --model qwen3:4b [--ctx 4096]
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SLICE = ["R01", "R04", "R05", "R08", "R10", "R12", "R17", "R18", "R19"]  # 7 complies, 1 missing, 1 deviates in the key


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="ollama")
    ap.add_argument("--model")
    ap.add_argument("--ctx")
    ap.add_argument("--why", action="store_true")
    a = ap.parse_args()
    if a.ctx:
        os.environ["AMBER_OLLAMA_CTX"] = a.ctx
    from amber import docs
    from amber.llm import LLM
    from amber.submittal import _combine, _decide_condition, _flag_shared_evidence, _req_cache_file, extract_offers, load_schedule

    case = json.loads((ROOT / "eval/answer_keys/G2.json").read_text(encoding="utf-8"))
    checklist = json.loads((ROOT / "eval/answer_keys/genset_requirements.json").read_text(encoding="utf-8"))["requirements"]
    spec_doc = docs.load(str(ROOT / case["spec"]))
    row = load_schedule(str(ROOT / "data/schedules/equipment_schedule.csv"), case["tag"])
    reqs = json.loads(_req_cache_file(spec_doc, row, checklist).read_text(encoding="utf-8"))["requirements"]
    reqs = [r for r in reqs if r["req_id"] in SLICE]
    sub = docs.load(str(ROOT / case["submittal"]))
    key = {l["req_id"]: l["expected"] for l in case["labels"]}

    llm = LLM(provider=a.provider, model=a.model)
    t0 = time.time()
    offers = extract_offers(llm, sub, reqs)
    _flag_shared_evidence(reqs, offers)
    secs = time.time() - t0
    ok, rows = 0, []
    for r in reqs:
        parts = [_decide_condition(c, offers.get(c["cid"]), sub) for c in r["conditions"]]
        v = _combine(parts)[0].value if parts else "unclear"
        ok += v == key[r["req_id"]]
        rows.append(f"{r['req_id']} key={key[r['req_id']]:8} got={v:8} {'ok' if v == key[r['req_id']] else 'XX'}")
        if v != key[r["req_id"]] and "--why" in sys.argv:
            for c, (d, cite, conf) in zip(r["conditions"], parts):
                o = offers.get(c["cid"]) or {}
                rows.append(f"     {c['cid']} {c.get('attribute')}: {d.verdict.value} | {d.why[:110]} | model said stated={o.get('stated')} values={o.get('values')} quote={str(o.get('quote'))[:60]!r}")
    u = llm.meter.models()[0]
    print("\n".join(rows))
    print(f"\nmodel={u.name} ctx={os.getenv('AMBER_OLLAMA_CTX', '-')} calls={u.calls} tokens_in={u.tokens_in} "
          f"tokens_out={u.tokens_out} seconds={secs:.0f} per_call={secs / max(1, u.calls):.0f} correct={ok}/{len(reqs)}")


if __name__ == "__main__":
    main()
