"""Structure a spec's requirements once (with a capable model) and cache them for every later submittal check,
including offline runs on a small local model that could not do this step itself.

usage: python scripts/build_requirements.py G2 [--provider gemini|groq]
Writes data/requirements/<hash>.json (committed: derived only from the spec, contains no submittal facts).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from amber import docs  # noqa: E402
from amber.llm import LLM  # noqa: E402
from amber.submittal import _req_cache_file, load_schedule, structure_requirements  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("case")
ap.add_argument("--provider")
a = ap.parse_args()
case = json.loads((ROOT / f"eval/answer_keys/{a.case}.json").read_text(encoding="utf-8"))
checklist = json.loads((ROOT / "eval/answer_keys" / case.get("checklist", "genset_requirements.json")).read_text(encoding="utf-8"))["requirements"]
sched = ROOT / "data/schedules/equipment_schedule.csv"
spec_doc = docs.load(str(ROOT / case["spec"]))
row = load_schedule(str(sched), case["tag"])
cf = _req_cache_file(spec_doc, row, checklist)
if cf.exists():
    print("already cached:", cf.name)
    sys.exit(0)
reqs = structure_requirements(LLM(provider=a.provider), spec_doc, row, docs.doc_id_for(str(sched)), checklist)
print(("cached " + cf.name) if cf.exists() else "NOT cached (structuring incomplete)", "|", len(reqs), "requirements,",
      sum(len(r.get("conditions", [])) for r in reqs), "conditions")
