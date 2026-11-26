"""The case file: routing, record linking, reconciliation across a supplier's documents, pre-qualification, the
supplier-reply loop and resuming after an interruption. No model calls: every reading used here is saved."""
import json
from datetime import date
from pathlib import Path

import pytest

from amber import case as C
from amber import docs, linking, triage, vendors
from amber.schema import Citation
from amber.verify import listed_as_choice, under_optional_heading, verify

ROOT = Path(__file__).resolve().parents[1]
SUB = ROOT / "data" / "submittals"
HAVE_DATASHEETS = all((SUB / f).exists() for f in ("cat_3516C_2000ekW_LEHE1376.pdf", "cummins_DQKAB_submittal_CSDG.pdf",
                                                   "kohler_KD2000_G5-626.pdf", "cummins_C2000D6E_spec_sheet.pdf"))
needs_datasheets = pytest.mark.skipif(not HAVE_DATASHEETS, reason="third-party datasheets not downloaded (fetch_data.py)")


def _f(status, needs_human, whys, conds_verdicts=None):
    conds = [{"cid": f"X{i}", "verdict": (conds_verdicts or [status] * len(whys))[i], "why": w} for i, w in enumerate(whys)]
    return {"status": status, "needs_human": needs_human, "why": "; ".join(whys), "data": {"conditions": conds}}


# ------------------------------------------------------------------ triage

def test_an_item_the_document_does_not_establish_goes_to_the_supplier_only_when_read_twice():
    f = _f("unclear", True, ["no value found, but the submittal mentions heater on page(s) [4]"])
    assert triage.route(f, "unclear")["route"] == "ask_supplier"
    assert triage.route(f, "missing")["route"] == "ask_supplier"
    assert triage.route(f, None)["route"] == "engineer"          # not read a second time: a person checks first
    assert triage.route(f, "complies")["route"] == "engineer"    # the second reading found a value: contested


def test_judged_evidence_never_goes_to_the_supplier_or_stands_alone():
    judged = _f("complies", True, ["model judgement on verified quote: 'UL 2200 listed'"])
    assert triage.route(judged, "complies")["route"] == "engineer"
    mixed = _f("unclear", True, ["no value found, but the submittal mentions tank", "model reading (complies) and code check (deviates) disagree"],
               ["unclear", "unclear"])
    assert triage.route(mixed, "unclear")["route"] == "engineer"


def test_decided_answers_stay_decided_and_a_stated_absence_is_a_question():
    assert triage.route(_f("complies", False, ["offered 2000 kW meets >= 2000 kW"]))["route"] == "decide"
    assert triage.route(_f("missing", False, ["not stated in the submittal"]))["route"] == "ask_supplier"


def test_bid_cells_silent_or_qualified_become_clarification_requests():
    assert triage.route_bid_cell({"data": {"scope_status": "silent"}, "needs_human": False})["route"] == "ask_supplier"
    assert triage.route_bid_cell({"data": {"scope_status": "qualified"}, "needs_human": True})["route"] == "ask_supplier"
    assert triage.route_bid_cell({"data": {"scope_status": "excluded"}, "needs_human": False})["route"] == "decide"


# ------------------------------------------------------------------ document structure in a supplier's own documents

def test_a_row_under_an_options_heading_is_not_what_the_bid_supplies():
    bid = docs.load(ROOT / "data/bids/B3_keystone_energy.pdf")
    bid.commitment = True
    c = verify(bid, "UL 2085 sub-base fuel tank, 24 hr runtime at full load")
    assert c and under_optional_heading(bid, c) and listed_as_choice(bid, c)
    base = docs.load(ROOT / "data/bids/B1_northline_power.pdf")
    base.commitment = True
    c1 = verify(base, "4 x UL 2085 dual-wall sub-base tanks sized for 24 hrs at 100% standby load")
    assert c1 and not under_optional_heading(base, c1)
    alt = verify(base, "Extend standard 2-year warranty to 5-year comprehensive")
    assert alt and under_optional_heading(base, alt)


def test_headings_are_not_used_on_a_datasheet_page_where_text_runs_across_columns():
    d = docs.Document(doc_id="ds", path="x", pages=[docs.Page(number=1, text="Optional\nInsulation system Class H\n",
                                                             raw="Optional\nInsulation system Class H\n")])
    c = Citation(doc_id="ds", page=1, quote="Insulation system Class H", match="exact")
    assert not listed_as_choice(d, c)          # a datasheet: 'Optional' may be a column header
    d.commitment = True
    assert listed_as_choice(d, c)              # a bid or reply: the heading governs the row


# ------------------------------------------------------------------ record linking

@needs_datasheets
def test_product_links_report_ambiguity_instead_of_picking():
    pkg = json.loads((ROOT / "examples/package_GEN.json").read_text(encoding="utf-8"))["result"]["parts"]["level_bids"]
    res = linking.link_products(pkg["products"], sorted(str(p) for p in SUB.glob("*.pdf")))
    assert res["B1"]["status"] == "linked" and res["B1"]["datasheet"] == "cat_3516C_2000ekW_LEHE1376.pdf"
    assert res["B2"]["datasheet"] == "cummins_DQKAB_submittal_CSDG.pdf"
    assert res["B3"]["datasheet"] == "kohler_KD2000_G5-626.pdf"          # not the KD1000 package that mentions KD2000
    assert res["B4"]["status"] == "ambiguous" and res["B4"]["route"] == "ask_supplier"
    kinds = {c["file"]: c["kind"] for c in res["B4"]["candidates"]}
    assert kinds == {"cummins_DQKAB_submittal_CSDG.pdf": "alias", "cummins_C2000D6E_spec_sheet.pdf": "variant"}


def test_scope_items_link_to_requirements_and_a_wrong_reference_is_reported():
    pkg = json.loads((ROOT / "examples/package_GEN.json").read_text(encoding="utf-8"))["result"]["parts"]["level_bids"]
    form = docs.load(ROOT / "data/bids/00_bid_form_generators.pdf")
    ck = json.loads((ROOT / "eval/answer_keys/genset_requirements.json").read_text(encoding="utf-8"))["requirements"]
    sl = linking.link_scope_to_requirements(pkg["scope"], "\n".join(p.text for p in form.pages), ck)
    assert {(l["scope_id"], l["req_id"]) for l in sl["links"]} == {("S2", "R21"), ("S3", "R19")}
    assert [(c["scope_id"], c["req_id"]) for c in sl["conflicts"]] == [("S4", "R19")]


# ------------------------------------------------------------------ pre-qualification (saved readings, no model)

def test_prequalification_replays_from_saved_readings():
    dirs = {r["vendor_id"]: r for r in vendors.load_directory()}
    need, as_of = date(2027, 10, 4), date(2026, 11, 26)
    tgc = vendors.prequalify({"vendor_id": "V-TGC", "name": "Tidewater"}, vendors.packet_for("V-TGC"), need, as_of,
                             llm=None, live=False, dir_row=dirs["V-TGC"])
    assert tgc["overall"] == "needs verification" and tgc["to_verify"] == ["Q2", "Q4", "Q5"]
    assert "Norfolk" in tgc["criteria"]["Q5"]["why"]                  # conflicting records named, not hidden
    assert tgc["criteria"]["Q7"]["route"] == "engineer"               # a self-certification is not verification
    kee = vendors.prequalify({"vendor_id": "V-KEE", "name": "Keystone"}, vendors.packet_for("V-KEE"), need, as_of,
                             llm=None, live=False, dir_row=dirs["V-KEE"])
    assert kee["fails"] == ["Q3"]
    key = json.loads((ROOT / "eval/answer_keys/prequal_GEN.json").read_text(encoding="utf-8"))["vendors"]
    for vid, res in (("V-TGC", tgc), ("V-KEE", kee)):
        assert {k: v["status"] for k, v in res["criteria"].items()} == {k: v["expected"] for k, v in key[vid].items()}


def test_no_packet_means_every_criterion_needs_verification():
    r = vendors.prequalify({"vendor_id": "V-RWP", "name": "Ridgeway"}, [], date(2027, 10, 4), date(2026, 11, 26),
                           llm=None, live=False, manufacturer_hint={"name": "Cummins C2000D6", "citation": None})
    assert r["criteria"]["P1"]["status"] == "meets"
    assert all(v["status"] == "needs_verification" for k, v in r["criteria"].items() if k != "P1")


# ------------------------------------------------------------------ the case file

@pytest.fixture(scope="module")
def case_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("cases")


@needs_datasheets
def test_a_case_interrupted_inside_a_step_resumes_there(case_dir):
    with pytest.raises(C.Interrupted):
        C.run_case("GEN", root=case_dir, fresh=True, crash_at="reconcile")
    cf = C.CaseFile("GEN", C.CASES["GEN"], root=case_dir)
    assert cf.state["steps"]["reconcile"]["status"] == "running"
    assert all(cf.state["steps"][s]["status"] == "done" for s in C.STEPS[:C.STEPS.index("reconcile")])
    cf = C.run_case("GEN", root=case_dir)
    st = cf.state["steps"]
    assert st["reconcile"]["status"] == "done" and st["reconcile"]["attempts"] == 2
    assert st["requirements"]["attempts"] == 1                          # earlier steps were reused, not run again
    assert st["replies"]["status"] == "waiting"
    events = [json.loads(l)["event"] for l in (case_dir / "GEN" / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
    assert "interrupted" in events and "reused" in events


@needs_datasheets
def test_the_supplier_package_settles_what_the_datasheet_leaves_open(case_dir):
    cf = C.run_case("GEN", root=case_dir)
    rec = cf.output("reconcile")
    f = lambda b, r: next(x for x in rec[b]["findings"] if x["data"]["req_id"] == r)
    assert (f("B1", "R12")["status"], f("B1", "R12")["route"]["route"]) == ("complies", "decide")   # datasheet: no rpm
    assert (f("B2", "R19")["status"], f("B2", "R19")["route"]["route"]) == ("deviates", "decide")   # 12-hour tank
    r09 = f("B3", "R09")
    assert r09["status"] == "deviates" and r09["route"]["kind"] == "conditional rating"
    assert "113" in r09["why"] and r09["route"]["route"] == "engineer"
    assert f("B3", "R19")["status"] == "unclear"                       # the UL 2085 tank is only an option


@needs_datasheets
def test_replies_flow_back_into_answers_prequalification_and_cost(case_dir):
    cf = C.run_case("GEN", root=case_dir, replies=True)
    rec, pq, rg = cf.output("reconcile"), cf.output("prequalify"), cf.output("ranges")
    f = lambda b, r: next(x for x in rec[b]["findings"] if x["data"]["req_id"] == r)
    assert f("B2", "R19")["status"] == "complies"                      # the reply replaces the 12-hour tank
    assert f("B1", "R20")["status"] == "deviates"                      # the reply reveals one 9 kW heater
    assert f("B1", "R09")["status"] == "unclear"                       # 'will be confirmed later' settles nothing
    assert pq["B2"]["overall"] == "qualified pending the owner's checks"
    assert rg["cost"]["B2"]["adjustments"].get("S3") == 72000          # $18,000 x 4 sets replaces the allowance
    assert "S2" not in rg["cost"]["B2"]["adjustments"]
    dec = cf.output("decision")
    assert dec["auto_award"] is False and dec["escalate_schedule"] is True
