"""Web page for project managers: run the specialists from a browser, see every answer with its sources, record a
decision on each item that needs a person, and copy the vendor follow-up drafts.

Run:  python -m amber.web            then open http://127.0.0.1:8000  (--port N to change, --no-browser to not open it)

Local only: the server binds to 127.0.0.1. API keys stay in .env on this machine; the page is only told whether a
provider is available, never a key. Files are read only from the data folder (uploads go to data/uploads/).
Results are saved under runs/web/: the same inputs on the same code open the saved result instead of spending
model tokens again, unless "run again" is chosen.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import threading
import time
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

import anyio
import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response
from starlette.routing import Route

from . import __version__, budget
from . import sources as _sources
from .bids import level_bids
from .delivery import assess_delivery_risk
from .discovery import find_products
from .followups import draft_follow_ups
from .llm import LLM, Meter, _has_key
from .package import run_package_review
from .report import render
from .submittal import check_submittal

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RUNS = ROOT / "runs"
WEB = RUNS / "web"
UPLOADS = DATA / "uploads"
KEYS = ROOT / "eval" / "answer_keys"
PAGE = Path(__file__).with_name("web_index.html")

MAX_UPLOAD = 40 * 1024 * 1024
UPLOAD_EXT = {".pdf", ".txt"}
UPLOAD_KINDS = {"submittals", "bids", "specs"}
PROVIDERS = ("groq", "openrouter", "cerebras", "ollama")  # the paid provider is never offered on this page
CHECKLISTS = {"26 32 13": "genset_requirements.json", "26 33 53": "ups_requirements.json"}
RESULT_ID = re.compile(r"^(runs|web):[A-Za-z0-9_.\-]{1,80}$")
REVIEW_STATUSES = {"agree", "complies", "deviates", "missing", "unclear"}

PRESET = {
    "label": "Project Alpha: standby generators (bid package BP-26-04)",
    "bid_form": "bids/00_bid_form_generators.pdf",
    "bids": {"B1": "bids/B1_northline_power.pdf", "B2": "bids/B2_tidewater_generator.pdf",
             "B3": "bids/B3_keystone_energy.pdf", "B4": "bids/B4_ridgeway_power_email.txt"},
    "submittals": {"B2": "submittals/cummins_DQKAB_submittal_CSDG.pdf", "B3": "submittals/kohler_KD2000_G5-626.pdf"},
    "spec": "specs/project_alpha/26_32_13_engine_generators_ALPHA.pdf",
    "tag": "GEN-A", "tag_group": "GEN", "as_of": "2026-12-01",
}
SCHEDULE, PO_STATUS, EVIDENCE = "schedules/equipment_schedule.csv", "schedules/po_status.csv", "leadtime_sources/leadtime_evidence.csv"

_jobs: dict[str, dict[str, Any]] = {}
_src_index: dict[str, Path] = {}
_lock = threading.Lock()


class BadRequest(ValueError):
    pass


# ---------- files ----------

def _data_path(p: str) -> Path:
    """A caller-supplied path inside the data folder, or refuse."""
    if not isinstance(p, str) or not p:
        raise BadRequest("a file is required")
    cand = (DATA / p).resolve()
    if DATA.resolve() not in cand.parents:
        raise BadRequest(f"only files in the data folder can be used: {p}")
    if not cand.is_file():
        raise BadRequest(f"file not found: {p} (see README: fetch_data.py downloads the public documents)")
    return cand


def _rel(p: Path) -> str:
    return p.resolve().relative_to(DATA.resolve()).as_posix()


def _list(folder: str, exts=(".pdf", ".txt")) -> list[str]:
    base = DATA / folder
    files = [p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in exts] if base.exists() else []
    return sorted(_rel(p) for p in files)


def _sealed() -> set[str]:
    """Held-out test documents whose one scored run has not happened yet. They stay off this page until it has,
    so the accuracy figures in the README stay honest (eval_submittal.py --final makes that run)."""
    out = set()
    for k in KEYS.glob("[GU][0-9]*.json"):
        case = json.loads(k.read_text(encoding="utf-8"))
        if case.get("split") == "heldout" and not (RUNS / k.name).exists():
            out.add(Path(case["submittal"]).relative_to("data").as_posix())
    return out


def _schedule() -> list[dict]:
    import csv
    with open(DATA / SCHEDULE, encoding="utf-8") as fh:
        return [{"tag": r["tag"], "item": r["item"], "spec_section": r["spec_section"], "need_on_site": r["need_on_site"]}
                for r in csv.DictReader(fh)]


def _tag_group(tag: str) -> str:
    return tag.split("-")[0]


def _checklist(tag: str) -> list[dict] | None:
    row = next((r for r in _schedule() if r["tag"] == tag), None)
    name = CHECKLISTS.get((row or {}).get("spec_section", ""))
    if not name:
        return None  # the specialist reads the requirements out of the spec itself
    return json.loads((KEYS / name).read_text(encoding="utf-8"))["requirements"]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---------- providers ----------

def _ollama_up() -> bool:
    try:
        return httpx.get("http://127.0.0.1:11434/api/tags", timeout=0.6).status_code == 200
    except httpx.HTTPError:
        return False


def _providers() -> list[dict]:
    names = {"groq": "Groq (free tier)", "openrouter": "OpenRouter (free)", "cerebras": "Cerebras (free)",
             "ollama": "This laptop (Ollama, offline)"}
    out = []
    for p in PROVIDERS:
        ok = _ollama_up() if p == "ollama" else _has_key(p)
        out.append({"id": p, "name": names[p], "available": ok})
    return out


def _llm(provider: str | None) -> LLM:
    if provider not in (None, "", *PROVIDERS):
        raise BadRequest(f"provider not offered here: {provider}")
    return LLM(provider=provider or None, meter=Meter())


# ---------- tools ----------

def _prepare(tool: str, a: dict) -> tuple[dict, list[Path]]:
    """Validate the form and resolve paths. Returns (keyword arguments, files whose contents define the result)."""
    if tool == "check_submittal":
        if a.get("submittal") in _sealed():
            raise BadRequest("this datasheet is a held-out test document: it is opened only by the one final scored run")
        spec, sub, sched = _data_path(a.get("spec")), _data_path(a.get("submittal")), _data_path(SCHEDULE)
        tag = a.get("tag") or ""
        if tag not in {r["tag"] for r in _schedule()}:
            raise BadRequest(f"unknown equipment tag: {tag}")
        return dict(spec_path=str(spec), submittal_path=str(sub), tag=tag, schedule_path=str(sched),
                    checklist=_checklist(tag)), [spec, sub, sched]
    if tool == "level_bids":
        form = _data_path(a.get("bid_form"))
        bids = {k: _data_path(v) for k, v in (a.get("bids") or {}).items() if v}
        if not 2 <= len(bids) <= 6:
            raise BadRequest("choose 2 to 6 bids")
        return dict(form_path=str(form), bid_paths={k: str(v) for k, v in bids.items()}), [form, *bids.values()]
    if tool == "find_products":
        tag = a.get("tag") or ""
        row = next((r for r in _schedule() if r["tag"] == tag), None)
        if not row:
            raise BadRequest(f"unknown equipment tag: {tag}")
        spec = _data_path(a.get("spec"))
        sealed = _sealed()
        lib = [_data_path(f) for f in _list("submittals") + _list("uploads/submittals") if f not in sealed]
        checklist = _checklist(tag)
        if not checklist:
            raise BadRequest(f"product discovery is set up for generators and UPS; not yet for {row['item']}")
        return dict(spec_path=str(spec), tag=tag, schedule_path=str(_data_path(SCHEDULE)), library=[str(p) for p in lib],
                    checklist=checklist), [spec, _data_path(SCHEDULE), *lib]
    if tool == "assess_delivery_risk":
        files = [_data_path(SCHEDULE), _data_path(PO_STATUS), _data_path(EVIDENCE)]
        as_of = _date(a.get("as_of"))
        return dict(schedule_path=str(files[0]), po_path=str(files[1]), evidence_path=str(files[2]), as_of=as_of), files
    if tool == "run_package_review":
        form = _data_path(a.get("bid_form"))
        bids = {k: _data_path(v) for k, v in (a.get("bids") or {}).items() if v}
        if set((a.get("submittals") or {}).values()) & _sealed():
            raise BadRequest("a held-out test document is opened only by the one final scored run")
        subs = {k: _data_path(v) for k, v in (a.get("submittals") or {}).items() if v}
        if not 2 <= len(bids) <= 6:
            raise BadRequest("choose 2 to 6 bids")
        if set(subs) - set(bids):
            raise BadRequest("a product submittal was given for a bidder with no bid")
        spec = _data_path(a.get("spec"))
        tag = a.get("tag") or ""
        if tag not in {r["tag"] for r in _schedule()}:
            raise BadRequest(f"unknown equipment tag: {tag}")
        fixed = [_data_path(SCHEDULE), _data_path(PO_STATUS), _data_path(EVIDENCE)]
        kw = dict(bid_form=str(form), bids={k: str(v) for k, v in bids.items()}, spec=str(spec), tag=tag,
                  tag_group=_tag_group(tag), schedule=str(fixed[0]), po_status=str(fixed[1]), evidence=str(fixed[2]),
                  as_of=_date(a.get("as_of")), submittals={k: str(v) for k, v in subs.items()}, checklist=_checklist(tag))
        return kw, [form, *bids.values(), *subs.values(), spec, *fixed]
    raise BadRequest(f"unknown tool: {tool}")


def _date(s: Any) -> str:
    try:
        return datetime.strptime(str(s), "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise BadRequest("date must be YYYY-MM-DD") from None


def _call(tool: str, kw: dict, llm: LLM | None):
    if tool == "check_submittal":
        return check_submittal(kw["spec_path"], kw["submittal_path"], kw["tag"], kw["schedule_path"],
                               checklist=kw["checklist"], llm=llm)
    if tool == "level_bids":
        return level_bids(kw["form_path"], kw["bid_paths"], llm=llm)
    if tool == "assess_delivery_risk":
        return assess_delivery_risk(kw["schedule_path"], kw["po_path"], kw["evidence_path"], kw["as_of"])
    if tool == "find_products":
        return find_products(kw["spec_path"], kw["tag"], kw["schedule_path"], kw["library"], kw["checklist"], llm=llm)
    return run_package_review(**kw, llm=llm)


def _cache_key(tool: str, a: dict, files: list[Path], provider: str | None) -> str:
    ident = {"tool": tool, "args": a, "files": {_rel(f): _sha(f) for f in files},
             "provider": provider or "default", "code": __version__}
    return hashlib.sha256(json.dumps(ident, sort_keys=True).encode()).hexdigest()[:20]


def _label(tool: str, a: dict) -> str:
    if tool == "check_submittal":
        return f"{Path(a['submittal']).stem} vs {a['tag']}"
    if tool == "level_bids":
        return f"{len(a['bids'])} bids on {Path(a['bid_form']).stem}"
    if tool == "assess_delivery_risk":
        return f"all long-lead items, as of {a['as_of']}"
    if tool == "find_products":
        return f"products in the library for {a['tag']}"
    return f"{a['tag']}: {len(a['bids'])} bids, {len(a.get('submittals') or {})} submittals"


def _index() -> dict:
    f = WEB / "index.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def _save(key: str, meta: dict, result: dict) -> None:
    WEB.mkdir(parents=True, exist_ok=True)
    (WEB / f"{key}.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    with _lock:
        idx = _index()
        idx[key] = meta
        (WEB / "index.json").write_text(json.dumps(idx, indent=1), encoding="utf-8")


def _worker(job: dict, tool: str, kw: dict, llm: LLM | None, key: str, meta: dict) -> None:
    try:
        res = _call(tool, kw, llm)
        out = res.model_dump(mode="json")
        if tool not in ("run_package_review", "find_products") and out.get("findings"):
            out["result"]["follow_ups"] = [f.data for f in draft_follow_ups(out).findings]
        meta.update(finished=_now(), seconds=round(time.time() - job["t0"]), cost_usd=res.run.cost_usd,
                    needs_human=len(res.needs_human), findings=len(res.findings))
        _save(key, meta, out)
        job.update(state="done", result_id=f"web:{key}")
    except Exception as e:  # noqa: BLE001 - shown to the person, never swallowed
        job.update(state="error", error=f"{type(e).__name__}: {e}")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------- results ----------

def _result_file(rid: str) -> Path:
    if not RESULT_ID.match(rid or ""):
        raise BadRequest("bad result id")
    src, name = rid.split(":", 1)
    f = (RUNS if src == "runs" else WEB) / f"{name}.json"
    if not f.is_file() or name == "index":
        raise BadRequest("result not found")
    return f


def _load(rid: str) -> dict:
    return json.loads(_result_file(rid).read_text(encoding="utf-8"))


def _reviews_file(rid: str) -> Path:
    _result_file(rid)
    return WEB / "reviews" / (rid.replace(":", "__") + ".json")


def _saved() -> list[dict]:
    out = []
    for key, m in _index().items():
        if (WEB / f"{key}.json").exists():
            out.append(dict(m, id=f"web:{key}", reviewed=_reviewed(f"web:{key}")))
    for f in sorted(RUNS.glob("*.json")):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if "tool" not in r or "findings" not in r:
            continue
        R = r.get("result") or {}
        what = R.get("package") or (f"{R.get('submittal', '')} vs {R.get('tag', '')}" if R.get("tag") else "")
        out.append({"id": f"runs:{f.stem}", "tool": r["tool"], "label": f"{f.stem}: {what}".strip(": "),
                    "finished": datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds"),
                    "findings": len(r["findings"]), "needs_human": len(r.get("needs_human") or []),
                    "cost_usd": round(sum(m.get("cost_usd") or 0 for m in (r.get("run") or {}).get("models") or []), 4),
                    "source": "command line", "reviewed": _reviewed(f"runs:{f.stem}")})
    return sorted(out, key=lambda m: m.get("finished") or "", reverse=True)


def _reviewed(rid: str) -> int:
    f = WEB / "reviews" / (rid.replace(":", "__") + ".json")
    try:
        return len(json.loads(f.read_text(encoding="utf-8"))) if f.exists() else 0
    except (json.JSONDecodeError, OSError):
        return 0


def _source_path(doc_id: str) -> Path | None:
    global _src_index
    if doc_id not in _src_index:  # new upload, or a held-out document whose final run has now happened
        _src_index = _sources.index(DATA, exclude=_sealed())
    return _src_index.get(doc_id)


# ---------- HTTP ----------

def _err(e: Exception, code: int = 400) -> JSONResponse:
    return JSONResponse({"error": str(e)}, status_code=code)


async def page(_: Request) -> HTMLResponse:
    return HTMLResponse(PAGE.read_text(encoding="utf-8"), headers={"Cache-Control": "no-store"})


async def state(_: Request) -> JSONResponse:
    running = [{"id": j, "tool": v["tool"], "label": v["label"]} for j, v in _jobs.items() if v["state"] == "running"]
    return JSONResponse({
        "version": __version__, "providers": _providers(), "running": running, "preset": PRESET,
        "paid_model": {"spent_usd": round(budget.spent_usd(), 2), "cap_usd": budget.cap_usd(), "used_here": False},
        "files": {"specs": _list("specs", (".pdf",)) + _list("uploads/specs"),
                  "submittals": [f for f in _list("submittals") if f not in _sealed()] + _list("uploads/submittals"),
                  "bids": _list("bids") + _list("uploads/bids")},
        "sealed": len(_sealed()),
        "tags": _schedule(), "saved": _saved(),
    })


async def upload(req: Request) -> JSONResponse:
    try:
        form = await req.form(max_files=1, max_part_size=MAX_UPLOAD)
        kind, f = form.get("kind"), form.get("file")
        if kind not in UPLOAD_KINDS or f is None or not hasattr(f, "read"):
            raise BadRequest("choose a file and what it is (submittal, bid or spec)")
        name = re.sub(r"[^A-Za-z0-9_.\-]+", "_", Path(f.filename or "upload").name).strip("._")[:80] or "upload"
        if Path(name).suffix.lower() not in UPLOAD_EXT:
            raise BadRequest("only PDF or .txt files")
        data = await f.read()
        if not data or len(data) > MAX_UPLOAD:
            raise BadRequest("file is empty or larger than 40 MB")
        if name.lower().endswith(".pdf") and not data.startswith(b"%PDF"):
            raise BadRequest("that file is not a PDF")
        dest = UPLOADS / kind
        dest.mkdir(parents=True, exist_ok=True)
        (dest / name).write_bytes(data)
        return JSONResponse({"path": f"uploads/{kind}/{name}"})
    except BadRequest as e:
        return _err(e)


async def run(req: Request) -> JSONResponse:
    try:
        body = await req.json()
        tool, a, provider = body.get("tool"), body.get("args") or {}, body.get("provider") or None
        kw, files = _prepare(tool, a)
        uses_model = tool != "assess_delivery_risk"
        key = _cache_key(tool, a, files, provider if uses_model else None)
        if not body.get("force") and (WEB / f"{key}.json").exists():
            return JSONResponse({"result_id": f"web:{key}", "cached": True})
        meta = {"tool": tool, "label": _label(tool, a), "args": a, "provider": provider or "default",
                "started": _now(), "source": "web page"}
        if not uses_model:  # code only, instant
            job = {"t0": time.time()}
            _worker(job, tool, kw, None, key, meta)
            if job.get("state") == "error":
                return _err(RuntimeError(job["error"]), 500)
            return JSONResponse({"result_id": job["result_id"], "cached": False})
        if any(v["state"] == "running" for v in _jobs.values()):
            raise BadRequest("another run is still going: free model tiers allow one at a time")
        llm = _llm(provider)
        jid = uuid.uuid4().hex[:12]
        job = {"state": "running", "tool": tool, "label": meta["label"], "t0": time.time(), "meter": llm.meter,
               "provider": llm.provider}
        _jobs[jid] = job
        threading.Thread(target=_worker, args=(job, tool, kw, llm, key, meta), daemon=True).start()
        return JSONResponse({"job": jid})
    except BadRequest as e:
        return _err(e)
    except json.JSONDecodeError:
        return _err(BadRequest("bad request"))


async def job_status(req: Request) -> JSONResponse:
    job = _jobs.get(req.path_params["jid"])
    if not job:
        return _err(BadRequest("no such run"), 404)
    steps = list(job["meter"].steps)
    return JSONResponse({"state": job["state"], "seconds": round(time.time() - job["t0"]), "calls": len(steps),
                         "last": (steps[-1].get("purpose") if steps else None), "provider": job["provider"],
                         "failed_calls": sum(1 for s in steps if not s.get("ok", True)),
                         "result_id": job.get("result_id"), "error": job.get("error")})


async def result(req: Request) -> JSONResponse:
    try:
        rid = req.path_params["rid"]
        res = _load(rid)
        rf = _reviews_file(rid)
        reviews = json.loads(rf.read_text(encoding="utf-8")) if rf.exists() else {}
        meta = _index().get(rid.split(":", 1)[1], {}) if rid.startswith("web:") else {}
        return JSONResponse({"id": rid, "result": res, "reviews": reviews, "meta": meta})
    except BadRequest as e:
        return _err(e, 404)


async def source(req: Request) -> JSONResponse:
    """A cited page with the quote highlighted (PDF), or the text / table with the quote or row marked."""
    q = req.query_params
    doc = q.get("doc", "")
    path = _source_path(doc) if re.fullmatch(r"[a-z0-9-]{1,48}", doc) else None
    if not path:
        return _err(BadRequest("that document is not available on this page"), 404)
    try:
        page_no = int(q.get("page", "1"))
    except ValueError:
        page_no = 1
    out = await anyio.to_thread.run_sync(lambda: _sources.show(path, page_no, q.get("q", "")[:600], q.get("loc", "")[:120]))
    out["doc_id"] = doc
    return JSONResponse(out)


MEDIA = {".pdf": "application/pdf", ".csv": "text/csv; charset=utf-8", ".txt": "text/plain; charset=utf-8",
         ".md": "text/plain; charset=utf-8", ".eml": "text/plain; charset=utf-8"}


async def original(req: Request) -> Response:
    """The original document, opened in the browser's own viewer (only documents the citations can name)."""
    doc = req.path_params["doc"]
    path = _source_path(doc) if re.fullmatch(r"[a-z0-9-]{1,48}", doc) else None
    if not path:
        return _err(BadRequest("that document is not available on this page"), 404)
    return FileResponse(path, media_type=MEDIA.get(path.suffix.lower(), "application/octet-stream"),
                        headers={"Content-Disposition": "inline", "X-Content-Type-Options": "nosniff"})


async def overview(_: Request) -> JSONResponse:
    """The project at a glance: delivery risk for every long-lead group (code only, instant, no tokens)."""
    res = await anyio.to_thread.run_sync(lambda: assess_delivery_risk(
        str(DATA / SCHEDULE), str(DATA / PO_STATUS), str(DATA / EVIDENCE), PRESET["as_of"]))
    rows = [f.data | {"citations": [c.model_dump() for c in f.citations]} for f in res.findings if f.data.get("arrival")]
    return JSONResponse({"as_of": PRESET["as_of"], "rows": rows})


async def report(req: Request) -> HTMLResponse:
    try:
        res = _load(req.path_params["rid"])
    except BadRequest as e:
        return HTMLResponse(str(e), status_code=404)
    if res.get("tool") != "run_package_review":
        return HTMLResponse("the printable report is for package reviews", status_code=400)
    return HTMLResponse(render(res))


async def drafts(req: Request) -> JSONResponse:
    try:
        rid = req.path_params["rid"]
        res = _load(rid)
        project = (await req.json()).get("project") or "Project Alpha"
        out = draft_follow_ups(res, project=str(project)[:80])
        return JSONResponse({"drafts": [f.data | {"citations": [c.model_dump() for c in f.citations]} for f in out.findings]})
    except (BadRequest, ValueError) as e:
        return _err(e)


async def review(req: Request) -> JSONResponse:
    """A person's decision on one finding: agree, or set the right status, with a note. Kept beside the result."""
    try:
        rid = req.path_params["rid"]
        body = await req.json()
        fid, decision, note = body.get("finding"), body.get("decision"), str(body.get("note") or "")[:1000]
        res = _load(rid)
        if fid not in {f["id"] for f in res["findings"]}:
            raise BadRequest("no such finding")
        rf = _reviews_file(rid)
        rf.parent.mkdir(parents=True, exist_ok=True)
        with _lock:
            reviews = json.loads(rf.read_text(encoding="utf-8")) if rf.exists() else {}
            if decision in (None, "", "clear"):
                reviews.pop(fid, None)
            elif decision in REVIEW_STATUSES:
                reviews[fid] = {"decision": decision, "note": note, "at": _now()}
            else:
                raise BadRequest("decision must be agree, complies, deviates, missing or unclear")
            rf.write_text(json.dumps(reviews, indent=1), encoding="utf-8")
        return JSONResponse({"reviews": reviews})
    except BadRequest as e:
        return _err(e)


app = Starlette(routes=[
    Route("/", page), Route("/api/state", state), Route("/api/upload", upload, methods=["POST"]),
    Route("/api/run", run, methods=["POST"]), Route("/api/jobs/{jid}", job_status),
    Route("/api/source", source), Route("/api/overview", overview), Route("/api/file/{doc}", original),
    Route("/api/results/{rid}", result), Route("/api/results/{rid}/report", report),
    Route("/api/results/{rid}/drafts", drafts, methods=["POST"]), Route("/api/results/{rid}/review", review, methods=["POST"]),
])


def main() -> None:
    import uvicorn
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8000
    url = f"http://127.0.0.1:{port}"
    print(f"Amber procurement specialists: {url}  (Ctrl+C to stop)")
    if "--no-browser" not in sys.argv:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
