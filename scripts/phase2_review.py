"""Reproducible live check of one spec/supplier pair; never reads an answer key.

Example: python scripts/phase2_review.py data/specs/x.pdf data/submittals/y.pdf --out runs/phase2/x.json
For an unfamiliar project omit --schedule; Project Alpha runs supply --schedule and --tag.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from amber.llm import LLM  # noqa: E402
from amber.submittal import check_submittal  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("supplier")
    ap.add_argument("--tag", default="User project")
    ap.add_argument("--schedule")
    ap.add_argument("--checklist")
    ap.add_argument("--provider", default="groq")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    checklist = json.loads((ROOT / a.checklist).read_text(encoding="utf-8"))["requirements"] if a.checklist else None
    os.environ["AMBER_RESULT_CACHE"] = "off"
    res = check_submittal(str(ROOT / a.spec), str(ROOT / a.supplier), a.tag,
                          str(ROOT / a.schedule) if a.schedule else None,
                          checklist=checklist, llm=LLM(provider=a.provider))
    dest = ROOT / a.out
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(res.model_dump_json(indent=2), encoding="utf-8")
    print(json.dumps({"out": a.out, "coverage": res.result["coverage"], "summary": res.result["summary"],
                      "overall": res.result["overall"], "models": [m.model_dump() for m in res.run.models],
                      "latency_ms": res.run.latency_ms}, indent=2))


if __name__ == "__main__":
    main()
