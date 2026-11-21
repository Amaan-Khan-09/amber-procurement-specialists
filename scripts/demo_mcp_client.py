"""Call the Amber MCP server the way Amber (or any MCP client) would: over stdio, discovering the tools first.

usage: python scripts/demo_mcp_client.py            # lists tools and runs assess_delivery_risk (no model calls, free)
       python scripts/demo_mcp_client.py --submittal G2   # also runs check_submittal on a labelled case (uses the model)
"""
import argparse
import json
import sys
from pathlib import Path

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parents[1]


def payload(result) -> dict:
    """MCP 2.x returns structured content when the server declares an output schema; fall back to text."""
    sc = getattr(result, "structured_content", None)
    if sc:
        if "tool" in sc:  # the payload itself
            return sc
        if isinstance(sc.get("result"), dict) and "tool" in sc["result"]:  # wrapped by the SDK
            return sc["result"]
    return json.loads(result.content[0].text)


async def main(case: str | None) -> None:
    params = StdioServerParameters(command=sys.executable, args=["-m", "amber.server"], cwd=str(ROOT))
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            print("Tools the server offers:")
            for t in (await s.list_tools()).tools:
                print(f"  - {t.name}: {(t.description or '').split('.')[0]}.")

            bids = {"GEN": {"B2": {"min_weeks": 50, "max_weeks": 54, "basis": "after_submittal_approval"},
                            "B3": {"min_weeks": 68, "max_weeks": 74, "basis": "after_order"}}}
            print("\nCalling assess_delivery_risk (as of 2026-12-01) ...")
            res = payload(await s.call_tool("assess_delivery_risk", {"as_of": "2026-12-01", "bid_lead_times": bids}))
            print(f"{'item group':12} {'scenario':24} {'need':11} {'typical':11} {'latest-likely':13} {'chance late':>11}")
            for row in res["result"]["ranked"]:
                print(f"{row['tag_group']:12} {row['scenario']:24} {row['need']:11} {row['P50']:11} {row['P90']:13} {row['p_late']:>10.0%}")
            top = next(f for f in res["findings"] if f["data"].get("p_late", 0) >= 0.5)
            print("\nFirst high-risk finding:", top["claim"])
            for c in top["citations"][:2]:
                print(f"  source: {c['doc_id']} {c.get('locator', '')} -> \"{c['quote'][:90]}\"")
            print("  action:", top["data"]["actions"][0])

            if case:
                key = json.loads((ROOT / f"eval/answer_keys/{case}.json").read_text(encoding="utf-8"))
                checklist = json.loads((ROOT / "eval/answer_keys/genset_requirements.json").read_text(encoding="utf-8"))["requirements"]
                strip = lambda p: str(Path(p).relative_to("data")) if p.startswith("data") else p
                print(f"\nCalling check_submittal on {case} ({key['submittal']}) ...")
                res = payload(await s.call_tool("check_submittal", {
                    "spec_path": strip(key["spec"]), "submittal_path": strip(key["submittal"]), "tag": key["tag"],
                    "checklist": checklist}))
                print("overall:", res["result"]["overall"], res["result"]["summary"])
                for f in res["findings"][:5]:
                    print(f"  {f['status']:9} {f['confidence']:.2f}  {f['claim'][:70]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--submittal", help="also run check_submittal on this answer-key case, e.g. G2")
    anyio.run(main, ap.parse_args().submittal)
