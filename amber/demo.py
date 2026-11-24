"""Build a static, read-only copy of the web page (for GitHub Pages) from the saved results in examples/.

Every file the page asks the server for is answered from pre-computed JSON, by the same server code the real app
uses, so the demo cannot show anything the app would not. Our own documents (the Project Alpha specs, the bids, the
schedule and the lead-time table) are shown as page images with the quoted words highlighted. Manufacturers' datasheets
are copyrighted, so they are never republished: the demo shows the short verified excerpt the agent cited, with a link
to the manufacturer's own page.

usage: python scripts/build_static_demo.py   (writes docs/demo/)
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterator

import pymupdf
from starlette.testclient import TestClient

from . import sources, web
from .docs import doc_id_for
from .report import render

ROOT, DATA = web.ROOT, web.DATA
OWN_PREFIXES = ("specs/project_alpha/", "bids/", "schedules/", "leadtime_sources/")
SHIM = Path(__file__).with_name("demo_shim.js")
DELIVERY_AS_OF = web.PRESET["as_of"]


def is_own(path: Path) -> bool:
    """Ours to publish: made by us (Project Alpha specs, bids, schedule) or a table of short cited excerpts."""
    rel = path.relative_to(DATA).as_posix()
    return rel.startswith(OWN_PREFIXES) and not (rel.startswith("leadtime_sources/") and path.suffix.lower() == ".pdf")


def safe(rid: str) -> str:
    return rid.replace(":", "__")


def _third_party_urls() -> dict[str, str]:
    spec = importlib.util.spec_from_file_location("amber_fetch_data", ROOT / "tools" / "data_prep" / "fetch_data.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    urls = {doc_id_for(Path(rel)): url for rel, _sha, url in mod.FILES}
    urls.setdefault("vertiv-exl-s1-package", urls.get(doc_id_for(Path("vertiv_EXL_S1_300-1200kW.pdf")), ""))
    return {k: v for k, v in urls.items() if v}


def _citations(obj: Any) -> Iterator[dict]:
    if isinstance(obj, dict):
        if {"doc_id", "page", "quote"} <= obj.keys():
            yield obj
        for v in obj.values():
            yield from _citations(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _citations(v)


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _pdf_entry(path: Path, c: dict) -> dict:
    with pymupdf.open(path) as pdf:
        n = pdf.page_count
        page_no = min(max(1, int(c["page"])), n)
        pg = pdf[page_no - 1]
        w, h = pg.rect.width or 1, pg.rect.height or 1
        rects = sources.find_rects(pg, c["quote"][:600]) if len(pg.get_text("text").strip()) >= 40 else []
    box = [[round(r.x0 / w, 4), round(r.y0 / h, 4), round(r.x1 / w, 4), round(r.y1 / h, 4)] for r in rects]
    return {"kind": "pdf", "name": path.name, "pages": n, "page": page_no, "found": len(box), "scanned": False,
            "top": min((b[1] for b in box), default=None), "rects": box,
            "image": f"data/pages/{doc_id_for(path)}-{page_no}.jpg"}


def build(out: Path) -> dict:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    idx = sources.index(DATA)
    urls = _third_party_urls()
    summary: dict[str, Any] = {}

    with tempfile.TemporaryDirectory() as tmp:
        saved_paths = (web.RUNS, web.WEB, web.UPLOADS)
        web.RUNS, web.WEB, web.UPLOADS = Path(tmp) / "runs", Path(tmp) / "runs" / "web", Path(tmp) / "uploads"
        web.RUNS.mkdir(parents=True)
        web._jobs.clear()
        web._proof_cache.clear()
        try:
            client = TestClient(web.app)
            # the one code-only specialist the demo can really run: the delivery forecast as of the scenario date
            run = client.post("/api/run", json={"tool": "assess_delivery_risk", "args": {"as_of": DELIVERY_AS_OF}}).json()
            state = client.get("/api/state").json()
            overview = client.get("/api/overview").json()
            proof = client.get("/api/proof").json()
            results: dict[str, dict] = {}
            for item in state["saved"]:
                rid = item["id"]
                res = client.get(f"/api/results/{rid}").json()
                body = res["result"]["result"]
                if "follow_ups" not in body:
                    d = client.post(f"/api/results/{rid}/drafts", json={})
                    body["follow_ups"] = d.json()["drafts"] if d.status_code == 200 else []
                results[rid] = res
        finally:
            web.RUNS, web.WEB, web.UPLOADS = saved_paths

    state.update(providers=[], running=[], files={"specs": [], "submittals": [], "bids": []}, sealed=0,
                 paid_model={"spent_usd": 0, "cap_usd": 0, "used_here": False})
    _write(out / "data" / "state.json", state)
    _write(out / "data" / "overview.json", overview)
    _write(out / "data" / "proof.json", proof)
    for rid, res in results.items():
        _write(out / "data" / "results" / f"{safe(rid)}.json", res)
        if res["result"]["tool"] == "run_package_review":
            (out / "reports").mkdir(parents=True, exist_ok=True)
            (out / "reports" / f"{safe(rid)}.html").write_text(render(res["result"]), encoding="utf-8")

    # sources: every distinct citation anywhere in the saved results or the overview
    cites: dict[str, dict] = {}
    for obj in [overview, *[r["result"] for r in results.values()]]:
        for c in _citations(obj):
            cites[f"{c['doc_id']}|{int(c['page'])}|{c['quote']}|{c.get('locator') or ''}"] = c
    entries: dict[str, dict] = {}
    pages: dict[str, dict] = {}
    files: dict[str, str] = {}
    pngs = 0
    for key, c in cites.items():
        doc, path = c["doc_id"], idx.get(c["doc_id"])
        if path is not None and is_own(path):
            if path.suffix.lower() == ".pdf":
                entries[key] = _pdf_entry(path, c)
                if doc not in pages:
                    with pymupdf.open(path) as pdf:
                        pages[doc] = {"name": path.name, "pages": pdf.page_count}
                        for n, pg in enumerate(pdf, 1):
                            img = out / "data" / "pages" / f"{doc}-{n}.jpg"
                            img.parent.mkdir(parents=True, exist_ok=True)
                            img.write_bytes(pg.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)).tobytes("jpeg", jpg_quality=72))
                            pngs += 1
            else:
                entries[key] = sources.show(path, int(c["page"]), c["quote"][:600], c.get("locator") or "")
            (out / "files").mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, out / "files" / path.name)
            files[doc] = f"files/{path.name}"
        else:  # a manufacturer's document: only the short cited excerpt, never the page
            n = None
            if path is not None and path.suffix.lower() == ".pdf":
                with pymupdf.open(path) as pdf:
                    n = pdf.page_count
            entries[key] = {"kind": "quote", "name": path.name if path else doc, "pages": n, "page": int(c["page"]),
                            "found": 1, "url": urls.get(doc)}
            if urls.get(doc):
                files[doc] = urls[doc]
    _write(out / "data" / "sources.json", entries)
    _write(out / "data" / "pages.json", pages)

    config = {"files": files, "delivery": {"as_of": DELIVERY_AS_OF, "result_id": run["result_id"]}}
    (out / "demo-shim.js").write_text(SHIM.read_text(encoding="utf-8").replace("__CONFIG__", json.dumps(config)), encoding="utf-8")
    html = web.PAGE.read_text(encoding="utf-8")
    marker = '<script>\n"use strict";'
    assert html.count(marker) == 1
    (out / "index.html").write_text(html.replace(marker, '<script src="demo-shim.js"></script>\n' + marker), encoding="utf-8")
    summary.update(results=len(results), citations=len(cites), page_images=pngs, third_party_excerpts=sum(e["kind"] == "quote" for e in entries.values()))
    return summary
