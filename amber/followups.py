"""draft_follow_ups: turn the gaps the specialists found into ready-to-send vendor messages, the way a procurement
engineer (or Amber) follows up.

No model is involved: every sentence is filled from a finding that already exists, and every fact in it is a verified
quote with its document and page. So a draft can never contain anything the source documents do not say. Drafts are
never sent: each one is handed to a person to review and send.

Input: the JSON result of check_submittal, level_bids, assess_delivery_risk or run_package_review.
"""
from __future__ import annotations

from collections import defaultdict

from .schema import Citation, Finding, RunInfo, ToolResult, Verdict

ASK_SUBMITTAL = {
    "deviates": "The submittal does not meet this requirement. Please confirm a compliant alternative, or submit a formal "
                "deviation request with the reason and any cost or schedule impact.",
    "missing": "We could not find this in the submittal. Please provide the data sheet section or a written confirmation.",
    "unclear": "The submittal is not clear on this point. Please confirm exactly what will be supplied for this project.",
}
ASK_BID = {
    "excluded": "Your bid excludes this item. Please price it as an add, or confirm it is provided by others.",
    "qualified": "Your bid offers this item short of the requirement. Please confirm a compliant offer and any price change.",
    "silent": "Your bid does not mention this item. Please confirm whether it is included in your base price.",
    "unclear": "Your bid is not clear on this item. Please confirm whether it is included in your base price.",
    "alternate": "This item is priced as an alternate. Please confirm the alternate price is firm for the same validity period.",
}


def _cite_line(c: dict) -> str:
    loc = f", {c['locator']}" if c.get("locator") else ""
    scan = " (scanned page)" if c.get("ocr") else ""
    return f'{c["doc_id"]} p.{c["page"]}{loc}{scan}: "{c["quote"][:160]}"'


def _submittal_items(findings: list[dict], default_doc: str | None = None, spec_prefix: str = "26-") -> dict[str, list[dict]]:
    """Group submittal gaps by the submittal document they concern ('missing' items cite no submittal page, so they
    go to the submittal the check was run on)."""
    out: dict[str, list[dict]] = defaultdict(list)
    for f in findings:
        if f.get("status") not in ASK_SUBMITTAL or "req_id" not in (f.get("data") or {}):
            continue
        spec = [c for c in f.get("citations", []) if c["doc_id"].startswith(spec_prefix)]
        sub = [c for c in f.get("citations", []) if not c["doc_id"].startswith(spec_prefix)
               and not c["doc_id"].startswith("equipment-schedule")]
        doc = sub[0]["doc_id"] if sub else (default_doc or "the submittal")
        out[doc].append({"f": f, "spec": spec, "sub": sub})
    return out


def _submittal_draft(doc: str, items: list[dict], project: str, tag: str | None) -> dict:
    lines = [f"Subject: {project}{' ' + tag if tag else ''} - submittal review comments ({len(items)} items)", "",
             "Hello,", "", f"We have reviewed your submittal ({doc}) against the project specification. "
             "Please respond to each item below.", ""]
    cites: list[dict] = []
    for n, it in enumerate(items, 1):
        f = it["f"]
        loc = (f.get("data") or {}).get("locator") or ""
        lines.append(f"{n}. {f['claim']}" + (f" (spec {loc})" if loc else ""))
        for c in it["spec"][:1]:
            lines.append(f"   Specification: {_cite_line(c)}")
        for c in it["sub"][:1]:
            lines.append(f"   Your submittal: {_cite_line(c)}")
        lines.append(f"   Request: {ASK_SUBMITTAL[f['status']]}")
        lines.append("")
        cites += it["spec"][:1] + it["sub"][:1]
    lines += ["Thank you.", f"Procurement, {project}"]
    return {"to": f"Supplier of {doc}", "kind": "submittal_review", "subject": lines[0][9:], "body": "\n".join(lines[2:]),
            "items": len(items), "citations": cites}


def _bid_drafts(lb: dict, findings: list[dict], project: str) -> list[dict]:
    scope = {s["id"]: s["item"] for s in lb.get("scope", [])}
    uncovered = {u["id"] for u in lb.get("uncovered_scope") or []}
    by_bid: dict[str, list[dict]] = defaultdict(list)
    for f in findings:
        d = f.get("data") or {}
        if d.get("scope_status") in ASK_BID and d.get("bid"):
            by_bid[d["bid"]].append(f)
    drafts = []
    for bid, fs in sorted(by_bid.items()):
        product = (lb.get("products") or {}).get(bid) or ""
        lines = ["Hello,", "", f"Thank you for your proposal for {lb.get('package') or 'this package'}"
                 + (f" ({product})" if product else "") + ". Before we can compare bids on the same scope, please "
                 "clarify the items below.", ""]
        cites = []
        n = 0
        for n, f in enumerate(sorted(fs, key=lambda x: x["data"]["scope_id"]), 1):
            sid, st = f["data"]["scope_id"], f["data"]["scope_status"]
            lines.append(f"{n}. {sid} {scope.get(sid, '')}")
            for c in f.get("citations", [])[:1]:
                lines.append(f"   Your proposal: {_cite_line(c)}")
            lines.append(f"   Request: {ASK_BID[st]}" + (" No bid we received includes this item, so we are asking every "
                                                         "bidder to price it." if sid in uncovered else ""))
            lines.append("")
            cites += f.get("citations", [])[:1]
        for t in ((lb.get("terms") or {}).get(bid) or []):
            if t.get("risk") in ("unquantified_cost", "short_validity", "not_firm") and t.get("citation"):
                ask = {"unquantified_cost": "Please confirm a firm price or a cap on this adjustment.",
                       "short_validity": "Please extend the price validity to at least 60 days.",
                       "not_firm": "Please confirm this as a firm bid against the bid form."}[t["risk"]]
                n += 1
                lines += [f"{n}. Commercial term: {t.get('note', '')}", f"   Your proposal: {_cite_line(t['citation'])}",
                          f"   Request: {ask}", ""]
                cites.append(t["citation"])
        lines += ["Thank you.", f"Procurement, {project}"]
        drafts.append({"to": f"Bidder {bid}", "kind": "bid_clarification",
                       "subject": f"{project} - {lb.get('package') or 'bid'}: clarification request",
                       "body": "\n".join(lines), "items": len(fs), "citations": cites})
    return drafts


def _delivery_drafts(findings: list[dict], project: str) -> list[dict]:
    drafts = []
    for f in findings:
        d = f.get("data") or {}
        if d.get("risk") != "high" or d.get("scenario") != "as ordered":
            continue
        a = d["arrival"]
        body = "\n".join([
            "Hello,", "", f"For {d['tag_group']} ({', '.join(d.get('tags') or [])}) on {project}, we need the equipment on site by "
            f"{d['need_on_site']}. Published lead times for this class and your quoted lead time put the likely arrival around "
            f"{a['P50']} (range {a['P10']} to {a['P90']}).", "",
            "Please confirm in writing: your reserved production slot, the committed ship date, and any option to expedite.", "",
            "Thank you.", f"Procurement, {project}"])
        drafts.append({"to": f"Supplier of {d['tag_group']}", "kind": "expedite_request",
                       "subject": f"{project} - {d['tag_group']}: confirm production slot and ship date", "body": body,
                       "items": 1, "citations": f.get("citations", [])[:3]})
    return drafts


def draft_follow_ups(result: dict, project: str = "Project Alpha") -> ToolResult:
    tool = result.get("tool")
    findings = result.get("findings") or []
    R = result.get("result") or {}
    drafts: list[dict] = []
    if tool == "check_submittal":
        for doc, items in _submittal_items(findings, R.get("submittal")).items():
            drafts.append(_submittal_draft(doc, items, project, R.get("tag")))
    elif tool == "level_bids":
        drafts += _bid_drafts(R, findings, project)
    elif tool == "assess_delivery_risk":
        drafts += _delivery_drafts(findings, project)
    elif tool == "run_package_review":
        parts = R.get("parts") or {}
        lb_f = [dict(f, id=f["id"].split("/", 1)[-1]) for f in findings if f["id"].startswith("level_bids/")]
        drafts += _bid_drafts(parts.get("level_bids") or {}, lb_f, project)
        for b in (parts.get("submittals") or {}):
            sub_f = [f for f in findings if f["id"].startswith(f"submittal:{b}/")]
            for doc, items in _submittal_items(sub_f, (parts["submittals"][b] or {}).get("submittal")).items():
                drafts.append(_submittal_draft(doc, items, project, (parts["submittals"][b] or {}).get("tag")))
        drafts += _delivery_drafts([f for f in findings if f["id"].startswith("delivery/")], project)
    else:
        raise ValueError(f"not a specialist result this tool can read (tool={tool!r})")

    out = []
    for i, d in enumerate(drafts, 1):
        cites = [Citation(**c) for c in d["citations"]]
        out.append(Finding(id=f"F-draft-{i}", claim=f"draft to {d['to']}: {d['subject']}", status=Verdict.unclear,
                           confidence=0.6, citations=cites, needs_human=True,
                           why="a draft for a person to review and send; every fact in it is a verified quote",
                           data={k: d[k] for k in ("to", "kind", "subject", "body", "items")}))
    res = ToolResult(tool="draft_follow_ups", findings=out,
                     result={"drafts": len(out), "source_tool": tool,
                             "note": "Drafts only. Nothing is sent. Every fact quoted is from a verified citation."},
                     run=RunInfo(models=[], latency_ms=0))
    return res.finalize()
