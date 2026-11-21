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
