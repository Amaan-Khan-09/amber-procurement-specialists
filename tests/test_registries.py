"""Public registry lookups: confirmed, no match, ambiguous identity and unavailable source, with injected sources."""
import io
import json
import urllib.error

import pytest

from amber import registries as R
from amber import vendors


def _usa(results, total=None):
    def http(url, body=None, timeout=30):
        return json.dumps({"results": results, "page_metadata": {"total": total or len(results)}}).encode()
    return http


def _down(url, body=None, timeout=30):
    raise R.SourceError("URLError: name resolution failed")


def test_one_clear_entity_is_confirmed_with_its_identifier():
    r = R.lookup_entity("PD Power Systems, LLC", http=_usa([{"name": "PD POWER SYSTEMS, LLC", "uei": "GRRQGPH7QS29", "amount": 1}]))
    assert r["status"] == "confirmed" and r["uei"] == "GRRQGPH7QS29" and r["looked_up"] and r["endpoint"] == R.USA_RECIPIENT


def test_several_entities_with_the_name_are_ambiguous_never_picked():
    r = R.lookup_entity("Cummins", http=_usa([{"name": "CUMMINS INC", "uei": "A"}, {"name": "CUMMINS INC.", "uei": "B"},
                                              {"name": "CUMMINS PACIFIC, LLC", "uei": "C"}]))
    assert r["status"] == "ambiguous" and len(r["candidates"]) >= 2 and "uei" not in r


def test_a_name_that_only_shares_a_word_does_not_match():
    r = R.lookup_entity("Tidewater Generator Co.", http=_usa([{"name": "TIDEWATER MARINE LLC", "uei": "Z"}, {"name": "GENERATOR SOURCE INC", "uei": "Y"}]))
    assert r["status"] == "no match"


@pytest.mark.parametrize("fn", [lambda: R.lookup_entity("Any Co", http=_down), lambda: R.sam_exclusions("Any Co", http=_down, key="k"),
                                lambda: R.public_discovery(http=_down)])
def test_a_source_that_fails_is_unavailable_never_no_match(fn):
    r = fn()
    assert r["status"] == "unavailable" and "no match" not in r.get("why", "")


def test_without_a_key_the_exclusion_check_is_unavailable_and_says_so():
    r = R.sam_exclusions("Any Co", http=_down, key="")
    assert r["status"] == "unavailable" and "SAM_API_KEY" in r["why"] and "NOT done" in r["why"]


def test_a_key_never_appears_in_an_error():
    def fail(url, body=None, timeout=30):
        raise R.SourceError("HTTPError 403 for " + url)
    r = R.sam_exclusions("Any Co", http=fail, key="SECRETKEY123")
    assert "SECRETKEY123" not in json.dumps(r)


def _sam(records):
    def http(url, body=None, timeout=30):
        return json.dumps({"totalRecords": len(records), "excludedEntity": records}).encode()
    return http


def _rec(name, uei):
    return {"exclusionIdentification": {"entityName": name, "ueiSAM": uei}, "exclusionDetails": {"exclusionType": "Ineligible"}}


def test_sam_confirmed_ambiguous_and_clear():
    assert R.sam_exclusions("Acme Power LLC", http=_sam([_rec("ACME POWER LLC", "U1")]), key="k")["status"] == "confirmed"
    two = R.sam_exclusions("Acme Power", http=_sam([_rec("ACME POWER LLC", "U1"), _rec("ACME POWER INC", "U2")]), key="k")
    assert two["status"] == "ambiguous"
    assert R.sam_exclusions("Acme Power", http=_sam([]), key="k")["status"] == "no match"


def test_only_the_official_list_can_pass_or_fail_the_exclusion_criterion():
    res = lambda: {"criteria": {"Q7": {"status": "needs_verification", "why": "", "route": "engineer"}}, "overall": "x", "fails": [], "owner_checks": []}
    screen = lambda sam, ent="confirmed": {"sam_exclusions": {"status": sam, "looked_up": "t", "why": "w"},
                                           "entity": {"status": ent, "legal_entity": "E", "uei": "U" if ent == "confirmed" else None},
                                           "screening_list": {"status": "no match"}}
    q = lambda s: vendors.apply_registry(res(), s)["criteria"]["Q7"]
    assert q(screen("confirmed"))["status"] == "fails"
    assert q(screen("no match"))["status"] == "meets"
    for s in (screen("unavailable"), screen("ambiguous"), screen("no match", ent="no match")):
        assert q(s)["status"] == "needs_verification"      # a clean screening list never stands in for SAM.gov


def test_the_saved_lookup_snapshot_names_sources_and_times():
    s = R.snapshot()
    assert s and s["taken"] and s["discovery"]["endpoint"] == R.USA_AWARDS
    for sc in s["screens"].values():
        for k in ("entity", "sam_exclusions", "screening_list"):
            assert sc[k]["looked_up"] and sc[k]["source"] and sc[k]["status"] in ("confirmed", "no match", "ambiguous", "unavailable")
