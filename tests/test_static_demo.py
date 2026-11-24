"""The static demo: built from the saved results by the real server code, and it must never republish a manufacturer's
copyrighted document."""
import json
import re

import pytest

from amber import demo


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    out = tmp_path_factory.mktemp("demo")
    return out, demo.build(out)


def test_every_saved_result_and_citation_is_answered_from_files(site):
    out, summary = site
    state = json.loads((out / "data" / "state.json").read_text(encoding="utf-8"))
    assert summary["results"] == len(state["saved"]) >= 11
    for m in state["saved"]:
        assert (out / "data" / "results" / (m["id"].replace(":", "__") + ".json")).exists()
    sources = json.loads((out / "data" / "sources.json").read_text(encoding="utf-8"))
    res = json.loads((out / "data" / "results" / "example__package_GEN.json").read_text(encoding="utf-8"))["result"]
    for f in res["findings"]:
        for c in f["citations"]:
            assert f"{c['doc_id']}|{c['page']}|{c['quote']}|{c.get('locator') or ''}" in sources, c["doc_id"]
    assert (out / "reports" / "example__package_GEN.html").exists()


def test_the_demo_never_contains_a_manufacturers_document(site):
    out, _ = site
    own_pdfs = {"26_32_13_engine_generators_ALPHA.pdf", "26_33_53_static_ups_ALPHA.pdf", "B1_northline_power.pdf",
                "B2_tidewater_generator.pdf", "B3_keystone_energy.pdf"}
    files = [f for f in out.rglob("*") if f.is_file()]
    assert {f.name for f in files if f.suffix.lower() == ".pdf"} <= own_pdfs
    allowed_images = ("26-32-13-engine-generators-alpha", "26-33-53-static-ups-alpha", "b1-northline-power",
                      "b2-tidewater-generator", "b3-keystone-energy")
    assert all(f.name.startswith(allowed_images) for f in files if f.suffix.lower() in (".jpg", ".png"))
    sources = json.loads((out / "data" / "sources.json").read_text(encoding="utf-8"))
    quotes = [e for e in sources.values() if e["kind"] == "quote"]
    assert quotes and all("image" not in e and "rects" not in e for e in quotes)  # an excerpt, never a page


def test_no_local_paths_or_keys_in_the_demo(site):
    out, _ = site
    for f in out.rglob("*"):
        if f.is_file() and f.suffix.lower() in (".json", ".js", ".html", ".csv", ".txt"):
            text = f.read_text(encoding="utf-8", errors="replace")
            assert not re.search(r"[A-Za-z]:\\Users|/Users/|AppData|gsk_[A-Za-z0-9]{10}|AIza[0-9A-Za-z_-]{20}", text), f.name


def test_the_page_loads_the_shim_with_its_configuration_filled_in(site):
    out, _ = site
    assert '<script src="demo-shim.js"></script>' in (out / "index.html").read_text(encoding="utf-8")
    shim = (out / "demo-shim.js").read_text(encoding="utf-8")
    assert "__CONFIG__" not in shim and "result_id" in shim
