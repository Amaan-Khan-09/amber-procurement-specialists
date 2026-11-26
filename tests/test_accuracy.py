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


# ---- a rejection may not rest on two columns run together
def _two_columns(sorted_text, own_order):
    return Document("d", "d.pdf", pages=[Page(1, sorted_text, raw=own_order)])


def test_a_number_borrowed_from_the_next_column_cannot_reject_a_product():
    sorted_text = "Peak motor starting kVA: (35% dip for voltages\n (with standard starters) 4, 1110, AGM below)\n480 V 9957"
    own_order = "(with standard starters)\n4, 1110, AGM\nPeak motor starting kVA:\n(35% dip for voltages\nbelow)\n480 V\n9957"
    doc = _two_columns(sorted_text, own_order)
    cond = {"cid": "R03a", "kind": "numeric", "operator": ">=", "value": 3000, "unit": "kVA"}
    for quote in ("Peak motor starting kVA: (35% dip for voltages ... 4, 1110, AGM below)",  # stitched
                  "(35% dip for voltages (with standard starters) 4, 1110, AGM"):  # only exists in the sorted text
        offer = {"cid": "R03a", "stated": True, "values": [1110], "unit": "kVA", "quote": quote, "page": 1}
        d, cite, conf = _decide_condition(cond, offer, doc)
        assert cite is not None and d.verdict == Verdict.unclear and conf < 0.70, quote


def test_a_rejection_that_reads_as_one_run_of_text_still_stands():
    doc = _two_columns("Peak motor starting kVA 1110 kVA", "Peak motor starting kVA\n1110 kVA")
    cond = {"cid": "R03a", "kind": "numeric", "operator": ">=", "value": 3000, "unit": "kVA"}
    offer = {"cid": "R03a", "stated": True, "values": [1110], "unit": "kVA",
             "quote": "Peak motor starting kVA 1110 kVA", "page": 1}
    d, _, conf = _decide_condition(cond, offer, doc)
    assert d.verdict == Verdict.deviates and conf >= 0.70


# ---- a quoted passage is never "missing"
def test_a_verified_quote_with_no_value_is_unclear_not_missing():
    doc = _doc("Cooling systems available to operate in temperatures up to 50 C ")
    cond = {"cid": "R11b", "kind": "numeric", "op": "between", "min": 10, "max": 122, "unit": "°F"}
    offer = {"cid": "R11b", "stated": True, "values": [], "quote": "temperatures up to 50 C", "page": 1, "meets": "unknown"}
    d, cite, conf = _decide_condition(cond, offer, doc)
    assert cite is not None and d.verdict == Verdict.unclear and conf < 0.70


# ---- the layout reading: whole pages, columns apart
def test_layout_cleaning_keeps_words_numbers_and_tick_boxes():
    from amber import layout
    md = "## **Alternator**\n|**Type**|4-Pole<sup>1</sup>|\n|---|---|\n- " + chr(0x2751) + " Battery Charger<br>(1 Ph)"
    out = layout.clean(md)
    assert "Type | 4-Pole1" in out and chr(0x2751) + " Battery Charger (1 Ph)" in out and "**" not in out


def test_the_second_look_starts_with_pages_not_yet_read():
    from amber.submittal import _page_context
    doc = Document("d", "d.pdf", pages=[Page(n, "p", layout=f"fuel tank page {n} " + "x" * 5000) for n in (1, 2, 3, 4)])
    cond = [{"cid": "a", "attribute": "fuel_tank"}]
    first_text, first = _page_context(doc, cond, limit=11000)
    _, second = _page_context(doc, cond, skip=first, limit=11000)
    assert len(first) == 2 and first | second == {1, 2, 3, 4} and "[page" in first_text


def test_a_quote_from_a_table_row_is_found_on_the_layout_reading():
    from amber.verify import reads_as_one, verify
    doc = Document("d", "d.pdf", pages=[Page(1, "Peak kVA: 480 V 4, 1110 9957", raw="Peak kVA:\n480 V\n9957",
                                            layout="Peak motor starting kVA: | (35% dip)\n480 V KH07801TO4D | 9957")])
    c = verify(doc, "480 V KH07801TO4D | 9957", 1)
    assert c is not None and reads_as_one(doc, c)


# ---- a choice on a list is not a supplied item
def test_a_ticked_list_item_cannot_comply_on_its_own():
    boxed = chr(0x2751)
    cond = {"cid": "R16a", "kind": "text", "terms": ["3 pole"], "match": "all"}
    offer = {"cid": "R16a", "stated": True, "values": ["3-pole"], "quote": "3-pole breaker", "page": 1}
    listed = Document("d", "d.pdf", pages=[Page(1, boxed + " 3-pole breaker " * 1 + "x" * 40, raw=boxed + "\n3-pole breaker\n")])
    d, _, conf = _decide_condition(cond, dict(offer), listed)
    assert d.verdict == Verdict.unclear and conf < 0.70 and "choice" in d.why
    stated = Document("d", "d.pdf", pages=[Page(1, "Standard: 3-pole breaker " + "x" * 40, raw="Standard: 3-pole breaker")])
    assert _decide_condition(cond, dict(offer), stated)[0].verdict == Verdict.complies


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


def test_when_the_document_mentions_a_condition_the_pages_that_mention_it_are_read_again(monkeypatch):
    monkeypatch.setenv("AMBER_TARGETED_READ", "on")
    doc = _doc("Rated speed: 1800 rpm at 60 Hz. ")
    llm = FakeLLM(FOUND)
    offers = extract_offers(llm, doc, REQS)
    assert any(p.startswith("targeted re-read") for p in llm.purposes)
    assert offers["R12a"]["third_look"] is True
    d, cite, conf = _decide_condition(COND, offers["R12a"], doc)
    assert d.verdict == Verdict.complies and cite.quote == "Rated speed: 1800 rpm"
    assert conf <= 0.65 and "targeted re-read" in d.why  # evidenced, but a person confirms it


def test_a_statement_that_is_not_on_the_page_is_never_a_claim(monkeypatch):
    monkeypatch.setenv("AMBER_TARGETED_READ", "on")
    doc = _doc("Rated speed: 1800 rpm at 60 Hz. ")
    bad = [dict(FOUND[0], quote="Rated speed: 1500 rpm", values=["1500"])]
    offers = extract_offers(FakeLLM(bad), doc, REQS)
    d, cite, conf = _decide_condition(COND, offers["R12a"], doc)
    assert d.verdict == Verdict.unclear and cite is None and "not found" in d.why


def test_nothing_is_re_read_when_the_document_never_mentions_the_condition(monkeypatch):
    monkeypatch.setenv("AMBER_TARGETED_READ", "on")
    doc = _doc("Dimensions and weights are shown overleaf. ")
    llm = FakeLLM(FOUND)
    offers = extract_offers(llm, doc, REQS)
    assert not any(p.startswith("targeted re-read") for p in llm.purposes) and not offers.get("R12a", {}).get("stated")
    monkeypatch.delenv("AMBER_TARGETED_READ")  # off unless asked for: it found nothing on the development documents
    llm = FakeLLM(FOUND)
    extract_offers(llm, _doc("Rated speed: 1800 rpm at 60 Hz. "), REQS)
    assert not any(p.startswith("targeted re-read") for p in llm.purposes)


# ---- the saved-check cache
def _cache_setup(tmp_path, monkeypatch):
    from amber import submittal
    monkeypatch.setattr(submittal, "RESULT_CACHE", tmp_path / "cache")
    monkeypatch.delenv("AMBER_RESULT_CACHE", raising=False)
    spec, sub = tmp_path / "spec.txt", tmp_path / "sub.txt"
    spec.write_text("26 32 13 spec", encoding="utf-8")
    sub.write_text("Rated speed: 1800 rpm", encoding="utf-8")
    sched = tmp_path / "schedule.csv"
    sched.write_text("tag,item,spec_section\nGEN-A,Generator,26 32 13\n", encoding="utf-8")
    calls = []

    def fake_reqs(llm, spec_doc, row, schedule_id, checklist=None):
        return REQS

    def fake_offers(llm, sub_doc, reqs):
        calls.append(1)
        if getattr(llm, "fail", False):
            llm.meter.steps.append({"purpose": "read submittal", "ok": False, "error": "model down"})
        return {"R12a": dict(FOUND[0], quote="Rated speed: 1800 rpm")}

    monkeypatch.setattr(submittal, "structure_requirements", fake_reqs)
    monkeypatch.setattr(submittal, "extract_offers", fake_offers)
    return submittal, str(spec), str(sub), str(sched), calls


class _Llm:
    local, provider, model, switched = False, "groq", "m", []
    fail = False

    def __init__(self):
        from amber.llm import Meter
        self.meter = Meter()


def test_an_identical_check_is_reused_instead_of_paid_for_again(tmp_path, monkeypatch):
    submittal, spec, sub, sched, calls = _cache_setup(tmp_path, monkeypatch)
    first = submittal.check_submittal(spec, sub, "GEN-A", sched, llm=_Llm(), ocr=False)
    again = submittal.check_submittal(spec, sub, "GEN-A", sched, llm=_Llm(), ocr=False)
    assert len(calls) == 1 and "reused_saved_check" not in first.result and again.result["reused_saved_check"]
    assert [f.status for f in again.findings] == [f.status for f in first.findings]


def test_a_changed_input_or_code_never_gets_a_saved_answer(tmp_path, monkeypatch):
    submittal, spec, sub, sched, calls = _cache_setup(tmp_path, monkeypatch)
    submittal.check_submittal(spec, sub, "GEN-A", sched, llm=_Llm(), ocr=False)
    (tmp_path / "sub.txt").write_text("Rated speed: 1500 rpm", encoding="utf-8")  # a different datasheet
    submittal.check_submittal(spec, sub, "GEN-A", sched, llm=_Llm(), ocr=False)
    assert len(calls) == 2
    monkeypatch.setattr(submittal, "code_fingerprint", lambda: "another-version-of-the-checking-code")
    submittal.check_submittal(spec, sub, "GEN-A", sched, llm=_Llm(), ocr=False)
    assert len(calls) == 3
    monkeypatch.setenv("AMBER_RESULT_CACHE", "off")  # and it can be switched off
    submittal.check_submittal(spec, sub, "GEN-A", sched, llm=_Llm(), ocr=False)
    assert len(calls) == 4


def test_a_check_with_a_failed_model_call_is_not_kept(tmp_path, monkeypatch):
    submittal, spec, sub, sched, calls = _cache_setup(tmp_path, monkeypatch)
    llm = _Llm()
    llm.fail = True  # a model call fails during this check
    submittal.check_submittal(spec, sub, "GEN-A", sched, llm=llm, ocr=False)
    submittal.check_submittal(spec, sub, "GEN-A", sched, llm=_Llm(), ocr=False)
    assert len(calls) == 2  # the failed one was never saved, so the second call had to do the work


def test_a_clean_bid_comparison_is_reused_and_a_failed_one_is_not(tmp_path, monkeypatch):
    from amber import bids
    monkeypatch.setattr(bids, "RESULT_CACHE", tmp_path / "cache")
    monkeypatch.delenv("AMBER_RESULT_CACHE", raising=False)
    form, b1, b2 = tmp_path / "form.txt", tmp_path / "b1.txt", tmp_path / "b2.txt"
    form.write_text("Bid form: S1 generators", encoding="utf-8")
    b1.write_text("Bidder one offers generators. Base 100", encoding="utf-8")
    b2.write_text("Bidder two offers generators. Base 120", encoding="utf-8")
    calls = []
    FORM = {"package": "P", "quantity": 1, "scope": [{"id": "S1", "item": "Generators"}], "allowances": []}

    def fake_form(llm, doc):
        calls.append("form")
        if getattr(llm, "fail", False):
            llm.meter.steps.append({"purpose": "read bid form", "ok": False, "error": "model down"})
        return FORM

    def fake_bid(llm, doc, form_):
        calls.append(doc.doc_id)
        return {"bidder": doc.doc_id, "offered_product": "G", "base_total": 100.0, "items": {"S1": {"status": "included"}},
                "terms": [], "lead_time": None, "base_citation": None, "product_citation": None}

    monkeypatch.setattr(bids, "read_form", fake_form)
    monkeypatch.setattr(bids, "read_bid", fake_bid)
    paths = {"B1": str(b1), "B2": str(b2)}
    bids.level_bids(str(form), paths, llm=_Llm())
    again = bids.level_bids(str(form), paths, llm=_Llm())
    assert calls.count("form") == 1 and again.result["reused_saved_check"]  # the second comparison cost nothing
    (tmp_path / "b2.txt").write_text("Bidder two offers generators. Base 999", encoding="utf-8")  # a changed bid is read again
    bids.level_bids(str(form), paths, llm=_Llm())
    assert calls.count("form") == 2
    failing = _Llm()
    failing.fail = True
    (tmp_path / "b1.txt").write_text("changed once more", encoding="utf-8")
    bids.level_bids(str(form), paths, llm=failing)
    bids.level_bids(str(form), paths, llm=_Llm())
    assert calls.count("form") == 4  # the comparison with a failed model call was never kept
