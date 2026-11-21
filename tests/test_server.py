"""The MCP server starts over stdio, lists its tools, and refuses paths outside the data folder."""
import sys
from pathlib import Path

import anyio
import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parents[1]


async def _with_session(fn):
    params = StdioServerParameters(command=sys.executable, args=["-m", "amber.server"], cwd=str(ROOT))
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            return await fn(s)


def test_lists_check_submittal_with_schema():
    async def go(s):
        return await s.list_tools()
    tools = {t.name: t for t in anyio.run(_with_session, go).tools}
    assert "check_submittal" in tools
    props = tools["check_submittal"].input_schema["properties"]
    assert {"spec_path", "submittal_path", "tag"} <= set(props)


def test_refuses_paths_outside_data_folder():
    async def go(s):
        return await s.call_tool("check_submittal", {"spec_path": "../pyproject.toml",
                                                     "submittal_path": "x.pdf", "tag": "GEN-A"})
    res = anyio.run(_with_session, go)
    assert res.is_error
    assert "outside the data folder" in str(res.content)
