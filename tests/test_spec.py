from pathlib import Path

import pytest

from amber import docs, spec

ROOT = Path(__file__).resolve().parents[1]
ALPHA = ROOT / "data/specs/project_alpha/26_32_13_engine_generators_ALPHA.pdf"
UH_RAW = ROOT / "data/specs/UH_263213_engine_generators.pdf"  # third-party, may be absent


@pytest.fixture(scope="module")
def alpha():
    return spec.parse(docs.load(ALPHA))


def by_loc(clauses, loc):
    return [c for c in clauses if c.locator == loc]


def test_finds_parts_and_products(alpha):
    assert {c.part for c in alpha} >= {1, 2, 3}
    assert len(spec.products(alpha)) > 60


def test_locators_and_titles(alpha):
    cap = by_loc(alpha, "2.1.C")
    assert cap and cap[0].title == "System Capacity"
    assert "480Y/277 volt" in cap[0].text
    gov = [c for c in alpha if c.title == "Governor"]
    assert gov and gov[0].locator == "2.1.D.3"


def test_inline_numbers_are_not_mistaken_for_markers(alpha):
    # "Division 22." and "0.8 PF" must stay inside their sentences
    assert not by_loc(alpha, "0.8")
    assert not any(c.text.startswith("22. ") for c in alpha)


def test_page_headers_are_removed(alpha):
    assert not any("PROJECT ALPHA - PHASE 1" in c.text for c in alpha)


def test_page_numbers_point_at_real_pages(alpha):
    d = docs.load(ALPHA)
    for c in spec.products(alpha)[:40]:
        first_words = " ".join(c.text.split()[:6])
        assert first_words.split()[1] in d.page(c.page).text


@pytest.mark.skipif(not UH_RAW.exists(), reason="third-party PDF not downloaded")
def test_works_on_an_unedited_third_party_spec():
    clauses = spec.parse(docs.load(UH_RAW))
    titles = {c.title for c in spec.products(clauses)}
    assert {"System Capacity", "Governor"} <= titles
