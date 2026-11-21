"""Run check_submittal on one answer-key case and print a readable table.

usage: python scripts/run_check.py G2 [--provider groq|gemini|ollama] [--out runs/]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from amber.llm import LLM  # noqa: E402
from amber.submittal import check_submittal  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("--provider")
    ap.add_argument("--out", default="runs")
    a = ap.parse_args()
    case = json.loads((ROOT / f"eval/answer_keys/{a.case}.json").read_text(encoding="utf-8"))
    checklist = json.loads((ROOT / "eval/answer_keys/genset_requirements.json").read_text(encoding="utf-8"))["requirements"]
    res = check_submittal(str(ROOT / case["spec"]), str(ROOT / case["submittal"]), case["tag"],
                          str(ROOT / "data/schedules/equipment_schedule.csv"), checklist=checklist,
                          llm=LLM(provider=a.provider))
    out = ROOT / a.out
    out.mkdir(exist_ok=True)
    (out / f"{a.case}.json").write_text(res.model_dump_json(indent=2), encoding="utf-8")
    for f in res.findings:
        sub = next((c for c in f.citations if not c.doc_id.startswith("26-32-13")), None)
        print(f"{f.data['req_id']:4} {f.status.value:9} {f.confidence:.2f} {'HUMAN ' if f.needs_human else '      '}"
              f"{f.claim[:55]:55} | {f.why[:70]}" + (f" | p{sub.page}" if sub else ""))
    print("summary:", res.result["summary"], "overall:", res.result["overall"])
    print("run:", [m.model_dump() for m in res.run.models], f"cost ${res.run.cost_usd}", f"{res.run.latency_ms} ms")


if __name__ == "__main__":
    main()
