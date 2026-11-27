"""MCP server: exposes the procurement specialists so Amber (or any MCP client) can call them.

Run:  python -m amber.server            (stdio, for MCP clients such as Claude Desktop / Amber)
      python -m amber.server --http     (streamable HTTP on :8765)

File arguments are paths under AMBER_DATA_ROOT (default: the repo's data/ folder). Paths outside it
are refused, so a caller cannot make the server read arbitrary files.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import anyio
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import __version__
from .llm import LLM
from .schema import ToolResult
from .bids import level_bids as _level_bids
from .delivery import assess_delivery_risk as _assess
from .discovery import find_products as _find
from .followups import draft_follow_ups as _drafts
from .package import run_package_review as _package
from .submittal import check_submittal as _check_submittal

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = Path(os.getenv("AMBER_DATA_ROOT", ROOT / "data")).resolve()

server = MCPServer(
    name="amber-procurement-specialists",
    title="Amber procurement specialists",
    version=__version__,
    instructions=(
        "Procurement specialists for construction. Every answer is JSON with findings; each finding has a "
        "status, a confidence score, citations (document, page, paragraph/row, exact quote) and needs_human. "
        "Findings with needs_human=true must be reviewed by a person before acting."),
)


def _path(p: str) -> str:
    """Resolve a caller-supplied path inside DATA_ROOT, or refuse."""
    cand = (DATA_ROOT / p).resolve() if not Path(p).is_absolute() else Path(p).resolve()
    if DATA_ROOT not in cand.parents and cand != DATA_ROOT:
        raise ToolError(f"path outside the data folder is not allowed: {p}")
    if not cand.exists():
        raise ToolError(f"file not found: {p}")
    return str(cand)


@server.tool(
    name="check_submittal",
    title="Check a submittal against the spec",
    description=(
        "Check a supplier's product submittal (PDF datasheet or submittal package) against a specification "
        "section. For a new project set schedule_path to null; the equipment tag is optional. Returns one finding per requirement: complies / deviates / missing / "
        "unclear, citing the spec paragraph and the submittal page with exact quotes, a confidence score, and "
        "an overall approve / review / reject. Paths are relative to the server's data folder."),
)
async def check_submittal(spec_path: str, submittal_path: str, tag: str = "User project",
                          schedule_path: str | None = "schedules/equipment_schedule.csv",
                          checklist: list[dict[str, Any]] | None = None,
                          provider: str | None = None) -> ToolResult:
    args = (_path(spec_path), _path(submittal_path), tag, _path(schedule_path) if schedule_path else None)
    llm = LLM(provider=provider)
    res = await anyio.to_thread.run_sync(lambda: _check_submittal(*args, checklist=checklist, llm=llm))
    return res


@server.tool(
    name="level_bids",
    title="Level competing bids",
    description=(
        "Line up 2-6 bids for one package against the bid form's scope. For every scope item and bid: included / "
        "excluded / qualified / silent / alternate, with the bid's exact quote. Adds the owner's allowances (or the "
        "bidder's own alternate price) for every gap, ranks the leveled totals, flags commercial risks (escalation, "
        "tariffs, short validity, budget pricing) and lead times, and recommends an award only when it is safe; "
        "otherwise it lays out the options for a person. bids maps a bidder label to a file path."),
)
async def level_bids(bid_form_path: str, bids: dict[str, str], provider: str | None = None) -> ToolResult:
    form = _path(bid_form_path)
    paths = {k: _path(v) for k, v in bids.items()}
    llm = LLM(provider=provider)
    res = await anyio.to_thread.run_sync(lambda: _level_bids(form, paths, llm=llm))
    return res


@server.tool(
    name="assess_delivery_risk",
    title="Forecast delivery risk",
    description=(
        "For each long-lead item group in the equipment schedule: P10/P50/P90 arrival dates, chance of missing "
        "the need date, latest order date for an 80% on-time chance, and actions. Built in code (no model calls) "
        "from cited published lead-time ranges and vendor quotes; dissenting sources are flagged. Optionally "
        "compares bidders' lead times for items not yet ordered (bid_lead_times: {tag_group: {bidder: "
        "{min_weeks, max_weeks, basis, resubmittal}}})."),
)
async def assess_delivery_risk(as_of: str, schedule_path: str = "schedules/equipment_schedule.csv",
                               po_status_path: str = "schedules/po_status.csv",
                               evidence_path: str = "leadtime_sources/leadtime_evidence.csv",
                               bid_lead_times: dict[str, Any] | None = None) -> ToolResult:
    args = (_path(schedule_path), _path(po_status_path), _path(evidence_path), as_of)
    res = await anyio.to_thread.run_sync(lambda: _assess(*args, bid_lead_times=bid_lead_times))
    return res


@server.tool(
    name="run_package_review",
    title="Review a procurement package end to end",
    description=(
        "Runs the specialists together for one package: levels the bids, checks each bidder's product submittal "
        "against the spec, forecasts delivery per bidder (adding a resubmittal cycle where the product deviates), "
        "and returns one comparison table (leveled cost, scope gaps, submittal verdict, P50/P90 arrival, P(late)) "
        "with a recommendation only when it is safe to make one."),
)
async def run_package_review(bid_form_path: str, bids: dict[str, str], spec_path: str, tag: str, tag_group: str,
                             as_of: str, submittals: dict[str, str] | None = None,
                             schedule_path: str = "schedules/equipment_schedule.csv",
                             po_status_path: str = "schedules/po_status.csv",
                             evidence_path: str = "leadtime_sources/leadtime_evidence.csv",
                             provider: str | None = None) -> ToolResult:
    kw = dict(bid_form=_path(bid_form_path), bids={k: _path(v) for k, v in bids.items()}, spec=_path(spec_path),
              tag=tag, tag_group=tag_group, schedule=_path(schedule_path), po_status=_path(po_status_path),
              evidence=_path(evidence_path), as_of=as_of,
              submittals={k: _path(v) for k, v in (submittals or {}).items()}, llm=LLM(provider=provider))
    res = await anyio.to_thread.run_sync(lambda: _package(**kw))
    return res


@server.tool(
    name="find_products",
    title="Find products that could meet the spec",
    description=(
        "Product discovery from documents only: screens every datasheet in the library folder (default: submittals/) "
        "on the key ratings for the equipment tag (for a generator: standby rating, voltage and frequency, cooling at "
        "site ambient, EPA tier, engine speed) with the same verified check as check_submittal. Returns the candidates "
        "ranked likely fits / needs a closer look / does not fit, each rating cited. Never names a product that is "
        "not in a document; a screen is never an approval (every candidate goes to a person)."),
)
async def find_products(tag: str, spec_path: str, library: list[str] | None = None,
                        schedule_path: str = "schedules/equipment_schedule.csv",
                        checklist: list[dict[str, Any]] | None = None, provider: str | None = None) -> ToolResult:
    from .web import _sealed  # held-out test documents stay unread until their one scored run
    sealed = _sealed()
    files = [_path(p) for p in (library or [])] or sorted(
        str(p) for p in (DATA_ROOT / "submittals").glob("*")
        if p.suffix.lower() in (".pdf", ".txt") and f"submittals/{p.name}" not in sealed)
    spec, sched = _path(spec_path), _path(schedule_path)
    if checklist is None:
        from .web import _checklist
        checklist = _checklist(tag)
    llm = LLM(provider=provider)
    try:
        return await anyio.to_thread.run_sync(lambda: _find(spec, tag, sched, files, checklist, llm=llm))
    except ValueError as e:
        raise ToolError(str(e)) from e


@server.tool(
    name="draft_follow_ups",
    title="Draft vendor follow-ups",
    description=(
        "Turn the gaps found by check_submittal, level_bids, assess_delivery_risk or run_package_review into ready-to-send "
        "vendor messages: submittal review comments, bid clarification requests and expediting requests. Pass the JSON "
        "result of one of those tools as `result`. No model is used: every fact in a draft is a verified quote with its "
        "document and page. Drafts are never sent; each is marked for a person to review and send."),
)
async def draft_follow_ups(result: dict[str, Any], project: str = "Project Alpha") -> ToolResult:
    try:
        return _drafts(result, project=project)
    except ValueError as e:
        raise ToolError(str(e)) from e


@server.tool(
    name="run_case",
    title="Run a purchase case file end to end",
    description=(
        "Run (or resume) one purchase as a case file: vendor discovery, record linking, datasheet checks, the bid "
        "comparison, each bid read as the supplier's commitment and reconciled with its datasheet condition by condition, "
        "pre-qualification, cost and arrival ranges, routing of every item (decided / ask the supplier / engineer), draft "
        "questions per supplier, supplier replies read against open items, and the award options with what still blocks "
        "each. State is saved after every step; an interrupted run resumes at the step it was in. Saved model readings are "
        "replayed (no model call) unless live=true. Set replies=true once supplier replies are in the inbox."),
)
async def run_case(case: str = "GEN", replies: bool = False, live: bool = False) -> ToolResult:
    from .case import CASES, as_tool_result, run_case as _run
    if case not in CASES:
        raise ToolError(f"unknown case {case!r}; known: {', '.join(CASES)}")
    cf = await anyio.to_thread.run_sync(lambda: _run(case, replies=replies, live=live))
    return as_tool_result(cf, "case")


@server.tool(
    name="discover_vendors",
    title="Find and rank vendors for a requirement",
    description=(
        "Which vendors could supply this equipment? Candidates come only from the vendor master and the datasheets we "
        "hold (never from model memory). Vendors that cannot supply it are set aside with the record that says why; the "
        "rest are ranked on points a buyer can audit: product fit on five key ratings (datasheet quotes), manufacturer "
        "named by the spec (quoted), bid received and lead time, service distance and on-time history. Code only."),
)
async def discover_vendors(case: str = "GEN") -> ToolResult:
    from .case import as_tool_result, run_case as _run
    cf = await anyio.to_thread.run_sync(lambda: _run(case, until="discover"))
    return as_tool_result(cf, "discover")


@server.tool(
    name="prequalify_vendors",
    title="Pre-qualify vendors against explicit criteria",
    description=(
        "Check each bidder against the spec's supplier criteria and the owner's pre-qualification policy: meets, fails or "
        "needs verification for every criterion, each with the quote it rests on. The model reads the supplier's packet; "
        "code verifies the words on the page and decides. Conflicting records (the packet and the vendor master disagree) "
        "and self-certifications are flagged, never accepted."),
)
async def prequalify_vendors(case: str = "GEN", live: bool = False) -> ToolResult:
    from .case import as_tool_result, run_case as _run
    cf = await anyio.to_thread.run_sync(lambda: _run(case, until="prequalify", live=live))
    return as_tool_result(cf, "prequalify")


def main() -> None:
    if "--http" in sys.argv:
        server.run("streamable-http", host="127.0.0.1", port=int(os.getenv("AMBER_PORT", "8765")))
    else:
        server.run("stdio")


if __name__ == "__main__":
    main()
