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
        "section, for one equipment tag. Returns one finding per requirement: complies / deviates / missing / "
        "unclear, citing the spec paragraph and the submittal page with exact quotes, a confidence score, and "
        "an overall approve / review / reject. Paths are relative to the server's data folder."),
)
async def check_submittal(spec_path: str, submittal_path: str, tag: str,
                          schedule_path: str = "schedules/equipment_schedule.csv",
                          checklist: list[dict[str, Any]] | None = None,
                          provider: str | None = None) -> dict[str, Any]:
    args = (_path(spec_path), _path(submittal_path), tag, _path(schedule_path))
    llm = LLM(provider=provider)
    res = await anyio.to_thread.run_sync(lambda: _check_submittal(*args, checklist=checklist, llm=llm))
    return res.model_dump(mode="json")


def main() -> None:
    if "--http" in sys.argv:
        server.run("streamable-http", host="127.0.0.1", port=int(os.getenv("AMBER_PORT", "8765")))
    else:
        server.run("stdio")


if __name__ == "__main__":
    main()
