"""The second look at the clause (amber/inspect_evidence.py): option selections, conditional limits, numbers read
from the quote itself, and the one-missing-fact clarification. Includes the 50 C regression from held-out G9."""
import json
from pathlib import Path

import pytest

from amber import docs
from amber import inspect_evidence as I

ROOT = Path(__file__).resolve().parents[1]
COOL = {"cid": "R09b", "attribute": "maximum_ambient_temperature", "kind": "numeric", "op": ">=", "value": 122, "unit": "°F"}


def _doc(*pages: str) -> docs.Document:
    return docs.Document(doc_id="t", path="t", pages=[docs.Page(number=i + 1, text=t, raw=t) for i, t in enumerate(pages)])


def _part(quote: str, why: str = "offered 122 °F meets >= 122 °F") -> dict:
    return {"cid": "R09b", "verdict": "complies", "why": why, "conf": 0.95, "source": "datasheet",
            "cite": {"doc_id": "t", "page": 1, "quote": quote, "match": "exact"}}


def _run(doc, part, cond=COOL):
    reqs = [{"req_id": "R09", "conditions": [cond]}]
    parts = {"R09": [part]}
    log = I.inspect_parts(reqs, parts, doc)
    return parts["R09"][0], log


# ------------------------------------------------------------------ option selections and conditional limits

def test_a_rating_offered_only_as_an_unticked_option_is_not_approved():
    d = _doc("Maximum Operating Ambient Temperature °F (°C) 122 (50)", "CONFIGURABLE OPTIONS\n○50 °C Ambient Cooling System")
    p, _ = _run(d, _part("Maximum Operating Ambient Temperature °F (°C) 122 (50)"))
    assert p["verdict"] == "unclear" and p["kind"] == "depends on an option" and p["option"]["state"] == "unselected"


def test_a_ticked_option_keeps_the_rating():
    d = _doc("Maximum Operating Ambient Temperature °F (°C) 122 (50)", "OPTIONS\n☒ 50 °C Ambient Cooling System")
    p, _ = _run(d, _part("Maximum Operating Ambient Temperature °F (°C) 122 (50)"))
    assert p["verdict"] == "complies"


def test_an_option_listed_as_available_without_a_mark_is_unknown():
    d = _doc("Maximum ambient 122 °F", "Cooling systems available for 50 °C ambient (optional)")
    p, _ = _run(d, _part("Maximum ambient 122 °F"))
    assert p["verdict"] == "unclear" and p["option"]["state"] == "listed"


def test_no_option_anywhere_leaves_a_plain_rating_alone():
    d = _doc("Radiator ambient capability 50 °C (122 °F)", "Standard features: unit mounted radiator")
    p, _ = _run(d, _part("Radiator ambient capability 50 °C (122 °F)"))
    assert p["verdict"] == "complies"


G9 = ROOT / "data" / "submittals" / "generac_MD2000_spec_sheet.pdf"


@pytest.mark.skipif(not G9.exists(), reason="third-party datasheet not downloaded")
def test_regression_g9_r09_the_50c_rating_that_needs_an_unmarked_option():
    """Held-out G9 (run once, 26 Nov): R09 was decided 'complies' on '122 (50)' while the 50 C cooling system is an
    unticked option on page 3. It must now be a question to the supplier, never an approval."""
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import eval_handoffs as E
    from amber import case as C
    k = json.loads((ROOT / "eval/answer_keys/G9.json").read_text(encoding="utf-8"))
    res = C.reconcile_supplier(E._reqs(k), docs.load(G9), C.offers_from_run(json.loads((ROOT / "examples/G9.json").read_text(encoding="utf-8"))),
                               [], [], C.second_readings().get("G9"), C.second_answers().get("G9"))
    f = next(x for x in res["findings"] if x["data"]["req_id"] == "R09")
    assert f["status"] == "unclear" and f["route"]["route"] == "ask_supplier" and f["route"]["kind"] == "clarification"
    assert "50 °C Ambient Cooling System" in f["data"]["question"]


# ------------------------------------------------------------------ computing from the quote

@pytest.mark.parametrize("quote,cond,verdict", [
    ("Voltage regulation, no load to full load ± 0.5%", {"attribute": "voltage_regulation_no_load_to_rated_load", "op": "<=", "value": 2, "unit": "%"}, "complies"),
    ("Total Harmonic Distortion in no-load DHT (%) 2,1", {"attribute": "voltage_thd_no_load_to_full_linear_load", "op": "<=", "value": 5, "unit": "%"}, "complies"),
    ("5% maximum total harmonic distortion", {"attribute": "voltage_thd_no_load_to_full_linear_load", "op": "<=", "value": 5, "unit": "%"}, "complies"),
    ("Fuel consumption | 100% load with fan – L/hr (gal/hr) 505.8 (133.6)", {"attribute": "average_fuel_consumption_full_standby_load", "op": "<=", "value": 145, "unit": "gph"}, "complies"),
    ("Fuel consumption at 100% load 163.4 gph", {"attribute": "average_fuel_consumption_full_standby_load", "op": "<=", "value": 145, "unit": "gph"}, "deviates"),
])
def test_a_number_in_a_verified_quote_is_compared_in_code(quote, cond, verdict):
    got = I.compute_numeric(dict(cond, kind="numeric"), quote)
    assert got and got["verdict"] == verdict


def test_a_quote_about_something_else_or_with_two_values_is_not_computed():
    thd = {"attribute": "voltage_thd_no_load_to_full_linear_load", "kind": "numeric", "op": "<=", "value": 5, "unit": "%"}
    assert I.compute_numeric(thd, "Frequency regulation ±0.25%") is None          # another attribute
    assert I.compute_numeric(thd, "Harmonic distortion 2% at no load, 6% at full load") is None  # ambiguous


def test_one_missing_fact_becomes_a_focused_question_unless_the_document_states_it():
    gov = {"cid": "R06a", "attribute": "governor_type", "kind": "text", "terms": ["electronic", "isochronous"], "match": "all"}
    why = "model judgement on verified quote: 'Governor: Electronic'"
    p, _ = _run(_doc("Governor: Electronic"), dict(_part("Governor: Electronic", why), cid="R06a"), gov)
    assert p["verdict"] == "unclear" and p["kind"] == "one missing fact" and p["missing"] == ["isochronous"]
    p, _ = _run(_doc("Governor: Electronic", "Control: isochronous governor control, 0.25%"), dict(_part("Governor: Electronic", why), cid="R06a"), gov)
    assert p["verdict"] == "complies" and p["kind"] == "computed from the quote"


def test_a_unit_printed_in_the_table_heading_counts_only_for_the_same_attribute():
    fuel = {"attribute": "average_fuel_consumption_full_standby_load", "kind": "numeric", "op": "<=", "value": 145, "unit": "gph"}
    d = _doc("Fuel Consumption\nDiesel, Lph (gph) at % load\nStandby Rating\n100% 528.3 (139.6)")
    assert I.unit_from_heading(d, fuel, "100% 528.3 (139.6)", 1)
    other = _doc("Cooling water\nCoolant flow, Lpm (gpm)\nStandby Rating\n100% 528.3 (139.6)")
    assert I.unit_from_heading(other, fuel, "100% 528.3 (139.6)", 1) is None


def test_internal_mounted_means_inside():
    sil = {"attribute": "silencer_location", "kind": "text", "terms": ["inside"], "match": "all"}
    assert I.compute_text(sil, "internal-mounted, exhaust silencers")["verdict"] == "complies"


def test_cylinder_notation_is_read():
    cyl = {"attribute": "cylinder_count", "kind": "text", "terms": ["8 cylinder", "12 cylinder", "16 cylinder"], "match": "any"}
    assert I.compute_text(cyl, "Cylinder arrangement 16V")["verdict"] == "complies"
    assert I.compute_text(cyl, "Rated voltage 480V") is None


def test_missing_descriptive_words_are_a_question_not_a_rejection():
    enc = {"cid": "R21a", "attribute": "enclosure_type", "kind": "text", "terms": ["weatherproof", "rodent-proof"], "match": "all"}
    part = {"cid": "R21a", "verdict": "deviates", "why": "does not meet all of: weatherproof, rodent-proof", "conf": 0.65, "source": "bid",
            "cite": {"doc_id": "t", "page": 1, "quote": "weather protective enclosure", "match": "exact"}}
    p, _ = _run(_doc("weather protective enclosure"), part, enc)
    assert p["verdict"] == "unclear" and p["kind"] == "one missing fact"
    p, _ = _run(_doc("enclosure not weatherproof"), dict(part, cite=dict(part["cite"], quote="enclosure not weatherproof")), enc)
    assert p["verdict"] == "deviates"                       # the opposite is stated: stays a deviation
    ul = {"cid": "R19a", "attribute": "fuel_tank_listing", "kind": "text", "terms": ["ul 2085"], "match": "all"}
    p, _ = _run(_doc("UL 142 sub-base tank"), dict(part, cid="R19a", cite=dict(part["cite"], quote="UL 142 sub-base tank")), ul)
    assert p["verdict"] == "deviates"                       # a different listing contradicts


@pytest.mark.parametrize("quote,cond", [
    ("Max Fuel Flow 158 gal/hr", {"attribute": "average_fuel_consumption_full_standby_load", "op": "<=", "value": 145, "unit": "gph"}),
    ("Total Fuel Pump Flow (Combustion + Return) - 330 gph", {"attribute": "average_fuel_consumption_full_standby_load", "op": "<=", "value": 145, "unit": "gph"}),
    ("Frequency regulation, steady state ± 0.25%", {"attribute": "voltage_regulation_no_load_to_rated_load", "op": "<=", "value": 2, "unit": "%"}),
    ("Fan speed 710 rpm", {"attribute": "engine_speed", "op": "<=", "value": 1800, "unit": "rpm"}),
])
def test_regression_g10_a_neighbouring_quantity_is_never_compared(quote, cond):
    """Held-out G10 (run once on frozen code): a fuel FLOW figure was computed as fuel consumption and rejected."""
    assert I.compute_numeric(dict(cond, kind="numeric"), quote, "Fuel System Fuel Consumption") is None
