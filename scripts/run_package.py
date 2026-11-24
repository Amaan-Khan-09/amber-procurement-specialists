"""Full package review for the Project Alpha generators (bids + submittals + delivery) and a readable summary.

usage: python scripts/run_package.py [--provider groq|gemini]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from amber.llm import LLM  # noqa: E402
from amber.package import run_package_review  # noqa: E402

D = ROOT / "data"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider")
    a = ap.parse_args()
    checklist = json.loads((ROOT / "eval/answer_keys/genset_requirements.json").read_text(encoding="utf-8"))["requirements"]
    res = run_package_review(
        bid_form=str(D / "bids/00_bid_form_generators.pdf"),
        bids={"B1": str(D / "bids/B1_northline_power.pdf"), "B2": str(D / "bids/B2_tidewater_generator.pdf"),
              "B3": str(D / "bids/B3_keystone_energy.pdf"), "B4": str(D / "bids/B4_ridgeway_power_email.txt")},
        submittals={"B1": str(D / "submittals/cat_3516C_2000ekW_LEHE1376.pdf"),
                    "B2": str(D / "submittals/cummins_DQKAB_submittal_CSDG.pdf"),
                    "B3": str(D / "submittals/kohler_KD2000_G5-626.pdf"),
                    "B4": str(D / "submittals/cummins_C2000D6E_spec_sheet.pdf")},
        spec=str(D / "specs/project_alpha/26_32_13_engine_generators_ALPHA.pdf"), tag="GEN-A", tag_group="GEN",
        schedule=str(D / "schedules/equipment_schedule.csv"), po_status=str(D / "schedules/po_status.csv"),
        evidence=str(D / "leadtime_sources/leadtime_evidence.csv"), as_of="2026-12-01",
        checklist=checklist, llm=LLM(provider=a.provider))
    (ROOT / "runs").mkdir(exist_ok=True)
    (ROOT / "runs/package_GEN.json").write_text(res.model_dump_json(indent=2), encoding="utf-8")
    print(f"{'bid':4} {'product':40} {'leveled':>12} {'gaps':>4} {'submittal':12} {'P50 arrival':12} {'P(late)':>7}")
    for r in res.result["comparison"]:
        print(f"{r['bid']:4} {str(r['product'])[:40]:40} {r['leveled_cost'] or 0:>12,.0f} {len(r['scope_gaps']):>4} "
              f"{r['submittal']:12} {str(r['arrival_P50']):12} {r['p_late'] if r['p_late'] is not None else '-':>7}")
    d = res.result["decision"]
    print("\nauto_award:", d["auto_award"], "| recommend:", d["recommend"])
    for n in d["notes"]:
        print(" -", n)
    print("\nfindings:", len(res.findings), "| to a person:", len(res.needs_human),
          "| cost $", res.run.cost_usd, "| time", res.run.latency_ms // 1000, "s")


if __name__ == "__main__":
    main()
