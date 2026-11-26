"""Read a supplier's own commercial documents (a bid, a reply to our questions) against the spec's requirements.

The same verified check as a datasheet (model reads, code decides, every quote found on its page), pointed at a
different document: what the supplier COMMITS to in writing. The package case file (amber/case.py) reconciles it with
the datasheet. Saved runs go to examples/commitments/ so the case file can be replayed with no model call.

usage: python scripts/read_commitments.py B1 B2 B3 B4            read the four bids, all requirements
       python scripts/read_commitments.py --doc data/replies/B1_northline_reply.txt --name B1_reply --only R03,R04
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from amber.llm import LLM  # noqa: E402
from amber.submittal import check_submittal  # noqa: E402

OUT = ROOT / "examples" / "commitments"
SPEC = ROOT / "data/specs/project_alpha/26_32_13_engine_generators_ALPHA.pdf"
SCHEDULE = ROOT / "data/schedules/equipment_schedule.csv"
CHECKLIST = ROOT / "eval/answer_keys/genset_requirements.json"


def read(doc: Path, name: str, only: list[str] | None = None, llm: LLM | None = None) -> dict:
    checklist = json.loads(CHECKLIST.read_text(encoding="utf-8"))["requirements"]
    res = check_submittal(str(SPEC), str(doc), "GEN-A", str(SCHEDULE), checklist=checklist, llm=llm or LLM(), only=only,
                          commitment=True)
    OUT.mkdir(parents=True, exist_ok=True)
    data = json.loads(res.model_dump_json())
    data["source_document"] = doc.relative_to(ROOT).as_posix()
    (OUT / f"{name}.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    return data


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("bids", nargs="*")
    ap.add_argument("--doc")
    ap.add_argument("--name")
    ap.add_argument("--only")
    a = ap.parse_args()
    key = json.loads((ROOT / "eval/answer_keys/package_GEN.json").read_text(encoding="utf-8"))
    jobs = [(ROOT / key["bidders"][b]["bid"], f"{b}_bid", None) for b in a.bids]
    if a.doc:
        jobs.append((ROOT / a.doc, a.name, a.only.split(",") if a.only else None))
    total = []
    for doc, name, only in jobs:
        llm = LLM()  # one meter per document, so each saved run reports its own calls and tokens
        d = read(doc, name, only, llm)
        total += llm.meter.models()
        print(name, d["result"]["summary"], "steps:", [(s["purpose"][:30], s["ok"]) for s in d["run"]["steps"]])
    print("tokens:", [m.model_dump() for m in total])


if __name__ == "__main__":
    main()
