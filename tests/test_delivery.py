from pathlib import Path

import pytest

from amber.delivery import Evidence, _p_late, _quantiles, assess_delivery_risk
from amber.schema import Citation

ROOT = Path(__file__).resolve().parents[1]
C = Citation(doc_id="x", page=1, quote="q")


def ev(lo, hi, w=1.0):
    return Evidence("E", lo, hi, w, "src", C)


def test_quantiles_of_single_uniform():
    p10, p50, p90 = _quantiles([ev(40, 60)])
    assert p10 == pytest.approx(42, abs=0.5) and p50 == pytest.approx(50, abs=0.5) and p90 == pytest.approx(58, abs=0.5)


def test_heavier_source_pulls_the_middle():
    light = _quantiles([ev(40, 50), ev(60, 70)], (0.5,))[0]
    heavy = _quantiles([ev(40, 50), ev(60, 70, w=3.0)], (0.5,))[0]
    assert heavy > light


def test_p_late():
    assert _p_late([ev(40, 60)], 50) == pytest.approx(0.5)
    assert _p_late([ev(40, 60)], 70) == 0.0
    assert _p_late([ev(40, 60)], 30) == 1.0


def test_single_figure_quote_is_widened_not_zero_width():
    from amber.delivery import _span
    lo, hi, note = _span(60, 60, "Lead time approx 60 wks right now")
    assert (lo, hi) == (54, 66) and "±10%" in note
    later = _p_late([ev(50, 66), ev(*_span(60, 60, "approx")[:2], w=2.0)], 50)
    earlier = _p_late([ev(50, 66), ev(*_span(40, 40, "approx")[:2], w=2.0)], 50)
    assert later > earlier  # a slower quote can never lower the chance of being late


@pytest.fixture(scope="module")
def result():
    bids = {"GEN": {"B2": {"min_weeks": 50, "max_weeks": 54, "basis": "after_submittal_approval"},
                    "B3": {"min_weeks": 68, "max_weeks": 74, "basis": "after_order"}}}
    return assess_delivery_risk(str(ROOT / "data/schedules/equipment_schedule.csv"),
                                str(ROOT / "data/schedules/po_status.csv"),
                                str(ROOT / "data/leadtime_sources/leadtime_evidence.csv"), "2026-12-01",
                                bid_lead_times=bids)


def _find(res, group, scenario):
    return next(f for f in res.findings if f.data.get("tag_group") == group and f.data.get("scenario") == scenario)


def test_outlier_source_is_kept_but_flagged(result):
    gen = _find(result, "GEN", "market (not ordered)")
    outlier = next(e for e in gen.data["evidence"] if e["id"] == "LT-006")
    assert outlier["dissent"] and outlier["weight"] < 0.2


def test_every_forecast_cites_its_evidence(result):
    for f in result.findings:
        assert f.citations and len(f.citations) == len(f.data["evidence"])


def test_faster_bidder_arrives_earlier(result):
    b2, b3 = _find(result, "GEN", "award to B2"), _find(result, "GEN", "award to B3")
    assert b2.data["arrival"]["P50"] < b3.data["arrival"]["P50"]


def test_ranges_are_ordered_and_late_items_flagged(result):
    for f in result.findings:
        a = f.data["arrival"]
        assert a["P10"] <= a["P50"] <= a["P90"]
    assert _find(result, "GEN", "market (not ordered)").data["risk"] == "high"
    assert _find(result, "UPS", "as ordered").data["risk"] == "low"


def test_unordered_item_gets_latest_order_date(result):
    acts = _find(result, "GEN", "market (not ordered)").data["actions"]
    assert any("place the order by" in a for a in acts)
