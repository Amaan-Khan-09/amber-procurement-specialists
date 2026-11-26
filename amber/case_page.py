"""The case file as one page a judge can read top to bottom: what was decided, by whom, on what evidence, and what
the measured change in hand-offs is. Rendered from the frozen case (examples/case_GEN/) and the hand-off evaluation
(eval/handoff_set/results.json); no model calls, no JavaScript needed.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "examples" / "case_GEN"
EVAL = ROOT / "eval" / "handoff_set" / "results.json"
INDEX = Path(__file__).with_name("web_index.html")

ROUTE_LABEL = {"decide": ("decided by the agent", "ok"), "ask_supplier": ("question to the supplier", "info"),
               "engineer": ("engineer judges", "warn")}
VERDICT_CLS = {"complies": "ok", "meets": "ok", "linked": "ok", "included": "ok", "deviates": "bad", "fails": "bad",
               "unclear": "warn", "missing": "mute", "needs_verification": "warn", "ambiguous": "warn", "qualified": "warn",
               "silent": "mute", "excluded": "bad", "alternate": "info"}

CSS = """
.wrap{max-width:1200px;margin:0 auto;padding:18px 16px 80px}
.toc{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0 18px}.toc a{font-size:13px;font-weight:600;padding:3px 10px;border:1px solid var(--line);border-radius:99px;text-decoration:none;background:var(--card)}
.tag{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;padding:1px 7px;border-radius:5px;margin-left:6px;vertical-align:2px}
.tag.m{background:var(--okbg);color:var(--ok)}.tag.k{background:var(--warnbg);color:var(--warn)}.tag.a{background:var(--infobg);color:var(--info)}
.q{font-style:italic;color:var(--ink);background:var(--soft);border-left:3px solid #e6b800;padding:2px 8px;border-radius:0 6px 6px 0;display:inline-block;margin:2px 0;font-size:13px}
.src{font-size:12px;color:var(--mute)}
.arrow{color:var(--mute);padding:0 4px}
.kpi .v small{font-size:14px;color:var(--mute);font-weight:600}
td .b{margin:1px 0}
.steps td:first-child{font-weight:600;white-space:nowrap}
.mono{font-family:ui-monospace,Consolas,monospace;font-size:12.5px}
details summary{cursor:pointer;font-weight:600}
.pq td{text-align:center}.pq td:first-child,.pq td:nth-child(2){text-align:left}
.pq .b{min-width:22px}
@media (max-width:700px){.hide-sm{display:none}}
@media (max-width:560px){.tiles,.grid{grid-template-columns:1fr}.toc a{font-size:12px}h1{font-size:19px}}
body{overflow-wrap:anywhere}
"""


def _e(s) -> str:
    return html.escape(str(s if s is not None else ""))


def _b(text, cls) -> str:
    return f'<span class="b {cls}">{_e(text)}</span>'


def _v(verdict) -> str:
    return _b(str(verdict).replace("_", " "), VERDICT_CLS.get(str(verdict), "mute"))


def _r(route) -> str:
    lab, cls = ROUTE_LABEL.get(route, (route, "mute"))
    return _b(lab, cls)


def _cite(c: dict | None, n: int = 150) -> str:
    if not c:
        return ""
    where = f"{c.get('doc_id', '')}" + (f" p{c['page']}" if c.get("page") and c.get("match") != "record" else
                                        f" ({c.get('locator')})" if c.get("locator") else "")
    return f'<div><span class="q">"{_e(str(c.get("quote", ""))[:n])}"</span> <span class="src">{_e(where)}</span></div>'


def _load(d: Path, step: str) -> dict:
    return json.loads((d / "steps" / f"{step}.json").read_text(encoding="utf-8"))


def _style() -> str:
    t = INDEX.read_text(encoding="utf-8")
    m = re.search(r"<style>(.*?)</style>", t, re.S)
    return (m.group(1) if m else "") + CSS


def _money(x) -> str:
    return f"${x / 1e6:.3f}M" if isinstance(x, (int, float)) else "-"


def render(snap: Path = SNAP, eval_file: Path = EVAL, back_href: str = "./") -> str:
    s1, s2, rs = snap / "1_questions_sent", snap / "2_after_replies", snap / "resume"
    state = json.loads((s2 / "state.json").read_text(encoding="utf-8"))
    ev = json.loads(eval_file.read_text(encoding="utf-8")) if eval_file.exists() else None
    disc, link = _load(s2, "discover"), _load(s2, "link")
    only = lambda d: {k: v for k, v in d.items() if not k.startswith("_")}  # a step's own summary is not a bidder
    pq1, pq2 = only(_load(s1, "prequalify")), only(_load(s2, "prequalify"))
    rec1, rec2 = only(_load(s1, "reconcile")), only(_load(s2, "reconcile"))
    rng1, rng2, tri1, tri2 = _load(s1, "ranges"), _load(s2, "ranges"), _load(s1, "triage"), _load(s2, "triage")
    q1, rep, dec = _load(s1, "questions"), _load(s2, "replies"), _load(s2, "decision")
    names = {r["vendor_id"]: r["name"] for r in disc["ranked"]}
    bv = state["memory"]["bidder_vendor"]
    out = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>Generator case file</title><style>{_style()}</style></head><body>"]
    out.append(f"<header><div class='bar'><div class='brand'><div class='logo' aria-hidden='true'><svg width='16' height='16' viewBox='0 0 16 16'>"
               f"<path d='M9 1L3 9h4l-1 6 6-8H8l1-6z' fill='#fff'/></svg></div><div>Case file: four 2000 kW generators"
               f"<small>Project Alpha (fictional) · one purchase, end to end</small></div></div><div class='grow'></div>"
               f"<a class='btn sm' href='{_e(back_href)}'>Back to the specialists</a></div></header><div class='wrap'>")
    out.append(f"<h1>{_e(state['goal'])}</h1><p class='lead'>Thirteen steps ran as one case file that remembers what each step "
               "found and resumes where it stopped. Every answer below cites its source; every number in the measured section "
               "comes from <span class='mono'>scripts/eval_handoffs.py</span>. Labels: <span class='tag m'>measured</span> "
               "<span class='tag k'>mock data</span> <span class='tag a'>assumption</span>.</p>")
    out.append("<div class='toc'>" + "".join(f"<a href='#{a}'>{t}</a>" for a, t in [
        ("measured", "Measured change"), ("steps", "Steps & resume"), ("decision", "Decision"), ("discovery", "Vendor discovery"),
        ("prequal", "Pre-qualification"), ("links", "Record links"), ("reconcile", "Reconciled answers"), ("ranges", "Ranges"),
        ("triage", "Who acts"), ("replies", "Questions & replies")]) + "</div>")

    # ---- measured
    if ev:
        L, D = ev["summary"]["like_for_like"], ev["summary"]["by_group"]["datasheet"]
        P = ev["summary"]["by_group"]["package"]
        U = ev["summary"].get("unseen_set4")
        n = L["before"]["n"]

        def tile(k, b, a, sub, cls="okt"):
            return (f"<div class='tile kpi {cls}'><div class='k'>{_e(k)}</div><div class='v'>{b} <span class='arrow'>&rarr;</span> {a}</div>"
                    f"<div class='s'>{sub}</div></div>")
        e1, e2 = tri1["summary"], tri2["summary"]
        out.append("<h2 id='measured'>Measured change in hand-offs <span class='tag m'>measured</span></h2>")
        out.append("<div class='tiles'>"
                   + tile("Sent to an engineer", L["before"]["to an engineer"], L["now"]["to an engineer"],
                          f"of {n} fixed cases ({L['before']['to an engineer'] / n:.0%} &rarr; {L['now']['to an engineer'] / n:.0%})")
                   + tile("Datasheet answers to an engineer", f"{D['before']['to an engineer'] / D['before']['n']:.0%}",
                          f"{D['now']['to an engineer'] / D['now']['n']:.0%}",
                          f"of {D['before']['n']}; {D['now']['to the supplier']} now go straight to the supplier as questions")
                   + tile("Right without a person", L["before"]["correct autonomous"], L["now"]["correct autonomous"], f"of {n}")
                   + tile("Critical errors", L["before"]["critical"], L["now"]["critical"], "accepting what fails, rejecting what complies",
                          "okt" if L["now"]["critical"] <= L["before"]["critical"] else "badt")
                   + tile("Package answers right", f"{P['before']['right action']}/{P['before']['n']}", f"{P['now']['right action']}/{P['now']['n']}",
                          "reading the supplier's bid next to its datasheet")
                   + (tile("Unseen datasheet (held out)", f"{U['before']['to an engineer']}/{U['before']['n']}",
                           f"{U['now']['to an engineer']}/{U['now']['n']}",
                           f"to an engineer; {U['now']['to the supplier']} supplier questions, all right; labelled before its one run",
                           "infot") if U else "")
                   + tile("After two replies (mock)", f"{e1['engineer']} / {e1['ask_supplier']}", f"{e2['engineer']} / {e2['ask_supplier']}",
                          "engineer items / supplier questions in this case", "infot")
                   + "</div>")
        rows = ["correct autonomous", "justified hand-off", "unnecessary hand-off", "incorrect autonomous", "critical",
                "to an engineer", "to the supplier", "right action"]
        groups = [("All like-for-like", L)] + [(g, ev["summary"]["by_group"][g]) for g in ("datasheet", "package", "link", "bid scope", "decision")] \
            + [(f"category: {c.replace('_', ' ')}", ev["summary"]["by_category"][c]) for c in ("routine", "missing_info", "conflict", "escalate")]
        out.append("<div class='card scroll'><table><tr><th>Set</th><th class='n'>n</th>" + "".join(f"<th class='n'>{_e(r)}<br>before &rarr; now</th>" for r in rows) + "</tr>")
        for lab, g in groups:
            out.append(f"<tr><td>{_e(lab)}</td><td class='n'>{g['before']['n']}</td>" + "".join(
                f"<td class='n'>{g['before'][r]} &rarr; <b>{g['now'][r]}</b></td>" for r in rows) + "</tr>")
        if U:
            out.append(f"<tr><td>unseen datasheet (held-out set 4)</td><td class='n'>{U['before']['n']}</td>" + "".join(
                f"<td class='n'>{U['before'][r]} &rarr; <b>{U['now'][r]}</b></td>" for r in rows) + "</tr>")
        PQ = ev["summary"]["new_specialist_prequal"]
        out.append(f"<tr><td>new: pre-qualification (before = all by hand)</td><td class='n'>{PQ['before']['n']}</td>" + "".join(
            f"<td class='n'>{PQ['before'][r]} &rarr; <b>{PQ['now'][r]}</b></td>" for r in rows) + "</tr></table>")
        out.append("<p class='small'><b>Before</b> = the routing at commit 48b321c (anything under 0.70 to one queue). <b>Now</b> = the same "
                   "saved model readings, routed by amber/triage.py and reconciled across the supplier's documents. "
                   "<b>Correct autonomous</b>: the agent acted alone (decided, or asked the supplier) and the action was right. "
                   "<b>Justified hand-off</b>: an engineer was asked and the case needs judgement or the agent's answer was wrong. "
                   "<b>Unnecessary</b>: an engineer was asked but the agent was right and no judgement was needed. <b>Critical</b>: "
                   "accepting what fails or is not shown, or rejecting what complies. These documents were seen during development: "
                   "a repair record on a fixed set, not a held-out score. The bid and supplier documents are mock data.</p>")
        bad = [r for r in ev["results"] if r["now"]["outcome"] == "incorrect autonomous"]
        out.append("<details><summary>Every case the agent now gets wrong on its own (" + str(len(bad)) + ")</summary><table>"
                   "<tr><th>Case</th><th>Expected</th><th>Now</th><th>Severity</th></tr>" + "".join(
                       f"<tr><td class='mono'>{_e(r['id'])}</td><td>{_v(r['expected'])} {_r(r['expected_route'])}</td>"
                       f"<td>{_v(r['now']['answer'])} {_r(r['now']['route'])}</td><td>{_e(r['now']['severity'])}</td></tr>" for r in bad)
                   + "</table></details></div>")

    # ---- steps & resume
    out.append("<h2 id='steps'>Steps, memory and resuming</h2><div class='card scroll'><table class='steps'><tr><th>Step</th><th>Status</th>"
               "<th class='n'>Runs</th><th>What it found</th></tr>")
    for name in ("requirements", "discover", "link", "datasheets", "bids", "commitments", "reconcile", "prequalify", "ranges",
                 "triage", "questions", "replies", "decision"):
        st = state["steps"].get(name, {})
        status = _b(st.get("status", "-"), "ok" if st.get("status") == "done" else "warn")
        out.append(f"<tr><td>{_e(name)}</td><td>{status}</td>"
                   f"<td class='n'>{_e(st.get('attempts', ''))}</td><td>{_e(st.get('summary', ''))}</td></tr>")
    out.append("</table>")
    mem = state["memory"]
    out.append("<p class='small'>What the steps share (memory, saved in state.json): need date " + _e(mem.get("need_date")) + "; bidder &rarr; vendor "
               + _e(", ".join(f"{b}={v}" for b, v in bv.items())) + "; product links; scope links " + _e(mem.get("scope_links")) +
               "; questions asked per supplier; replies read " + _e(", ".join(sorted(mem.get("replies_read", {})))) +
               ". A step whose inputs (files, earlier outputs, memory it uses) are unchanged is reused, not run again.</p>")
    if (rs / "journal.jsonl").exists():
        ev_lines = [json.loads(l) for l in (rs / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
        keep = [e for e in ev_lines if e["event"] in ("started", "interrupted", "reused", "done")][:30]
        out.append("<details><summary>An interrupted run, resumed (journal)</summary><p class='small'>The first run was stopped on purpose "
                   "inside <b>reconcile</b> (after 2 of 4 suppliers). The second run reused the six finished steps, saw the step that was "
                   "still marked running, and ran it again.</p><table>" + "".join(
                       f"<tr><td class='mono'>{_e(e['t'][11:])}</td><td>{_b(e['event'], 'bad' if e['event'] == 'interrupted' else 'mute' if e['event'] == 'reused' else 'ok')}</td>"
                       f"<td>{_e(e.get('step', ''))}</td><td class='small'>{_e(e.get('note', e.get('summary', ''))[:110])}</td></tr>" for e in keep)
                   + "</table></details>")
    out.append("</div>")

    # ---- decision
    out.append("<h2 id='decision'>Decision: stays with a person</h2><div class='card scroll'><p>" + _e(dec["why"]) + ".</p>"
               "<table><tr><th>Bid</th><th>Vendor</th><th class='n'>Leveled cost (range)</th><th>Arrival P50 / P90</th>"
               "<th class='n'>P(late)</th><th>Pre-qualification</th><th>Still open</th></tr>")
    for o in dec["options"]:
        late = "" if o["p_late"] is None else f"{o['p_late']:.0%}"
        out.append(f"<tr><td><b>{_e(o['bid'])}</b></td><td>{_e(names.get(o['vendor'], o['vendor']))}</td>"
                   f"<td class='n'>{_money(o['cost_low'])} &ndash; {_money(o['cost_high'])}</td><td>{_e(o['arrival_P50'])} / {_e(o['arrival_P90'])}</td>"
                   f"<td class='n'>{late}</td>"
                   f"<td>{_v('meets' if o['prequal'].startswith('qualified') else 'fails' if o['prequal'] == 'fails' else 'needs_verification')} "
                   f"<span class='small'>{_e(o['prequal'])}</span></td><td class='small'>{_e('; '.join(o['blockers']))}</td></tr>")
    out.append("</table><p class='small'>Every option is likely to arrive after the 2027-10-04 need date: schedule mitigation is escalated "
               "to the project manager. Bidders and prices are mock data.</p></div>")

    # ---- discovery
    out.append("<h2 id='discovery'>Vendor discovery <span class='tag k'>mock vendor master</span></h2><div class='card scroll'>"
               "<p class='small'>Candidates come only from the vendor master and the datasheets we hold; nothing from model memory. "
               "Points are listed so a buyer can disagree with any of them. The spec's manufacturer list is quoted below.</p>")
    out.append(_cite(disc.get("spec_citation"), 160))
    out.append("<table><tr><th class='n'>#</th><th>Vendor</th><th>Manufacturer / product</th><th class='n'>Points</th><th>Why (each point)</th></tr>")
    for v in disc["ranked"]:
        out.append(f"<tr><td class='n'>{v['rank']}</td><td><b>{_e(v['name'])}</b>{' ' + _b('engineer approves an equal', 'warn') if v['needs_engineer'] else ''}</td>"
                   f"<td>{_e(', '.join(v['manufacturers']))}<div class='src'>{_e(v.get('product') or '')}</div></td><td class='n'>{v['points']}</td>"
                   f"<td class='small'>{'<br>'.join(_e(r) for r in v['reasons'])}</td></tr>")
    out.append("</table><h3 style='margin-top:12px'>Set aside</h3><table>" + "".join(
        f"<tr><td>{_e(x['name'])}</td><td class='small'>{_e(x['why'])}</td></tr>" for x in disc["excluded"]) + "</table>")
    out.append("<p class='small'><b>The case to watch:</b> Tidewater ranks first (best product fit, shortest lead time, on the spec's list) "
               "and still does not pass pre-qualification until its reply arrives: an expiring insurance certificate, an authorization "
               "letter 'available on request', and no named service branch where the vendor master says Norfolk, 190 miles away.</p></div>")

    # ---- prequal
    crit = list(next(iter(pq2.values()))["criteria"].keys())
    out.append("<h2 id='prequal'>Pre-qualification <span class='tag k'>mock packets</span></h2><div class='card scroll'>"
               "<p class='small'>Criteria P1-P2 are the real spec's (1.4.A acceptable manufacturers, 1.4.G ten years); Q1-Q7 are the "
               "general contractor's policy (mock). The model reads each packet; code verifies the words on the page and decides. "
               "A self-certification about federal exclusion is recorded, not trusted: the owner checks the list.</p>"
               "<table class='pq'><tr><th>Bid</th><th>When</th>" + "".join(f"<th>{_e(c)}</th>" for c in crit) + "<th>Overall</th></tr>")
    for label, pq in (("questions sent", pq1), ("after reply", pq2)):
        for b, v in pq.items():
            if label == "after reply" and json.dumps(pq1[b]["criteria"], sort_keys=True) == json.dumps(v["criteria"], sort_keys=True):
                continue
            out.append(f"<tr><td><b>{_e(b)}</b> <span class='src'>{_e(v['name'])}</span></td><td class='small'>{label}</td>" + "".join(
                f"<td title='{_e(v['criteria'][c]['why'])}'>{_b({'meets': 'ok', 'fails': 'no', 'needs_verification': '?'}[v['criteria'][c]['status']], VERDICT_CLS[v['criteria'][c]['status']])}</td>"
                for c in crit) + f"<td class='small'>{_e(v['overall'])}</td></tr>")
    out.append("</table><details><summary>Every criterion that is not met, with its evidence</summary>")
    for b, v in pq2.items():
        for c, r in v["criteria"].items():
            if r["status"] != "meets":
                out.append(f"<div class='f'><b>{_e(b)} {_e(c)}</b> {_v(r['status'])} {_e(r['text'])}<div class='small'>{_e(r['why'])}</div>"
                           + "".join(_cite(x) for x in r["citations"][:2]) + "</div>")
    out.append("</details></div>")

    # ---- links
    out.append("<h2 id='links'>Record links</h2><div class='card scroll'><table><tr><th>Bid</th><th>Product named</th><th>Link</th><th>Evidence</th></tr>")
    for b, v in link["products"].items():
        cands = "".join(f"<div class='small'>{_b(c['kind'], 'ok' if c['kind'] in ('primary', 'exact') else 'warn')} {_e(c['file'])} "
                        f"(found {_e(c['found'])}{', via ' + _e(c['via']['bid']) + chr(39) + 's bid' if c.get('via') else ''})</div>" for c in v["candidates"])
        out.append(f"<tr><td><b>{_e(b)}</b></td><td>{_e(v['product'])}</td><td>{_v(v['status'])} {_r(v['route'])}</td>"
                   f"<td class='small'>{_e(v['why'])}{cands}</td></tr>")
    out.append("</table><h3 style='margin-top:12px'>Bid form scope items &rarr; spec requirements</h3><table>")
    for l in link["scope"]["links"]:
        out.append(f"<tr><td>{_v('linked')}</td><td>{_e(l['scope_id'])} &rarr; {_e(l['req_id'])}</td><td class='small'>{_e(l['why'])}</td></tr>")
    for l in link["scope"]["conflicts"]:
        out.append(f"<tr><td>{_v('ambiguous')}</td><td>{_e(l['scope_id'])} &#x2260; {_e(l['req_id'])}</td><td class='small'>{_e(l['why'])}</td></tr>")
    out.append(f"</table><p class='small'>Equipment records: {_e(link['records']['why'])}; need dates {_e(', '.join(link['records']['need_dates']))}.</p></div>")

    # ---- reconcile
    out.append("<h2 id='reconcile'>Reconciled answers: datasheet alone vs the supplier's whole package</h2><div class='card scroll'>"
               "<p class='small'>Each condition of each requirement takes the strongest verified evidence across the datasheet, the "
               "bid and any reply. A bid commitment settles what a datasheet leaves as an option; a bid that commits to less is a "
               "deviation; records that disagree stay a conflict for the supplier to resolve; a footnote that lowers a rating when an "
               "option is fitted is linked to that option.</p><table><tr><th>Bid</th><th>Requirement</th><th>Datasheet alone</th>"
               "<th>Bid + datasheet</th><th>After reply</th><th>Evidence used</th></tr>")
    for b in bv:
        if "findings" not in rec1.get(b, {}):
            continue
        base = {f["data"]["req_id"]: f for f in rec1[b]["datasheet_only"]}
        f1 = {f["data"]["req_id"]: f for f in rec1[b]["findings"]}
        f2 = {f["data"]["req_id"]: f for f in rec2[b]["findings"]}
        for rid, f in f2.items():
            a, m, z = base[rid], f1[rid], f
            if (a["status"], a["route"]["route"]) == (m["status"], m["route"]["route"]) == (z["status"], z["route"]["route"]):
                continue
            ev_c = [c for c in z["citations"][1:] if c.get("doc_id") and not str(c["doc_id"]).startswith("equipment")][:2]
            out.append(f"<tr><td><b>{_e(b)}</b></td><td><b>{_e(rid)}</b> <span class='small'>{_e(z['claim'][:70])}</span></td>"
                       f"<td>{_v(a['status'])}<br>{_r(a['route']['route'])}</td><td>{_v(m['status'])}<br>{_r(m['route']['route'])}"
                       f"<div class='src'>{_e(m['route']['kind'])}</div></td><td>{_v(z['status'])}<br>{_r(z['route']['route'])}</td>"
                       f"<td>{''.join(_cite(c, 110) for c in ev_c)}</td></tr>")
    out.append("</table>")
    cond = [(b, c) for b in bv for c in rec1.get(b, {}).get("conditional", [])]
    for b, c in cond:
        out.append(f"<div class='banner note card'><b>{_e(b)} {_e(c['req_id'])}: related sections linked.</b> {_e(c['why'])}</div>")
    out.append("</div>")

    # ---- ranges
    out.append("<h2 id='ranges'>Honest ranges</h2><div class='card scroll'><h3>Leveled cost</h3><table><tr><th>Bid</th><th class='n'>Base</th>"
               "<th class='n'>Range when questions went out</th><th class='n'>Range after replies</th><th>How it is derived</th></tr>")
    for b in bv:
        c1, c2 = rng1["cost"][b], rng2["cost"][b]
        out.append(f"<tr><td><b>{_e(b)}</b></td><td class='n'>{_money(c1['base'])}</td><td class='n'>{_money(c1['low'])} &ndash; {_money(c1['high'])}</td>"
                   f"<td class='n'>{_money(c2['low'])} &ndash; {_money(c2['high'])}</td><td class='small'>{_e(c2['derivation'])}"
                   + "".join(f"<br>&bull; {_e(n)}" for n in c2["notes"] if "reply" in n) + "</td></tr>")
    out.append("</table><h3 style='margin-top:12px'>Arrival on site <span class='tag m'>measured sources</span></h3><table><tr><th>Scenario</th>"
               "<th>P10</th><th>P50</th><th>P90</th><th class='n'>P(after need date)</th><th>Evidence (weight)</th></tr>")
    for sc, a in rng2["arrival"].items():
        evs = "; ".join(f"{x['id']} {x['range_weeks'][0]:g}-{x['range_weeks'][1]:g} wk ({x['weight']:g}{', dissent' if x.get('dissent') else ''})"
                        for x in (a.get("evidence") or []))
        out.append(f"<tr><td>{_e(sc)}</td><td>{_e(a['P10'])}</td><td><b>{_e(a['P50'])}</b></td><td>{_e(a['P90'])}</td>"
                   f"<td class='n'>{a['p_late']:.0%}</td><td class='small'>{_e(evs)}</td></tr>")
    out.append("</table><div class='grid' style='margin-top:10px'><div><h3>Assumptions <span class='tag a'>assumption</span></h3><ul class='small'>"
               + "".join(f"<li>{_e(x)}</li>" for x in rng2["assumptions"]) + "</ul></div><div><h3>Missing inputs that widen the range</h3><ul class='small'>"
               + "".join(f"<li>{_e(x)}</li>" for x in rng2["missing_inputs"]) + "</ul></div></div></div>")

    # ---- triage
    out.append("<h2 id='triage'>Who acts on what</h2><div class='card scroll'><table><tr><th>Group</th><th class='n'>Items</th>"
               "<th class='n'>decided</th><th class='n'>to the supplier</th><th class='n'>to an engineer</th><th class='n'>after replies: engineer</th></tr>")
    for g, s in tri1["by_group"].items():
        s2g = tri2["by_group"].get(g, s)
        out.append(f"<tr><td>{_e(g)}</td><td class='n'>{s['total']}</td><td class='n'>{s['decide']}</td><td class='n'>{s['ask_supplier']}</td>"
                   f"<td class='n'>{s['engineer']}</td><td class='n'>{s2g['engineer']}</td></tr>")
    out.append("</table><details><summary>The engineer's queue after the replies, with the reason for each</summary><table>")
    for it in tri2["items"]:
        if it["route"] == "engineer":
            out.append(f"<tr><td>{_e(it['bid'])}</td><td class='mono'>{_e(it['group'])} {_e(it['id'])}</td><td>{_b(it.get('kind', ''), 'warn')}</td>"
                       f"<td class='small'>{_e(str(it.get('why', ''))[:170])}</td></tr>")
    out.append("</table></details></div>")

    # ---- questions & replies
    out.append("<h2 id='replies'>Questions to suppliers and their replies <span class='tag k'>mock replies</span></h2><div class='card scroll'>"
               "<p class='small'>Drafts are never sent automatically. Each question cites what was read. A reply is matched to its "
               "supplier by the sender's name in the vendor master and read only against that supplier's open items.</p>")
    for b, d in q1["drafts"].items():
        out.append(f"<details><summary>{_e(b)} {_e(names.get(d['to'], d['to']))}: {len(d['questions'])} questions</summary>" + "".join(
            f"<div class='f'><b>{_e(q['ref'])}</b> {_b(q.get('kind') or '', 'info')} {_e(q['ask'])}" + "".join(
                _cite({"doc_id": w["doc"], "page": w["page"], "quote": w["quote"]}, 120) for w in q["we_read"]) + "</div>" for q in d["questions"])
                   + "</details>")
    out.append("<h3 style='margin-top:12px'>Replies read</h3><table>" + "".join(
        f"<tr><td>{_e(r.get('bid', ''))}</td><td class='mono'>{_e(r['file'])}</td><td class='small'>{_e(r.get('matched_by', r.get('note', '')))}; "
        f"read against {len(r.get('asked', []))} open items</td></tr>" for r in rep.get("read", [])) + "</table>")
    out.append("<p class='small'>What the replies changed is in the 'After reply' column above, in the pre-qualification table and in the "
               "cost ranges: Northline's reply settled 14 open items and revealed one deviation (a single 9 kW jacket-water heater where "
               "two 5 kW are required); its 'will be confirmed with the final submittal' settled nothing; its claim of full rating "
               "'with the 50 C cooling package', which it had not confirmed, went to an engineer. Tidewater's reply replaced the 12-hour "
               "tank with a 24-hour UL 2085 tank at $18,000 a set, which replaced the $220,000 allowance in its leveled cost, and "
               "settled its three pre-qualification items. Scored against the replies' key: 17 of 18 answers right.</p></div>")
    out.append("<p class='small'>Built by amber/case_page.py from examples/case_GEN (scripts/snapshot_case.py) and "
               "eval/handoff_set/results.json (scripts/eval_handoffs.py).</p></div></body></html>")
    return "".join(out)


def write(path: Path, back_href: str = "./") -> Path:
    path.write_text(render(back_href=back_href), encoding="utf-8")
    return path
