"""The manager web page: local only, never shows a key, reads only the data folder, keeps held-out documents sealed,
reuses saved results instead of spending tokens, and records a person's decisions beside the result."""
import json

import pytest
from starlette.testclient import TestClient

from amber import web


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(web, "WEB", tmp_path / "runs" / "web")
    monkeypatch.setattr(web, "UPLOADS", tmp_path / "uploads")
    (tmp_path / "runs").mkdir()
    web._jobs.clear()
    return TestClient(web.app)


def test_page_and_state_never_expose_a_key(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_secret_value_123")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-secret_456")
    page = client.get("/")
    assert page.status_code == 200 and "Amber procurement specialists" in page.text
    s = client.get("/api/state")
    assert s.status_code == 200
    text = s.text
    assert "secret" not in text and "gsk_" not in text and "sk-or" not in text
    providers = {p["id"]: p["available"] for p in s.json()["providers"]}
    assert providers["groq"] and providers["openrouter"]
    assert "gemini" not in providers  # the paid model is never offered on the page


def test_refuses_files_outside_the_data_folder(client):
    r = client.post("/api/run", json={"tool": "level_bids", "args": {"bid_form": "../.env", "bids": {}}})
    assert r.status_code == 400 and "data folder" in r.json()["error"]


def test_refuses_the_paid_provider(client):
    r = client.post("/api/run", json={"tool": "check_submittal", "provider": "gemini",
                                      "args": {"spec": web.PRESET["spec"], "submittal": web.PRESET["submittals"]["B2"], "tag": "GEN-A"}})
    if r.status_code == 400 and "file not found" in r.json()["error"]:
        pytest.skip("public datasheets not downloaded (fetch_data.py)")
    assert r.status_code == 400 and "provider" in r.json()["error"]


def test_held_out_documents_stay_sealed_until_their_final_run(client, tmp_path, monkeypatch):
    monkeypatch.setattr(web, "EXAMPLES", tmp_path / "no-examples")  # as before any final run existed
    sealed = web._sealed()
    assert sealed, "held-out set 2 has no run yet, so it must be sealed"
    doc = sorted(sealed)[0]
    r = client.post("/api/run", json={"tool": "check_submittal", "args": {"spec": web.PRESET["spec"], "submittal": doc, "tag": "GEN-A"}})
    assert r.status_code == 400 and "held-out" in r.json()["error"]
    assert doc not in client.get("/api/state").json()["files"]["submittals"]


def test_delivery_runs_instantly_then_reopens_from_the_saved_result(client):
    args = {"as_of": "2026-12-01"}
    first = client.post("/api/run", json={"tool": "assess_delivery_risk", "args": args}).json()
    assert first["cached"] is False and first["result_id"].startswith("web:")
    again = client.post("/api/run", json={"tool": "assess_delivery_risk", "args": args}).json()
    assert again == {"result_id": first["result_id"], "cached": True}
    res = client.get(f"/api/results/{first['result_id']}").json()
    assert res["result"]["tool"] == "assess_delivery_risk" and res["result"]["findings"]
    saved = client.get("/api/state").json()["saved"]
    assert any(m["id"] == first["result_id"] for m in saved)


def test_review_decisions_are_saved_beside_the_result(client):
    rid = client.post("/api/run", json={"tool": "assess_delivery_risk", "args": {"as_of": "2026-12-01"}}).json()["result_id"]
    fid = client.get(f"/api/results/{rid}").json()["result"]["findings"][0]["id"]
    r = client.post(f"/api/results/{rid}/review", json={"finding": fid, "decision": "agree", "note": "checked the PO"})
    assert r.status_code == 200 and r.json()["reviews"][fid]["decision"] == "agree"
    assert client.get(f"/api/results/{rid}").json()["reviews"][fid]["note"] == "checked the PO"
    assert client.post(f"/api/results/{rid}/review", json={"finding": fid, "decision": "approve it all"}).status_code == 400
    assert client.post(f"/api/results/{rid}/review", json={"finding": "nope", "decision": "agree"}).status_code == 400
    assert client.post(f"/api/results/{rid}/review", json={"finding": fid, "decision": "clear"}).json()["reviews"] == {}


def test_committed_examples_open_without_any_run(client):
    saved = {m["id"]: m for m in client.get("/api/state").json()["saved"]}
    assert "example:package_GEN" in saved and saved["example:package_GEN"]["source"] == "example in the repo"
    res = client.get("/api/results/example:package_GEN").json()["result"]
    assert res["tool"] == "run_package_review" and res["result"]["follow_ups"]
    assert client.get("/api/results/example:package_GEN/report").status_code == 200


def test_result_ids_cannot_escape_the_runs_folder(client):
    for rid in ("runs:../../.env", "web:..%2F..%2Fx", "other:G2", "web:index"):
        assert client.get(f"/api/results/{rid}").status_code == 404


def test_upload_accepts_pdf_and_txt_only(client):
    bad = client.post("/api/upload", data={"kind": "bids"}, files={"file": ("x.exe", b"MZ...", "application/octet-stream")})
    assert bad.status_code == 400
    fake = client.post("/api/upload", data={"kind": "submittals"}, files={"file": ("x.pdf", b"not a pdf", "application/pdf")})
    assert fake.status_code == 400
    ok = client.post("/api/upload", data={"kind": "bids"}, files={"file": ("../../B5 email.txt", b"Bid: $1", "text/plain")})
    assert ok.status_code == 200 and ok.json()["path"] == "uploads/bids/B5_email.txt"
    assert (web.UPLOADS / "bids" / "B5_email.txt").read_bytes() == b"Bid: $1"


def test_follow_up_drafts_from_a_saved_command_line_run(client):
    run = {"tool": "level_bids", "result": {"package": "P", "scope": [{"id": "S7", "item": "Rigging"}]},
           "findings": [{"id": "F-B1-S7", "claim": "B1 S7: excluded", "status": "deviates", "confidence": 0.9, "needs_human": False,
                         "why": "excluded", "citations": [{"doc_id": "b1", "page": 1, "locator": "", "quote": "Rigging by others.",
                                                          "match": "exact", "ocr": False}],
                         "data": {"bid": "B1", "scope_id": "S7", "scope_status": "excluded"}}],
           "needs_human": [], "run": {"models": [], "latency_ms": 0}}
    (web.RUNS / "BLX.json").write_text(json.dumps(run), encoding="utf-8")
    d = client.post("/api/results/runs:BLX/drafts", json={}).json()["drafts"]
    assert len(d) == 1 and "Rigging by others." in d[0]["body"]


def test_source_viewer_highlights_the_quote_on_the_cited_page(client):
    r = client.get("/api/source", params={"doc": "26-32-13-engine-generators-alpha", "page": 3,
                                          "q": "shall be rated for the continuous standby capacity (kW and kVA at 0.8 PF)"})
    assert r.status_code == 200
    out = r.json()
    assert out["kind"] == "pdf" and out["page"] == 3 and out["found"] >= 1 and out["image"].startswith("data:image/png;base64,")


def test_source_viewer_marks_the_cited_row_and_links_the_website(client):
    out = client.get("/api/source", params={"doc": "leadtime-evidence", "q": "", "loc": "LT-002 (1500-2000 kW)"}).json()
    assert out["kind"] == "table" and len(out["hl"]) == 1
    assert out["rows"][out["hl"][0]][0] == "LT-002"
    assert all(u.startswith("https://") for u in out["links"].values())


def test_source_viewer_and_originals_refuse_unknown_or_sealed_documents(client):
    for doc in ("../.env", "nope", "C:/Windows/win.ini"):
        assert client.get("/api/source", params={"doc": doc}).status_code == 404
        assert client.get(f"/api/file/{doc}").status_code == 404
    for rel in web._sealed():  # held-out documents stay unseen until their final run
        from amber.docs import doc_id_for
        assert client.get("/api/source", params={"doc": doc_id_for(rel)}).status_code == 404
    orig = client.get("/api/file/26-32-13-engine-generators-alpha")
    assert orig.status_code == 200 and orig.headers["content-type"] == "application/pdf"


def test_overview_needs_no_model(client, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    o = client.get("/api/overview").json()
    assert o["rows"] and all(r["arrival"]["P50"] and r["citations"] for r in o["rows"])


def test_a_held_out_document_is_sealed_exactly_until_its_final_run_is_committed(client):
    from pathlib import Path
    sealed = web._sealed()
    seen_sealed = 0
    for k in web.KEYS.glob("[GU][0-9]*.json"):
        case = json.loads(k.read_text(encoding="utf-8"))
        rel = Path(case["submittal"]).relative_to("data").as_posix()
        has_run = (web.EXAMPLES / k.name).exists() or (web.RUNS / k.name).exists()
        if case["split"] == "heldout":
            assert (rel in sealed) == (not has_run), k.name
            seen_sealed += rel in sealed
        else:
            assert rel not in sealed
    assert seen_sealed == len(sealed)  # nothing else is hidden


def test_proof_tab_reproduces_the_readme_numbers_from_the_saved_runs(client):
    web._proof_cache.clear()
    P = client.get("/api/proof").json()
    assert (P["sets"]["1"]["n"], P["sets"]["1"]["correct"]) == (58, 34)  # held-out set 1, before the fixes
    assert (P["sets"]["2"]["n"], P["sets"]["2"]["correct"]) == (42, 28)  # held-out set 2
    assert P["sets"]["2"]["auto_correct"] == P["sets"]["2"]["auto_total"] == 11
    assert (P["sets"]["3"]["n"], P["sets"]["3"]["correct"]) == (42, 32)  # held-out set 3: fresh documents, run once
    assert (P["sets"]["3"]["auto_correct"], P["sets"]["3"]["auto_total"]) == (14, 15)
    assert P["fabrications"] in (0, None)  # None only when the datasheets are not downloaded
    assert P["bids"]["cells"] == 44 and P["bids"]["award_withheld"] and P["bids"]["rank_ok"]
    assert P["bids"]["second_run"]["cells"] == 44 and P["bids"]["second_run"]["award_withheld"]  # a second reading of the same bids
    assert all(c["result_id"].startswith(("runs:", "example:")) for c in P["cases"])


def test_results_carry_the_independent_readers_verdicts_without_changing_any_verdict(client):
    r = client.get("/api/results/example:G7").json()
    cr = r["cross_read"]
    assert len(cr) == 21 and all(set(x) >= {"verdict", "agrees", "model"} for x in cr.values())
    by_id = {f["id"]: f for f in r["result"]["findings"]}
    assert all(x["agrees"] == (x["verdict"] == by_id[i]["status"]) for i, x in cr.items())
    pkg = client.get("/api/results/example:package_GEN").json()["cross_read"]
    assert {i.split("/")[0] for i in pkg} == {"submittal:B1", "submittal:B3", "submittal:B4"}  # B2's 66-page sheet is not cross-read


def test_the_proof_tab_reports_what_the_independent_reader_tells_us(client):
    web._proof_cache.clear()
    C = client.get("/api/proof").json()["cross"]
    assert C["n"] == 142 and len(C["documents"]) == 7
    assert (C["handed_agrees"]["n"], C["handed_agrees"]["right"]) == (49, 41)  # agreement sorts what a person must look at
    assert (C["handed_disagrees"]["n"], C["handed_disagrees"]["right"]) == (50, 19)
    assert C["auto_agrees"]["right"] == C["auto_agrees"]["n"]
    assert (C["unclear_with_concrete_reader"]["n"], C["unclear_with_concrete_reader"]["right"]) == (22, 7)  # it never overrules
    assert (C["unclear_with_reader_missing"]["n"], C["unclear_with_reader_missing"]["right"]) == (15, 13)
