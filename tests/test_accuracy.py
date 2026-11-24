"""Accuracy fixes found by replaying the saved runs: parser bugs, shortened quotes, and the targeted re-read."""
from amber import checks
from amber.docs import Document, Page
from amber.schema import Verdict
from amber.submittal import _decide_condition, _partial_terms, extract_offers
from amber.verify import match_level


# ---- numbers
def test_a_dash_in_a_range_or_tolerance_is_not_a_minus_sign():
    assert checks.numbers_in("Standby: kW 1590--2000") == [1590.0, 2000.0]
    assert checks.numbers_in("1,500-2,000 kW") == [1500.0, 2000.0]
    assert checks.numbers_in("+/-0.25%") == [0.25]
    assert checks.numbers_in("-40 C to 122 F") == [-40.0, 122.0]


def test_decimal_commas_and_thousand_separators():
    assert checks.numbers_in("Voltage regulation (+/- %) 0,50") == [0.5]
    assert checks.numbers_in("THD in no-load (%) 2,1") == [2.1]
    assert checks.numbers_in("7,000 kVA") == [7000.0]
    assert checks.numbers_in("cylinders 6,12,16") == [6.0, 12.0, 16.0]


def test_a_qualifier_is_not_a_label():
    vals, err = checks._single_numbers(["up to 8 units"], "units")
    assert err is None and vals == ["up to 8 units"]
    _, err = checks._single_numbers(["Peak motor starting kVA: (35% dip for voltages"], "kVA")
    assert err  # a real table label is still refused


# ---- shortened quotes
PAGE = "Peak motor starting kVA: (35% dip) 5400 6200 7000 (60 Hz) more text"


def test_a_quote_shortened_with_dots_needs_every_piece_on_the_page_in_order():
    assert match_level("Peak motor starting kVA: ... 7000 (60 Hz)", PAGE) == "segments"
    assert match_level("7000 (60 Hz) ... Peak motor starting kVA:", PAGE) is None  # wrong order
    assert match_level("Peak motor starting kVA: ... 9999 (60 Hz)", PAGE) is None  # an invented number


# ---- text conditions
def _doc(text):
    return Document("d", "d.pdf", pages=[Page(1, text * 3)])


def test_a_partly_matched_text_requirement_is_unclear_unless_the_model_confirms_it():
    cond = {"cid": "R07a", "kind": "text", "terms": ["24 volt", "electric starter"], "match": "all"}
    assert _partial_terms(cond, "Starting voltage 24 V") == (["24 volt"], ["electric starter"])  # '24 V' is '24 volt'
    assert _partial_terms(cond, "Starting voltage 12 V") is None  # no term found: nothing partial, a real mismatch
    assert _partial_terms(cond, "24 volt starting") == (["24 volt"], ["electric starter"])
    assert _partial_terms({"terms": ["a", "b"], "match": "any"}, "a") is None  # alternatives: nothing partial
    doc = _doc("Starting system 24 volt negative ground ")
    offer = {"cid": "R07a", "stated": True, "values": ["24 volt"], "quote": "Starting system 24 volt negative ground", "page": 1}
    d, _, conf = _decide_condition(cond, dict(offer, meets="unknown"), doc)
    assert d.verdict == Verdict.unclear and conf < 0.70
    d, _, conf = _decide_condition(cond, dict(offer, meets="yes"), doc)  # the model's own judgement still counts, capped
    assert d.verdict == Verdict.complies and conf <= 0.65


# ---- the targeted re-read
class FakeLLM:
    local = False

    def __init__(self, third):
        self.third, self.purposes = third, []

    def json(self, system, user, max_tokens=0, schema=None, purpose=""):
        self.purposes.append(purpose)
        if purpose.startswith("targeted re-read"):
            return {"offers": self.third}
        return {"offers": [{"cid": "R12a", "stated": False, "values": [], "unit": "", "quote": "", "page": 0, "meets": "unknown"}]}


COND = {"cid": "R12a", "kind": "numeric", "attribute": "rated_speed", "op": "<=", "value": 1800, "unit": "rpm"}
REQS = [{"req_id": "R12", "requirement": "Speed at most 1800 rpm", "conditions": [COND]}]
FOUND = [{"cid": "R12a", "stated": True, "values": ["1800"], "unit": "rpm", "quote": "Rated speed: 1800 rpm", "page": 1, "meets": "yes"}]


def test_when_the_document_mentions_a_condition_the_pages_that_mention_it_are_read_again():
    doc = _doc("Rated speed: 1800 rpm at 60 Hz. ")
    llm = FakeLLM(FOUND)
    offers = extract_offers(llm, doc, REQS)
    assert any(p.startswith("targeted re-read") for p in llm.purposes)
    assert offers["R12a"]["third_look"] is True
    d, cite, conf = _decide_condition(COND, offers["R12a"], doc)
    assert d.verdict == Verdict.complies and cite.quote == "Rated speed: 1800 rpm"
    assert conf <= 0.65 and "targeted re-read" in d.why  # evidenced, but a person confirms it


def test_a_statement_that_is_not_on_the_page_is_never_a_claim():
    doc = _doc("Rated speed: 1800 rpm at 60 Hz. ")
    bad = [dict(FOUND[0], quote="Rated speed: 1500 rpm", values=["1500"])]
    offers = extract_offers(FakeLLM(bad), doc, REQS)
    d, cite, conf = _decide_condition(COND, offers["R12a"], doc)
    assert d.verdict == Verdict.unclear and cite is None and "not found" in d.why


def test_nothing_is_re_read_when_the_document_never_mentions_the_condition(monkeypatch):
    doc = _doc("Dimensions and weights are shown overleaf. ")
    llm = FakeLLM(FOUND)
    offers = extract_offers(llm, doc, REQS)
    assert not any(p.startswith("targeted re-read") for p in llm.purposes) and not offers.get("R12a", {}).get("stated")
    monkeypatch.setenv("AMBER_TARGETED_READ", "off")  # and it can be switched off for a like-for-like comparison
    llm = FakeLLM(FOUND)
    extract_offers(llm, _doc("Rated speed: 1800 rpm at 60 Hz. "), REQS)
    assert not any(p.startswith("targeted re-read") for p in llm.purposes)
