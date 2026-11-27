"""The case file as one page a judge can read top to bottom: what was decided, by whom, on what evidence, and what
the measured change in hand-offs is. Rendered from the frozen case (examples/case_GEN/) and the hand-off evaluation
(eval/handoff_set/results.json); no model calls, no JavaScript needed.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from . import registries

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
.front{margin:6px 0 30px}
.front .kicker{font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--brand);margin:0 0 8px}
.front h1{font-size:clamp(26px,4.4vw,42px);line-height:1.15;margin:0 0 10px;letter-spacing:-.02em;max-width:900px}
.front .sub{font-size:clamp(15px,1.8vw,18px);color:var(--mute);max-width:780px;margin:0 0 22px}
.proofs{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.proof{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;display:flex;flex-direction:column;gap:8px}
.proof .who{font-size:12px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--mute)}
.proof .words{font-size:17px;line-height:1.45;border-left:4px solid #e6b800;padding:2px 0 2px 12px;font-style:italic;flex:1}
.proof .where{font-size:12px;color:var(--mute)}
.sum{margin:12px 0 0;background:var(--badbg);border:1px solid var(--bad);border-radius:12px;padding:14px 18px;display:flex;gap:18px;align-items:center;flex-wrap:wrap}
.sum .math{font-size:clamp(22px,3vw,30px);font-weight:800;color:var(--bad);font-variant-numeric:tabular-nums;white-space:nowrap}
.sum .say{flex:1;min-width:240px}
.three{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:26px 0 12px}
.num{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.num .v{font-size:clamp(28px,3.6vw,38px);font-weight:800;line-height:1.1;font-variant-numeric:tabular-nums}
.num .v span{color:var(--mute);font-weight:600;font-size:.7em;padding:0 6px}
.num .k{font-weight:600;margin-top:4px}
.num .s{font-size:12.5px;color:var(--mute);margin-top:2px}
.go{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}
@media (max-width:760px){.proofs,.three{grid-template-columns:1fr}.sum .math{white-space:normal}}
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
.walk li{margin-bottom:10px}
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


METRIC_LABELS = [("to an engineer", "Sent to an engineer"), ("supplier questions", "Question to the supplier"),
                 ("clarification requests", "Focused clarification"), ("unresolved", "Unresolved (engineer + any question)"),
                 ("correct decisions", "Correct decision made alone"),
                 ("incorrect decisions (critical)", "Wrong decision: approves what fails, or rejects what complies"),
                 ("incorrect decisions (minor)", "Wrong decision: minor"), ("missed escalations", "Missed mandatory escalation"),
                 ("questions not needed", "Questions not needed"), ("unnecessary hand-offs", "Unnecessary hand-off"),
                 ("right action", "Right action (any route)")]
VERSION_COLS = (("v2", "v2: original"), ("v3", "v3: previous"), ("v4", "v4: candidate"))


def _versions(title: str, s: dict) -> str:
    cols = [(v, c) for v, c in VERSION_COLS if v in s]
    n = s[cols[0][0]]["n"]
    rows = "".join(f"<tr><td>{_e(lab)}</td>" + "".join(
        f"<td class='n'>{s[v][k]} <span class='src'>({s[v][k] / n:.0%})</span></td>" for v, _ in cols) + "</tr>"
        for k, lab in METRIC_LABELS)
    return (f"<h3>{_e(title)} <span class='src'>n = {n}</span></h3><table><tr><th>Outcome</th>"
            + "".join(f"<th class='n'>{_e(c)}</th>" for _, c in cols) + "</tr>" + rows + "</table>")


def _wrong(s: dict, v: str) -> int:
    return s[v]["incorrect decisions (critical)"] + s[v]["incorrect decisions (minor)"]


def _case_card(r: dict, title: str) -> str:
    return (f"<div class='f'><b>{_e(title)}</b> <span class='mono'>{_e(r['id'])}</span> &middot; key: {_v(r['expected'])} {_r(r['expected_route'])}"
            f"<div>Previous: {_v(r['v3']['answer'])} {_r(r['v3']['route'])} <span class='small'>{_e((r['v3'].get('why') or '')[:240])}</span></div>"
            f"<div>Now: {_v(r['v4']['answer'])} {_r(r['v4']['route'])} <span class='small'>{_e((r['v4'].get('why') or '')[:300])}</span></div></div>")


def _before_after(rows: list[dict]) -> str:
    by = {r["id"]: r for r in rows}
    out = ["<h2 id='change'>One case that needed a person and now does not, and one that still does</h2><div class='card'>"]
    if "G6/R01" in by:
        out.append(_case_card(by["G6/R01"], "Resolved: the ratings table has several rows; the project's voltage picks the row."))
    if "G6/R11" in by:
        out.append(_case_card(by["G6/R11"], "Still escalates: full rating depends on how a derating clause is read, and the model's reading and the code's check disagree."))
    out.append("<p class='small'>Both are on a real Kohler datasheet (documents seen while building).</p></div>")
    return "".join(out)


def _measured(ev: dict, pkg_file: Path) -> str:
    S = ev["summary"]
    L, F = S["like_for_like"], S.get("fresh_set6") or {}
    n = L["v4"]["n"]

    def tile(k, a, b, sub, cls="okt"):
        return (f"<div class='tile kpi {cls}'><div class='k'>{_e(k)}</div><div class='v'>{a} <span class='arrow'>&rarr;</span> {b}</div>"
                f"<div class='s'>{sub}</div></div>")
    out = [_before_after(ev["results"]),
           "<h2 id='measured'>Measured: previous version (v3) against this candidate (v4) <span class='tag m'>measured</span></h2><div class='tiles'>",
           tile("Unresolved cases", L["v3"]["unresolved"], L["v4"]["unresolved"], f"of {n}: sent to an engineer or asked of a supplier"),
           tile("Engineer hand-offs", L["v3"]["to an engineer"], L["v4"]["to an engineer"], f"original version: {L['v2']['to an engineer']}"),
           tile("Correct decisions made alone", L["v3"]["correct decisions"], L["v4"]["correct decisions"], f"original: {L['v2']['correct decisions']}"),
           tile("Wrong decisions", _wrong(L, "v3"), _wrong(L, "v4"),
                f"missed escalations {L['v3']['missed escalations']} &rarr; {L['v4']['missed escalations']}")]
    if F:
        out.append(tile("Fresh sheets: unresolved", F["v3"]["unresolved"], F["v4"]["unresolved"], f"of {F['v4']['n']}, candidate frozen first", "infot"))
        out.append(tile("Fresh sheets: wrong decisions", _wrong(F, "v3"), _wrong(F, "v4"),
                        f"missed escalations {F['v3']['missed escalations']} &rarr; {F['v4']['missed escalations']}",
                        "infot" if _wrong(F, "v4") <= _wrong(F, "v3") else "badt"))
    out.append("</div><div class='card scroll'>")
    if F:
        out.append(_versions("Fresh datasheets nobody had opened when the candidate was frozen", F))
        out.append("<p class='small'>The candidate's one wrong decision here is a <b>labelling error</b> under review (the sheet says "
                   "\"stationary diesel engines are Tier II compliant\"; the key said unclear); the key was not edited. Separately, a fresh "
                   "cross-document case showed a <b>real critical error</b> in this and the previous version: a bid's passing fuel figure was "
                   "accepted over the datasheet's failing one. Fixed afterwards with a regression test (docs/RESULTS.md).</p>")
    out.append(_versions("Fixed development set (documents seen while building: a repair record)", L))
    out.append("<p class='small'><b>v2</b> commit 9cd1b4e. <b>v3</b> commit 1d14f3e. <b>v4</b> this candidate. All read the same saved model "
               "output. No question is counted as resolved without a verified follow-up, and there is none in these sets. Answer keys "
               "were written by an AI before the code they score and are <b>not yet reviewed by a person</b>.</p>")
    like = [r for r in ev["results"] if r["group"] in ("datasheet", "package", "link", "bid scope", "decision")]
    changed = [r for r in like if (r["v3"]["answer"], r["v3"]["route"]) != (r["v4"]["answer"], r["v4"]["route"])]
    worse = [r for r in changed if r["v4"]["outcome"] in ("incorrect decision", "missed escalation") or r["v4"]["outcome"].endswith("not needed")
             or (r["v4"]["outcome"] == "unnecessary hand-off" and r["v3"]["outcome"] != "unnecessary hand-off")]
    better = [r for r in changed if r not in worse]

    def lst(rows):
        return ("<table><tr><th>Case</th><th>Key</th><th>v3</th><th>v4</th><th>Why (v4)</th></tr>" + "".join(
            f"<tr><td class='mono'>{_e(r['id'])}</td><td>{_v(r['expected'])}</td><td>{_v(r['v3']['answer'])} {_r(r['v3']['route'])}</td>"
            f"<td>{_v(r['v4']['answer'])} {_r(r['v4']['route'])}<div class='src'>{_e(r['v4']['outcome'])}</div></td>"
            f"<td class='small'>{_e((r['v4'].get('why') or r['v4'].get('kind') or '')[:170])}</td></tr>" for r in rows) + "</table>")
    out.append(f"<details><summary>Changed for the better or sideways ({len(better)} cases)</summary>{lst(better)}</details>")
    out.append(f"<details><summary>Got worse ({len(worse)} cases)</summary>{lst(worse)}</details>")
    why = {"confirm a reading": "judged, not computable: a term or unit the code cannot confirm",
           "contested": "two models disagree and the disputed clause does not settle it",
           "judgement": "engineering judgement (partial or conditional statements, discarded values)",
           "absence not confirmed": "large document: absence not confirmed by a whole second reading",
           "conditional rating": "a derating footnote applies when a fitted option is fitted"}
    eng = [r for r in like if r["v4"]["route"] == "engineer"]
    kinds: dict = {}
    for r in eng:
        kinds.setdefault(r["v4"].get("kind"), []).append(r)
    out.append(f"<h3>Why {len(eng)} cases still reach an engineer</h3><table><tr><th>Reason</th><th class='n'>Cases</th>"
               "<th class='n'>needed (key agrees)</th><th>Examples</th></tr>" + "".join(
                   f"<tr><td>{_e(why.get(k, 'an award or schedule decision'))}</td><td class='n'>{len(v)}</td><td class='n'>"
                   f"{sum(1 for r in v if r['v4']['outcome'] == 'justified hand-off')}</td><td class='small mono'>"
                   f"{_e(', '.join(r['id'] for r in v[:6]))}</td></tr>" for k, v in sorted(kinds.items(), key=lambda kv: -len(kv[1]))) + "</table>")
    if pkg_file.exists():
        pc = json.loads(pkg_file.read_text(encoding="utf-8"))["summary"]
        cols = list(next(iter(pc.values())))
        out.append("<h3>What the supplier's own documents add: 22 package cases we worked on, identical routing</h3><table><tr><th>Variant</th>"
                   + "".join(f"<th class='n'>{_e(c)}</th>" for c in cols) + "</tr>" + "".join(
                       f"<tr><td>{_e(v)}</td>" + "".join(f"<td class='n'>{s[c]}</td>" for c in cols) + "</tr>" for v, s in pc.items())
                   + "</table>")
    PQ = S["new_specialist_prequal"]["v4"]
    out.append(f"<p class='small'>Pre-qualification, scored separately on mock packets: {PQ['right action']} of {PQ['n']} criteria right.</p></div>")
    return "".join(out)


def _public_record(pr: dict) -> str:
    d = pr.get("discovery") or {}
    out = ["<h2 id='public'>Vendor discovery from public federal records <span class='tag m'>real lookups</span></h2><div class='card scroll'>",
           f"<p class='small'>{_e(d.get('source', ''))} &middot; <span class='mono'>{_e(d.get('endpoint', ''))}</span> &middot; looked up "
           f"{_e(d.get('looked_up', '-'))} &middot; query: {_e(d.get('query', ''))} &middot; status {_e(d.get('status', 'unavailable'))}. "
           "A record shows what the government bought from an entity; it does not pre-qualify anyone.</p><table><tr><th>Legal entity</th>"
           "<th>UEI</th><th>What the record establishes</th><th>Evidence</th><th>Exclusion (SAM.gov)</th><th>Screening list</th></tr>"]
    for v in d.get("candidates", []):
        sc = (pr.get("screens") or {}).get(v["legal_entity"]) or {}
        e = v["evidence"][0]
        sam, csl = (sc.get("sam_exclusions") or {}), (sc.get("screening_list") or {})
        size = f"{v['largest_kw']:g} kW" if v.get("largest_kw") else ""
        out.append(f"<tr><td><b>{_e(v['legal_entity'])}</b></td><td class='mono'>{_e(v['uei'])}</td><td>{_b(v['establishes'], 'ok' if v['establishes'] == 'supply' else 'warn')} "
                   f"{_e(size)}</td>"
                   f"<td class='small'><a href='{_e(e['url'])}'>{_e(e['award_id'])}</a> {_e(e['date'])} {_e(e['state'])}: {_e(e['description'][:90])}</td>"
                   f"<td>{_b(sam.get('status', 'not looked up'), 'warn' if sam.get('status') in (None, 'unavailable', 'ambiguous') else 'ok' if sam.get('status') == 'no match' else 'bad')}</td>"
                   f"<td>{_b(csl.get('status', 'not looked up'), 'ok' if csl.get('status') == 'no match' else 'warn')}</td></tr>")
    cards = [registries.scorecard(v, (pr.get("screens") or {}).get(v["legal_entity"]))
             for v in d.get("candidates", []) if (pr.get("screens") or {}).get(v["legal_entity"])]
    if cards:
        names = [r["criterion"] for r in cards[0]["criteria"]]
        cls = {"pass": "ok", "flag": "warn", "fail": "bad", "not verified": "mute"}
        out.append("</table><h3 style='margin-top:14px'>Pre-qualification scorecard for these real suppliers (public records only)</h3>"
                   "<div class='scroll'><table><tr><th>Criterion</th>" + "".join(f"<th>{_e(c['legal_entity'])}</th>" for c in cards) + "</tr>"
                   + "".join(f"<tr><td>{_e(n)}</td>" + "".join(
                       f"<td title='{_e(c['criteria'][i]['why'])}'>{_b(c['criteria'][i]['status'], cls[c['criteria'][i]['status']])}</td>" for c in cards)
                       + "</tr>" for i, n in enumerate(names))
                   + "<tr><td><b>Overall</b></td>" + "".join(f"<td>{_b(c['overall'].upper(), cls[c['overall']])}</td>" for c in cards) + "</tr></table></div>")
        first = cards[0]
        out.append(f"<details><summary>Why, for {_e(first['legal_entity'])}</summary><table>" + "".join(
            f"<tr><td>{_e(r['criterion'])}</td><td>{_b(r['status'], cls[r['status']])}</td><td class='small'>{_e(r['why'][:220])}"
            + (f" &middot; <a href='{_e(r['url'])}'>record</a>" if r['url'] else "")
            + (f"<div class='src'>{_e(r['source'])} {_e(r['looked_up'])}</div>" if r['source'] else "") + "</td></tr>"
            for r in first["criteria"]) + "</table></details><table>")
    keyless = any(((s.get("sam_exclusions") or {}).get("status") == "unavailable") for s in (pr.get("screens") or {}).values())
    note = ("<b>Unverified:</b> the federal exclusion list (SAM.gov) could not be asked: it needs a personal API key (SAM_API_KEY) "
            "that this lookup did not have, so no supplier here is reported as cleared. " if keyless else "")
    out.append(f"</table><p class='small'>{note}The trade.gov screening list is a separate export and sanctions screen, not the "
               "procurement exclusion list.</p></div>")
    return "".join(out)


def _front(rec2: dict, ev: dict | None) -> str:
    """The first screen: one story a judge can check in seconds (a footnote that fails a compliant-looking rating), and
    three measured numbers. Everything else on the page is the detail behind it."""
    cond = next((c for c in (rec2.get("B3") or {}).get("conditional", []) if c["req_id"] == "R09"), None)
    f = next((x for x in (rec2.get("B3") or {}).get("findings", []) if x["data"]["req_id"] == "R09"), None)
    m = re.search(r"(\d+) °F less (\d+) °F.*?= (\d+) °F.*?required (\d+) °F", cond["why"]) if cond else None
    if not (f and m):
        return ""
    base, less, left, need = m.groups()
    cites = f["citations"]
    pick = lambda test: next((c for c in cites if test(c)), None)
    sheet = pick(lambda c: c["quote"].lower().startswith("ambient temperature"))
    note = pick(lambda c: "reduces ambient" in c["quote"].lower())
    bid = pick(lambda c: c["doc_id"].startswith("b3-"))
    if not (sheet and note and bid):
        return ""
    card = lambda who, c, shown, where: (f"<div class='proof'><div class='who'>{who}</div><div class='words'>&ldquo;{_e(shown)}&rdquo;</div>"
                                         f"<div class='where'>{where}, page {_e(c['page'])}</div></div>")
    clean = re.sub(r"^[\d)\s†*‡§]+", "", note["quote"])
    out = ["<section class='front'><p class='kicker'>One datasheet, one bid, one footnote</p>",
           "<h1>The datasheet says the radiator is good for 122&nbsp;&deg;F. Read with the bid, it is not.</h1>",
           "<p class='sub'>The specification requires 122&nbsp;&deg;F. A check of the rating alone passes it. Our specialists read the "
           "footnote and the supplier's own bid together, and show the exact words.</p><div class='proofs'>",
           card("1 &middot; The rating", sheet, sheet["quote"], "Kohler KD2000 datasheet (real)"),
           card("2 &middot; The footnote", note, clean, "Same datasheet"),
           card("3 &middot; The bid", bid, bid["quote"], "Supplier's bid (fictional test document)"),
           "</div>",
           f"<div class='sum'><div class='math'>{base} &minus; {less} = {left}&nbsp;&deg;F &lt; {need}&nbsp;&deg;F</div><div class='say'>"
           f"<b>Below what the spec requires.</b> Because a footnote has to be interpreted, the agent does not reject on its own: it "
           f"hands an engineer the three quotes side by side to confirm.</div></div>"]
    if ev:
        S = ev["summary"]
        L, F = S["like_for_like"], S.get("fresh_set6")
        num = lambda v, k, s: f"<div class='num'><div class='v'>{v}</div><div class='k'>{k}</div><div class='s'>{s}</div></div>"
        out.append("<div class='three'>"
                   + num(f"{L['v3']['unresolved']}<span>&rarr;</span>{L['v4']['unresolved']}", "open items needing a person or supplier",
                         f"of {L['v4']['n']} checks on documents we built against, previous version to this one")
                   + num(f"{L['v3']['correct decisions']}<span>&rarr;</span>{L['v4']['correct decisions']}", "correct decisions made without a person",
                         f"same {L['v4']['n']} checks, against our own answer keys")
                   + (num(f"{F['v4']['unresolved']}<span>of</span>{F['v4']['n']}", "still open on datasheets it had never seen",
                          "two new sheets, code frozen first; results and errors below") if F else "")
                   + "</div>")
    out.append("<div class='go'><a class='btn primary' href='#walk'>Follow one decision end to end</a>"
               "<a class='btn' href='#measured'>All results, including errors</a>"
               "<a class='btn' href='#public'>Real supplier records</a></div></section>")
    return "".join(out)


def _walkthrough(s2, state, disc, link, pq2, rec2, names, bv) -> str:
    """One purchase decision from vendor lookup to a verdict backed by exact words: B2's fuel tank."""
    b, rid = "B2", "R19"
    f = next(x for x in rec2[b]["findings"] if x["data"]["req_id"] == rid)
    vid = bv[b]
    vname = names.get(vid, vid)
    rank = next((v for v in disc["ranked"] if v["vendor_id"] == vid), None)
    screen = (disc.get("public_record") or {}).get("screens", {}).get(vname) or {}
    lk = link["products"][b]
    ev_rows = [e for e in rec2[b]["evidence"] if e["req_id"] == rid]
    flagged = [(bb, x) for bb in bv for x in rec2.get(bb, {}).get("findings", [])
               if x["route"].get("kind") in ("conditional rating", "conflicting records")]
    conflict = next(iter(sorted(flagged, key=lambda p: p[1]["route"]["kind"] != "conditional rating")), None)
    reg = ""
    if screen:
        reg = ("<ul class='small'>" + "".join(
            f"<li><b>{_e(lbl)}</b>: {_e(screen[k]['status'])} &middot; {_e(screen[k]['source'])} &middot; looked up {_e(screen[k]['looked_up'])}"
            f"<div class='src'>{_e(screen[k].get('why', ''))}</div></li>" for k, lbl in
            (("entity", "Legal entity"), ("sam_exclusions", "Federal exclusion list"), ("screening_list", "Export/sanctions screen"))) + "</ul>")
    out = [f"<h2 id='walk'>One decision, end to end: does {_e(vname)}'s fuel tank meet the spec?</h2><div class='card scroll'><ol class='walk'>",
           f"<li><b>Vendor lookup</b> (real public sources; this bidder is fictional, so no federal record is expected){reg}</li>",
           f"<li><b>Vendor discovery</b>: ranked #{rank['rank'] if rank else '-'} in the project's vendor master (mock) with {_e(rank['points'] if rank else '-')} points; "
           f"<b>pre-qualification</b>: {_e(pq2[b]['overall'])}.</li>",
           f"<li><b>Which datasheet?</b> {_v(lk['status'])} {_e(lk['why'][:220])}</li>",
           f"<li><b>The spec</b>: {_e(f['claim'])}{_cite(f['citations'][0] if f['citations'] else None, 200)}</li>",
           "<li><b>The evidence record</b> (one row per document and per part of the requirement)<table><tr><th>Part of the requirement</th>"
           "<th>Document</th><th>Revision / date</th><th>Page</th><th>Exact words</th><th>Says</th><th>Role</th><th>Why</th></tr>"
           + "".join(f"<tr><td class='small'>{_e(str(e['attribute']).replace('_', ' '))}</td><td class='small'>{_e(e['document_kind'])}<div class='src'>{_e(e['document'])}</div></td>"
                     f"<td class='small'>{_e(e['revision'] or e['date'] or 'none printed')}</td><td class='n'>{_e(e['page'] or '')}</td>"
                     f"<td>{('<span class=q>' + _e(e['quote'][:90]) + '</span>') if e['quote'] else ''}</td>"
                     f"<td>{_b(e['says'], VERDICT_CLS.get(e['says'], 'mute'))}</td><td>{_b(e['role'], {'controls': 'ok', 'superseded': 'mute', 'conflicts': 'bad'}.get(e['role'], 'info'))}</td>"
                     f"<td class='small'>{_e(e['why'][:150])}</td></tr>" for e in ev_rows) + "</table>"
           + (f"<div class='src'>Supplier {_e(ev_rows[0].get('supplier'))} &middot; bid {b} &middot; items {_e(ev_rows[0].get('tags'))} &middot; model {_e(ev_rows[0].get('model'))}</div>" if ev_rows else "")
           + "</li>",
           f"<li><b>Verdict</b>: {_v(f['status'])} {_r(f['route']['route'])}<div class='small'>Controlling words: "
           + "; ".join(f"{_e(str(e['attribute']).replace('_', ' '))}: \"{_e(e['quote'][:80])}\" ({_e(e['document'])})" for e in ev_rows if e["role"] == "controls")
           + "</div></li></ol>"]
    if conflict:
        bb, x = conflict
        reason = next((c["why"] for c in x["data"]["conditions"] if c.get("kind") in ("conditional rating", "conflicting records")), x["why"])
        quotes = [c for c in x["citations"][1:] if not str(c.get("doc_id", "")).startswith("equipment")]
        out.append(f"<h3>Where the same method exposes a problem for review instead: {_e(bb)} {_e(x['data']['req_id'])}</h3>"
                   f"<p class='small'>{_e(x['claim'])}</p><p>{_e(reason[:460])}</p>" + "".join(_cite(c, 170) for c in quotes)
                   + f"<p>{_v(x['status'])} {_r(x['route']['route'])} <span class='small'>{_e(x['route'].get('why', ''))}</span></p>")
    out.append("</div>")
    return "".join(out)


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
    out.append(_front(rec2, ev))
    out.append(f"<h2 class='case'>The whole purchase: {_e(state['goal'])}</h2><p class='lead'>Thirteen steps ran as one case file that remembers what each step "
               "found and resumes where it stopped. Every answer below cites its source; every number in the measured section "
               "comes from <span class='mono'>scripts/eval_handoffs.py</span>. Labels: <span class='tag m'>measured</span> "
               "<span class='tag k'>mock data</span> <span class='tag a'>assumption</span>.</p>")
    out.append("<div class='toc'>" + "".join(f"<a href='#{a}'>{t}</a>" for a, t in [
        ("walk", "One decision"), ("change", "Before and after"), ("measured", "Measured"), ("public", "Public records"), ("steps", "Steps & resume"), ("decision", "Decision"), ("discovery", "Vendor discovery"),
        ("prequal", "Pre-qualification"), ("links", "Record links"), ("reconcile", "Reconciled answers"), ("ranges", "Ranges"),
        ("triage", "Who acts"), ("replies", "Questions & replies")]) + "</div>")

    # ---- one decision, end to end
    out.append(_walkthrough(s2, state, disc, link, pq2, rec2, names, bv))

    # ---- measured
    if ev:
        out.append(_measured(ev, eval_file.with_name("package_compare.json")))

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
    out.append(_public_record(disc.get("public_record") or {}))
    out.append("<h2 id='discovery'>The project's own vendor master <span class='tag k'>mock vendor master</span></h2><div class='card scroll'>"
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
    key = json.loads((ROOT / "eval" / "answer_keys" / "replies_GEN.json").read_text(encoding="utf-8"))["replies"]
    scored = [(b, rid, exp, next(f for f in rec2[b]["findings"] if f["data"]["req_id"] == rid)["status"])
              for b, v in key.items() for rid, (exp, _) in v["requirements"].items()]
    asked_clar = sum(1 for b in key for f in rec1[b]["findings"] if f["route"].get("kind") == "clarification")
    verified = sum(1 for b in key for f in rec1[b]["findings"] if f["route"].get("kind") == "clarification"
                   and (b, f["data"]["req_id"]) in {(x[0], x[1]) for x in scored if x[2] == x[3] and x[2] != "unclear"})
    out.append(f"<p class='small'>Replies scored against their key, written before they were read: <b>{sum(1 for x in scored if x[2] == x[3])} of "
               f"{len(scored)}</b> answers right. Focused clarifications asked of these two suppliers: {asked_clar}; settled by a reply "
               f"with a verified correct answer: <b>{verified}</b>. The replies are mock documents.</p></div>")
    out.append("<p class='small'>Built by amber/case_page.py from examples/case_GEN (scripts/snapshot_case.py) and "
               "eval/handoff_set/results.json (scripts/eval_handoffs.py).</p></div></body></html>")
    return "".join(out)


def write(path: Path, back_href: str = "./") -> Path:
    path.write_text(render(back_href=back_href), encoding="utf-8")
    return path
