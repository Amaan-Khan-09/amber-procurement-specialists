"""Run level_bids on the generator bid package and score it against eval/answer_keys/bids_genset.json.

usage: python scripts/eval_bids.py [--provider groq|gemini|ollama] [--reuse]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from amber.bids import level_bids  # noqa: E402
from amber.llm import LLM  # noqa: E402

KEY = json.loads((ROOT / "eval/answer_keys/bids_genset.json").read_text(encoding="utf-8"))
OUT = ROOT / "runs/BL1.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider")
    ap.add_argument("--reuse", action="store_true")
    a = ap.parse_args()
    if a.reuse and OUT.exists():
        res = json.loads(OUT.read_text(encoding="utf-8"))
    else:
        r = level_bids(str(ROOT / KEY["bid_form"]), {k: str(ROOT / v) for k, v in KEY["bids"].items()},
                       llm=LLM(provider=a.provider))
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(r.model_dump_json(indent=2), encoding="utf-8")
        res = json.loads(r.model_dump_json())
    R = res["result"]

    cells = ok = 0
    wrong = []
    for sid, row in KEY["matrix"].items():
        for b, want in row.items():
            got = R["matrix"].get(b, {}).get(sid, "?")
            cells += 1
            if got == want:
                ok += 1
            else:
                wrong.append(f"{b}.{sid}: key={want} agent={got}")
    print(f"scope matrix: {ok}/{cells} cells correct ({ok / cells:.0%})")
    for w in wrong:
        print("   ", w)
    print("\nbid   base(agent/key)          adjusted(agent/key)")
    for b in KEY["base_bid"]:
        lv = R["leveling"][b]
        print(f"{b}   {lv['base']:>12,.0f} / {KEY['base_bid'][b]:<12,}  {lv['adjusted']:>12,.0f} / {KEY['adjusted_total'][b]:,}"
              f"  {'OK' if abs(lv['adjusted'] - KEY['adjusted_total'][b]) < 1 else 'DIFF'}")
    aw = R["award"]
    print("\nranking agent:", aw["ranked"], " key:", KEY["rank_by_adjusted"])
    print("auto_award:", aw["auto_award"], "(key: False)")
    print("why:", aw["why"][:300])
    print("products:", R["products"])
    fab = [f for f in res["findings"] for c in f["citations"] if c.get("match") is None]
    print("\nfindings:", len(res["findings"]), " to a person:", len(res["needs_human"]),
          " cost $", round(sum(m["cost_usd"] for m in res["run"]["models"]), 5), " time", res["run"]["latency_ms"] // 1000, "s")


if __name__ == "__main__":
    main()
