"""Product discovery for one equipment tag over the datasheet library, with a readable summary.

usage: python scripts/run_discovery.py GEN-A [--provider groq|ollama]
Screens are cached per datasheet (.cache/discovery/), so a second run only screens what is new or failed.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from amber.discovery import find_products  # noqa: E402
from amber.llm import LLM  # noqa: E402
from amber.submittal import load_schedule  # noqa: E402

D = ROOT / "data"
SPECS = {"26 32 13": ("specs/project_alpha/26_32_13_engine_generators_ALPHA.pdf", "genset_requirements.json"),
         "26 33 53": ("specs/project_alpha/26_33_53_static_ups_ALPHA.pdf", "ups_requirements.json")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("tag")
    ap.add_argument("--provider")
    a = ap.parse_args()
    schedule = D / "schedules/equipment_schedule.csv"
    spec, checklist = SPECS[load_schedule(schedule, a.tag)["spec_section"]]
    reqs = json.loads((ROOT / "eval/answer_keys" / checklist).read_text(encoding="utf-8"))["requirements"]
    library = sorted(str(p) for p in (D / "submittals").glob("*") if p.suffix.lower() in (".pdf", ".txt"))
    res = find_products(str(D / spec), a.tag, str(schedule), library, reqs, llm=LLM(provider=a.provider))
    (ROOT / "runs").mkdir(exist_ok=True)
    (ROOT / f"runs/discovery_{a.tag}.json").write_text(res.model_dump_json(indent=2), encoding="utf-8")
    ids = res.result["screen"]
    print(f"{'product':48} {'verdict':20} " + " ".join(f"{r:>9}" for r in ids))
    for f in res.findings:
        by = {s["req_id"]: s["status"] for s in f.data["screen"]}
        print(f"{f.data['product'][:48]:48} {f.data['verdict']:20} " + " ".join(f"{by.get(r, '-'):>9}" for r in ids))
    for s in res.result["skipped"]:
        print(f"skipped {s['product']}: {s['reason']}")
    failed = sum(1 for s in res.run.steps if s.get("ok") is False)
    print(f"cost ${res.run.cost_usd} · {res.run.latency_ms // 1000}s · model calls {len(res.run.steps)} (failed {failed})")


if __name__ == "__main__":
    main()
