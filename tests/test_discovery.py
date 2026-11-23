"""Product discovery: candidates only from datasheets we hold, screened with the verified check, never an approval."""
from pathlib import Path

import pytest

from amber import discovery
from amber.schema import Citation, Finding, RunInfo, ToolResult, Verdict

ROOT = Path(__file__).resolve().parents[1]
SCHEDULE = str(ROOT / "data/schedules/equipment_schedule.csv")
CHECKLIST = [{"req_id": r} for r in discovery.SCREEN["26 32 13"]]

# what the screen "finds" in each fake datasheet
OUTCOMES = {
    "fits-2000kw": {r: "complies" for r in discovery.SCREEN["26 32 13"]},
    "small-1000kw": {**{r: "complies" for r in discovery.SCREEN["26 32 13"]}, "R01": "deviates"},
    "vague-sheet": {**{r: "complies" for r in discovery.SCREEN["26 32 13"]}, "R10": "unclear"},
}


@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setattr(discovery, "CACHE", tmp_path / "cache")
    files = {
        "fits-2000kw": "Diesel generator set, 2000 kW standby, 480 V, 60 Hz, 1800 rpm, EPA Tier 2.",
        "small-1000kw": "Diesel generator set, 1000 kW standby, 480 V, 60 Hz.",
        "vague-sheet": "Generator set family brochure. Ratings vary by model.",
        "ups-brochure": "Uninterruptible power supply, 1200 kVA double conversion. UPS module.",
    }
    paths = []
    for name, text in files.items():
        f = tmp_path / f"{name}.txt"
        f.write_text(text, encoding="utf-8")
        paths.append(str(f))
    spec = tmp_path / "spec.txt"
    spec.write_text("Section 26 32 13 engine generators", encoding="utf-8")
    calls = []

    def fake_check(spec_path, path, tag, schedule_path, checklist=None, llm=None, only=None):
        name = Path(path).stem
        calls.append(name)
        fs = [Finding(id=f"F-{r}", claim=f"requirement {r}", status=Verdict(OUTCOMES[name][r]), confidence=0.9,
                      citations=[Citation(doc_id="spec", page=1, quote="spec words"),
                                 Citation(doc_id=name, page=2, quote=f"{name} quote for {r}")],
                      why="checked", data={"req_id": r}) for r in only]
        return ToolResult(tool="check_submittal", findings=fs, result={}, run=RunInfo(models=[], latency_ms=1)).finalize()

    monkeypatch.setattr(discovery, "check_submittal", fake_check)
    return {"paths": paths, "spec": str(spec), "calls": calls}


class _NoModel:
    provider = "test"

    def __init__(self):
        from amber.llm import Meter
        self.meter = Meter()


def test_ranks_fitting_products_first_and_skips_other_equipment(library):
    res = discovery.find_products(library["spec"], "GEN-A", SCHEDULE, library["paths"], CHECKLIST, llm=_NoModel())
    order = [(f.data["product"], f.data["verdict"]) for f in res.findings]
    assert order == [("fits-2000kw", "likely fits"), ("vague-sheet", "needs a closer look"), ("small-1000kw", "does not fit")]
    assert res.result["skipped"][0]["product"] == "ups-brochure"
    assert "ups-brochure" not in library["calls"]  # the wrong kind of equipment is never screened


def test_a_screen_is_never_an_approval_and_cites_only_the_product_itself(library):
    res = discovery.find_products(library["spec"], "GEN-A", SCHEDULE, library["paths"], CHECKLIST, llm=_NoModel())
    for f in res.findings:
        assert f.needs_human and f.confidence <= discovery.SCREEN_CAP
        assert f.citations and all(c.doc_id == f.data["product"] for c in f.citations)
    named = {c["product"] for c in res.result["candidates"]}
    assert named <= {Path(p).stem for p in library["paths"]}  # nothing named that is not in the library


def test_screens_are_cached(library):
    discovery.find_products(library["spec"], "GEN-A", SCHEDULE, library["paths"], CHECKLIST, llm=_NoModel())
    first = len(library["calls"])
    again = discovery.find_products(library["spec"], "GEN-A", SCHEDULE, library["paths"], CHECKLIST, llm=_NoModel())
    assert len(library["calls"]) == first and all(f.data["cached"] for f in again.findings)


def test_refuses_equipment_without_screening_ratings(library):
    with pytest.raises(ValueError):
        discovery.find_products(library["spec"], "SWGR-A", SCHEDULE, library["paths"], CHECKLIST, llm=_NoModel())
