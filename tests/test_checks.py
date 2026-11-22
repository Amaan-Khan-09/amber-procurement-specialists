from amber.checks import decide, qty
from amber.schema import Verdict


def V(req, offer):
    return decide(req, offer).verdict


def test_unit_conversion_fuel():
    req = {"kind": "numeric", "op": "<=", "value": 145, "unit": "gph"}
    assert V(req, {"values": [528], "unit": "L/hr"}) == Verdict.complies      # 139.5 gph
    assert V(req, {"values": [560], "unit": "L/hr"}) == Verdict.deviates      # 147.9 gph


def test_temperature_f_vs_c():
    req = {"kind": "numeric", "op": ">=", "value": 122, "unit": "°F"}
    assert V(req, {"values": [50], "unit": "°C"}) == Verdict.complies
    assert V(req, {"values": [40], "unit": "°C"}) == Verdict.deviates


def test_power_rating_and_equality():
    assert V({"kind": "numeric", "op": ">=", "value": 2000, "unit": "kW"}, {"values": ["2000 ekW"], "unit": "kW"}) == Verdict.complies
    assert V({"kind": "numeric", "op": "==", "value": 1800, "unit": "rpm"}, {"values": [1800], "unit": "rpm"}) == Verdict.complies
    assert V({"kind": "numeric", "op": "<=", "value": 1800, "unit": "rpm"}, {"values": [1500], "unit": "rpm"}) == Verdict.complies


def test_missing_when_not_stated():
    assert V({"kind": "numeric", "op": ">=", "value": 24, "unit": "h"}, None) == Verdict.missing
    assert V({"kind": "numeric", "op": ">=", "value": 24, "unit": "h"}, {"values": []}) == Verdict.missing


def test_options_without_selection():
    req = {"kind": "text", "options": ["480Y/277", "277/480"]}
    many = {"values": ["277/480", "4160", "13800"], "selected": None}
    assert V(req, many) == Verdict.unclear
    assert V(req, {**many, "values": ["4160", "13800"]}) == Verdict.deviates
    assert V(req, {"values": ["277/480"], "selected": True}) == Verdict.complies


def test_two_numbers_in_one_value_are_not_guessed():
    req = {"kind": "numeric", "op": "<=", "value": 145, "unit": "gph"}
    assert V(req, {"values": ["528.3 (139.6)"], "unit": "gph"}) == Verdict.unclear
    assert V(req, {"values": ["528.3 L/hr, 139.6 gph"], "unit": "gph"}) == Verdict.complies


def test_features_of_one_product_are_judged_together():
    req = {"kind": "text", "terms": ["24 v", "negative ground"], "match": "all"}
    assert V(req, {"values": ["24 V DC", "negative ground"]}) == Verdict.complies


def test_voltage_notation_variants_match():
    req = {"kind": "text", "terms": ["480Y/277"], "match": "all"}
    assert V(req, {"values": ["277/480 V"], "selected": True}) == Verdict.complies
    assert V(req, {"values": ["480/277"], "selected": True}) == Verdict.complies
    assert V(req, {"values": ["4160/2400"], "selected": True}) == Verdict.deviates


def test_incompatible_units_are_unclear_not_guessed():
    req = {"kind": "numeric", "op": ">=", "value": 2000, "unit": "kW"}
    d = decide(req, {"values": [2500], "unit": "kVA"})
    assert d.verdict == Verdict.unclear and not d.exact


def test_keyword_feature():
    req = {"kind": "text", "keywords": ["brushless"]}
    assert V(req, {"values": ["Brushless, rotating-field alternator"]}) == Verdict.complies
    assert V(req, {"values": ["Brush-type exciter"]}) == Verdict.deviates


def test_qty_parses_commas():
    assert qty("2,500 kVA", "kVA").magnitude == 2500


def test_grounding_is_word_based_not_substring():
    from amber.submittal import _grounded
    assert _grounded(["Electronic governor"], "Integrated digital electronic isochronous governor")
    assert not _grounded(["Hydraulic governor"], "Integrated digital electronic isochronous governor")
    assert _grounded(["277/480"], "Voltage - 480Y/277, 3 Phase")
    assert not _grounded([], "anything")


def test_derate_sentence_becomes_a_capped_judgement_not_a_confident_verdict():
    from amber.docs import Document, Page
    from amber.submittal import JUDGEMENT_CAP, _decide_condition
    doc = Document("d", "d.pdf", pages=[Page(1, "Derating factors. For temp above 40C engine derates at 17.6% per 10C. " * 3)])
    cond = {"cid": "R11a", "kind": "numeric", "op": ">=", "value": 122, "unit": "°F"}
    offer = {"cid": "R11a", "stated": True, "values": [], "quote": "For temp above 40C engine derates at 17.6% per 10C",
             "page": 1, "meets": "no"}
    d, cite, conf = _decide_condition(cond, offer, doc)
    assert d.verdict == Verdict.deviates and cite and conf <= JUDGEMENT_CAP < 0.70


def test_model_and_code_disagreement_goes_to_a_person():
    from amber.docs import Document, Page
    from amber.submittal import _decide_condition
    doc = Document("d", "d.pdf", pages=[Page(1, "Standby rating  1500  kW  at 0.8 PF " * 4)])
    cond = {"cid": "R01a", "kind": "numeric", "op": ">=", "value": 2000, "unit": "kW"}
    offer = {"cid": "R01a", "stated": True, "values": [1500], "unit": "kW", "quote": "Standby rating  1500  kW", "page": 1,
             "meets": "yes"}  # model wrongly says yes; code says deviates
    d, cite, conf = _decide_condition(cond, offer, doc)
    assert d.verdict == Verdict.unclear and conf < 0.70 and "disagree" in d.why


def test_bill_of_material_page_is_always_found():
    from amber.docs import Document, Page
    from amber.submittal import _config_pages
    doc = Document("d", "d.pdf", pages=[Page(1, "intro " * 50), Page(2, "Bill of Material\nFeature Code Description Qty\nA416 Heater 1"),
                                        Page(3, "long page " * 900)])
    assert _config_pages(doc) == [2]


def test_reported_value_must_be_in_its_own_quote():
    from amber.docs import Document, Page
    from amber.submittal import _decide_condition
    doc = Document("d", "d.pdf", pages=[Page(1, "Standard radiator   Ambient design, °F  104   Fan load 77 HP " * 3)])
    cond = {"cid": "R11a", "kind": "numeric", "op": ">=", "value": 122, "unit": "°F"}
    offer = {"cid": "R11a", "stated": True, "values": [122], "unit": "°F", "quote": "Ambient design, °F  104", "page": 1, "meets": "yes"}
    d, cite, conf = _decide_condition(cond, offer, doc)
    assert d.verdict == Verdict.unclear and conf < 0.70 and "do not appear" in d.why


def test_number_without_its_unit_in_the_quote_cannot_be_confident():
    from amber.docs import Document, Page
    from amber.submittal import _decide_condition
    doc = Document("d", "d.pdf", pages=[Page(1, "3 Motor starting  380  416  440  480  600   Voltage " * 3)])
    cond = {"cid": "R03a", "kind": "numeric", "op": ">=", "value": 3000, "unit": "kVA"}
    offer = {"cid": "R03a", "stated": True, "values": [380, 416, 440, 480, 600], "unit": "kVA",
             "quote": "3 Motor starting  380  416  440  480  600", "page": 1, "meets": "no"}
    d, cite, conf = _decide_condition(cond, offer, doc)
    assert conf < 0.70 and "unit" in d.why


def test_unit_spellings():
    from amber.checks import unit_in_text
    assert unit_in_text("kVA", "Maximum kVA (90% sustained voltage) 7944")
    assert unit_in_text("gph", "Fuel Consumption L/hr (gal./hr) 528.3 (139.6) gal./hr")
    assert not unit_in_text("kVA", "Motor starting 380 416")
    assert unit_in_text("", "anything")


def test_voltage_unit_spellings_match():
    req = {"kind": "text", "terms": ["480 volts", "3-phase", "3-wire"], "match": "all"}
    assert V(req, {"values": ["480 VAC, 3 Phase, 3 Wire plus ground"], "selected": True}) == Verdict.complies
    assert V(req, {"values": ["277/480 V 3-phase 3-wire"], "selected": True}) == Verdict.complies
    assert V(req, {"values": ["400 V 3-phase 3-wire"], "selected": True}) == Verdict.deviates


def test_bom_word_alone_marks_a_configuration_page():
    from amber.docs import Document, Page
    from amber.submittal import _config_pages
    doc = Document("d", "d.pdf", pages=[Page(1, "intro " * 40), Page(2, "BOM\nA416 Alternator heater\nA334 Starter 24 V"), Page(3, "bombastic " * 50)])
    assert _config_pages(doc) == [2]  # whole word only: 'bombastic' is not a BOM


def test_quote_copied_across_a_hyphenated_line_break_verifies():
    from amber.verify import match_level
    assert match_level("Exciter type  Brushless, Permanent- Magnet Pilot Exciter",
                       "Exciter type  Brushless, Permanent-\nMagnet Pilot Exciter") is not None


def test_metric_imperial_pair_is_resolved_by_its_header():
    from amber.docs import Document, Page
    from amber.submittal import _decide_condition
    text = "Fuel Consumption, L/hr (gal./hr)\n100% at Standby  528.3 (139.6)\n75% at Standby  455.9 (120.4)\n" * 2
    doc = Document("d", "d.pdf", pages=[Page(1, text)])
    cond = {"cid": "R08a", "kind": "numeric", "op": "<=", "value": 145, "unit": "gph"}
    offer = {"cid": "R08a", "stated": True, "values": ["528.3", "139.6"], "unit": "gph",
             "quote": "100% at Standby  528.3 (139.6)", "page": 1, "meets": "yes"}
    d, cite, conf = _decide_condition(cond, offer, doc)
    assert d.verdict == Verdict.complies, d.why


def test_text_value_not_in_the_quote_is_not_believed():
    from amber.docs import Document, Page
    from amber.submittal import _decide_condition
    doc = Document("d", "d.pdf", pages=[Page(1, "Approvals: cULus listing (UL 2200 and CSA C22.2 No. 100) " * 3)])
    cond = {"cid": "R19a", "kind": "text", "terms": ["ul 2085"], "match": "all"}
    offer = {"cid": "R19a", "stated": True, "values": ["UL 2085"], "quote": "cULus listing (UL 2200 and CSA C22.2 No. 100)",
             "page": 1, "meets": "unknown"}
    d, cite, conf = _decide_condition(cond, offer, doc)
    assert d.verdict == Verdict.deviates and conf < 0.70  # quote shows UL 2200, not the claimed UL 2085: a person confirms


def test_one_quote_cannot_be_evidence_for_two_attributes():
    from amber.submittal import _flag_shared_evidence
    reqs = [{"req_id": "R17", "conditions": [{"cid": "R17a", "attribute": "voltage_regulation_percent"}]},
            {"req_id": "R18", "conditions": [{"cid": "R18a", "attribute": "voltage_thd_no_load_to_full_linear_load"}]},
            {"req_id": "R01", "conditions": [{"cid": "R01a", "attribute": "standby_kw"}]}]
    q = "Voltage regulation, no-load to full-load  ±0.25%"
    offers = {"R17a": {"stated": True, "quote": q, "values": ["±0.25%"]},
              "R18a": {"stated": True, "quote": q, "values": ["±0.25%"]},
              "R01a": {"stated": True, "quote": "Standby: kW 2000", "values": ["2000"]}}
    _flag_shared_evidence(reqs, offers)
    assert "shared_with" not in offers["R17a"]           # 'regulation' is in the quote: it keeps the evidence
    assert offers["R18a"]["shared_with"] == "R17"        # THD does not: goes to a person
    assert "shared_with" not in offers["R01a"]


def test_label_returned_as_a_value_is_not_read_as_a_number():
    req = {"kind": "numeric", "op": ">=", "value": 3000, "unit": "kVA"}
    assert V(req, {"values": ["Peak motor starting kVA: (35% dip for voltages"], "unit": "kVA"}) == Verdict.unclear
    assert V(req, {"values": ["9957 kVA"], "unit": "kVA"}) == Verdict.complies
    assert V({"kind": "numeric", "op": ">=", "value": 2000, "unit": "kW"}, {"values": ["Standby 2000 kW"], "unit": "kW"}) == Verdict.complies


def test_required_words_next_to_a_negation_do_not_pass():
    from amber.docs import Document, Page
    from amber.submittal import _decide_condition
    doc = Document("d", "d.pdf", pages=[Page(1, "Bypass  Manual Maintenance Bypass  Included 300-500 kW  Not included 600-1200 kW " * 2)])
    cond = {"cid": "U10a", "kind": "text", "terms": ["manual maintenance bypass", "maintenance bypass"], "match": "any"}
    offer = {"cid": "U10a", "stated": True, "values": ["Included 300-500 kW", "Not included 600-1200 kW"],
             "quote": "Manual Maintenance Bypass  Included 300-500 kW", "page": 1, "meets": "yes", "selected": True}
    d, cite, conf = _decide_condition(cond, offer, doc)
    assert d.verdict == Verdict.unclear and conf < 0.70  # was a confident 'complies' in the held-out run (U1, U10)


def test_plain_inclusion_still_passes():
    from amber.docs import Document, Page
    from amber.submittal import _decide_condition
    doc = Document("d", "d.pdf", pages=[Page(1, "Features: integral manual maintenance bypass switch, static bypass " * 2)])
    cond = {"cid": "X1a", "kind": "text", "terms": ["maintenance bypass"], "match": "any"}
    offer = {"cid": "X1a", "stated": True, "values": ["integral manual maintenance bypass switch"],
             "quote": "integral manual maintenance bypass switch", "page": 1, "meets": "yes", "selected": True}
    d, cite, conf = _decide_condition(cond, offer, doc)
    assert d.verdict == Verdict.complies
