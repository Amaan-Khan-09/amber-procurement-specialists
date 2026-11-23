"""Render a package-review result as one self-contained HTML page (used by scripts/make_report.py and the web page).

No external assets: works offline, prints cleanly, follows the OS light/dark setting.
"""
import html
from datetime import date

E = html.escape
BADGE = {"complies": "ok", "deviates": "bad", "missing": "warn", "unclear": "warn"}
CELL = {"included": "ok", "excluded": "bad", "qualified": "warn", "silent": "mute", "alternate": "info", "unclear": "warn"}

CSS = """
:root{--bg:#f7f8fa;--card:#fff;--ink:#1b2430;--mute:#667085;--line:#e3e7ee;--ok:#117a43;--okbg:#e4f4ea;--bad:#b42318;--badbg:#fde8e6;
--warn:#9a5b00;--warnbg:#fff1d6;--info:#1b5fc1;--infobg:#e3edfb;--accent:#173f7a}
@media (prefers-color-scheme:dark){:root{--bg:#0f141b;--card:#171e28;--ink:#e6ebf2;--mute:#97a3b6;--line:#2a3442;--ok:#59d38c;--okbg:#12301f;
--bad:#ff8a80;--badbg:#3a1714;--warn:#f5b84b;--warnbg:#3a2a0c;--info:#7db2ff;--infobg:#162a47;--accent:#7db2ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,Segoe UI,Roboto,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 64px}h1{font-size:24px;margin:0 0 4px}h2{font-size:17px;margin:32px 0 10px}
.sub{color:var(--mute);margin:0 0 18px}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:14px}
table{border-collapse:collapse;width:100%}th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;font-size:14px}
th{color:var(--mute);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.b{display:inline-block;padding:1px 9px;border-radius:99px;font-size:12px;font-weight:600}
.ok{color:var(--ok);background:var(--okbg)}.bad{color:var(--bad);background:var(--badbg)}.warn{color:var(--warn);background:var(--warnbg)}
.info{color:var(--info);background:var(--infobg)}.mute{color:var(--mute);background:var(--line)}
.banner{border-left:5px solid var(--warn);background:var(--warnbg);color:var(--ink)}.banner.safe{border-color:var(--ok);background:var(--okbg)}
.banner h3{margin:0 0 6px;font-size:16px}.banner li{margin:2px 0}
.cell{text-align:center;font-size:12px;font-weight:600;border-radius:6px;padding:3px 6px;white-space:nowrap}
q{display:block;color:var(--mute);font-size:12.5px;margin:2px 0 0;quotes:"\\201C" "\\201D"}.cite{font-size:12.5px;color:var(--mute)}
.cite b{color:var(--ink)}details summary{cursor:pointer;color:var(--accent);font-size:13px}svg text{fill:var(--mute);font-size:11px}
.small{font-size:12.5px;color:var(--mute)}@media print{body{background:#fff}.card{break-inside:avoid}}
"""


def money(x):
    return f"${x:,.0f}" if x is not None else "-"


def cites(f):
    out = []
    for c in f.get("citations", []):
        scan = " (scanned page, read by OCR)" if c.get("ocr") else ""
        out.append(f'<div class="cite"><b>{E(c["doc_id"])}</b> p.{c["page"]} {E(c.get("locator") or "")}{scan}<q>{E(c["quote"][:220])}</q></div>')
    return "".join(out)


def delivery_chart(rows):
    """P10-P90 bars with a P50 tick, one per scenario, and the need date as a vertical line."""
    if not rows:
        return ""
    d = lambda s: date.fromisoformat(s).toordinal()
    lo = min(d(r["arrival"]["P10"]) for r in rows)
    hi = max(d(r["arrival"]["P90"]) for r in rows)
    need = d(rows[0]["need_on_site"])
    lo, hi = min(lo, need) - 20, max(hi, need) + 20
    W, L, R, H = 1000, 200, 30, 36
    x = lambda o: L + (o - lo) / (hi - lo) * (W - L - R)
    h = 34 + H * len(rows)
    s = [f'<svg viewBox="0 0 {W} {h}" width="100%" role="img" aria-label="Delivery forecast: P10 to P90 arrival range per option against the need date">']
    for m in range(lo - lo % 1, hi, 1):
        dt = date.fromordinal(m)
        if dt.day == 1 and dt.month in (1, 4, 7, 10):
            s.append(f'<line x1="{x(m):.1f}" x2="{x(m):.1f}" y1="14" y2="{h - 6}" stroke="var(--line)"/><text x="{x(m) + 3:.1f}" y="11">{dt.strftime("%b %Y")}</text>')
    for i, r in enumerate(rows):
        y = 28 + i * H
        a = r["arrival"]
        col = "var(--bad)" if r["risk"] == "high" else "var(--warn)" if r["risk"] == "medium" else "var(--ok)"
        s.append(f'<text x="{L - 8}" y="{y + 12}" text-anchor="end" style="fill:var(--ink);font-size:12.5px">{E(r["label"])}</text>')
        s.append(f'<rect x="{x(d(a["P10"])):.1f}" y="{y}" width="{max(2, x(d(a["P90"])) - x(d(a["P10"]))):.1f}" height="16" rx="4" fill="{col}" opacity=".35"/>')
        s.append(f'<line x1="{x(d(a["P50"])):.1f}" x2="{x(d(a["P50"])):.1f}" y1="{y - 2}" y2="{y + 18}" stroke="{col}" stroke-width="3"/>')
        s.append(f'<text x="{x(d(a["P90"])) + 6:.1f}" y="{y + 12}">{int(round(r["p_late"] * 100))}% late</text>')
    s.append(f'<line x1="{x(need):.1f}" x2="{x(need):.1f}" y1="14" y2="{h - 6}" stroke="var(--info)" stroke-width="2" stroke-dasharray="5 4"/>'
             f'<text x="{x(need) + 5:.1f}" y="{h - 8}" style="fill:var(--info)">need on site {date.fromordinal(need).strftime("%d %b %Y")}</text></svg>')
    return "".join(s)


def render(res: dict) -> str:
    R, dec, parts = res["result"], res["result"]["decision"], res["result"]["parts"]
    lb, run = parts["level_bids"], res["run"]
    findings = res["findings"]

    body = [f"<h1>{E(R.get('package') or 'Package review')}</h1>"]
    models = ", ".join(f'{m["name"]} ({m["calls"]} calls)' for m in run["models"]) or "no model calls"
    cost = sum(m["cost_usd"] for m in run["models"])
    body.append(f'<p class="sub">{len(findings)} findings · {len(res["needs_human"])} for a person to review · models: {E(models)} · '
                f'est. cost ${cost:.3f} · {run["latency_ms"] // 1000}s · forecast as of {E(parts["delivery"]["as_of"])}</p>')

    safe = dec.get("auto_award")
    notes = "".join(f"<li>{E(n)}</li>" for n in dec.get("notes", []))
    why = E(dec.get("level_bids_reason") or "")
    body.append(f'<div class="card banner {"safe" if safe else ""}"><h3>{"Award recommended: " + E(str(dec.get("recommend"))) if safe else "No automatic award: a person should decide"}</h3>'
                f'<ul>{notes}</ul><div class="small">{why}</div></div>')

    body.append("<h2>Bidders side by side</h2><div class='card'><table><tr><th>Bid</th><th>Product</th><th class='n'>Leveled cost</th>"
                "<th>Scope gaps</th><th>Product vs spec</th><th>Typical arrival</th><th class='n'>Chance late</th></tr>")
    for r in R["comparison"]:
        sub = r["submittal"]
        late = "-" if r["p_late"] is None else "{:.0%}".format(r["p_late"])
        cls = {"reject": "bad", "review": "warn", "approve": "ok"}.get(sub, "mute")
        body.append(f'<tr><td><b>{E(r["bid"])}</b></td><td>{E(str(r["product"]))}</td><td class="n">{money(r["leveled_cost"])}'
                    f'<div class="small">base {money(r["base"])}</div></td><td>{len(r["scope_gaps"])} of {len(lb["scope"])}</td>'
                    f'<td><span class="b {cls}">{E(sub)}</span></td><td>{E(str(r["arrival_P50"]))}</td>'
                    f'<td class="n">{late}</td></tr>')
    body.append("</table></div>")

    body.append("<h2>What each bid covers</h2><div class='card' style='overflow-x:auto'><table><tr><th>Scope item</th>" +
                "".join(f"<th>{E(b)}</th>" for b in lb["matrix"]) + "</tr>")
    qmap = {}
    for f in findings:
        if f["id"].startswith("level_bids/F-B") and f.get("citations"):
            qmap[(f["data"].get("bid"), f["data"].get("scope_id"))] = f["citations"][0]["quote"]
    for s in lb["scope"]:
        body.append(f'<tr><td><b>{E(s["id"])}</b> {E(s["item"])}</td>')
        for b in lb["matrix"]:
            st = lb["matrix"][b].get(s["id"], "?")
            tip = qmap.get((b, s["id"]), "")
            body.append(f'<td><div class="cell {CELL.get(st, "mute")}" title="{E(tip)}">{E(st)}</div></td>')
        body.append("</tr>")
    body.append("</table><p class='small'>Hover a cell for the bid's own words. Totals: " +
                " · ".join(f'{b}: {money(v["adjusted"])}' for b, v in lb["leveling"].items()) + "</p></div>")

    rows = []
    award_rows = [f for f in findings if f["id"].startswith("delivery/") and f["data"].get("arrival")
                  and f["data"].get("scenario", "").startswith("award")]
    group = award_rows[0]["data"]["tag_group"] if award_rows else None  # only this package's own item group
    for f in award_rows:
        rows.append(dict(f["data"], label=f["data"]["scenario"].replace("award to ", "Award to ")))
    for f in findings:
        if f["id"].startswith("delivery/") and f["data"].get("scenario") == "market (not ordered)" and f["data"].get("tag_group") == group:
            rows.append(dict(f["data"], label="Market average (no bidder)"))
    body.append("<h2>When will it arrive?</h2><div class='card'>" + delivery_chart(rows) +
                "<p class='small'>Bar = earliest-likely to latest-likely arrival (P10 to P90), tick = typical (P50). "
                "Built in code from cited lead-time evidence and each bid's quoted lead time.</p>")
    if rows:
        ev = rows[0]["evidence"]
        body.append("<details><summary>Evidence behind the forecast</summary><table><tr><th>Source</th><th class='n'>Weeks</th><th class='n'>Weight</th><th>Note</th></tr>" +
                    "".join(f'<tr><td>{E(e["source"])}</td><td class="n">{e["range_weeks"][0]:.0f}-{e["range_weeks"][1]:.0f}</td>'
                            f'<td class="n">{e["weight"]}</td><td>{"<span class=&quot;b warn&quot;>dissent</span> " if e["dissent"] else ""}{E("; ".join(e["notes"]))}</td></tr>' for e in ev) +
                    "</table></details>")
    body.append("</div>")

    for b in R["comparison"]:
        fs = [f for f in findings if f["id"].startswith(f"submittal:{b['bid']}/")]
        if not fs:
            continue
        sm = parts["submittals"][b["bid"]]["summary"]
        body.append(f'<h2>{E(b["bid"])}: product submittal against the spec</h2><div class="card"><div class="small">'
                    + " · ".join(f"{v} {k}" for k, v in sm.items()) + "</div><table><tr><th>Requirement</th><th>Verdict</th><th>Evidence</th></tr>")
        for f in fs:
            human = ' <span class="b info">for review</span>' if f["needs_human"] else ""
            body.append(f'<tr><td>{E(f["claim"])}<div class="small">{E(str(f["data"].get("locator", "")))}</div></td>'
                        f'<td><span class="b {BADGE[f["status"]]}">{f["status"]}</span>{human}<div class="small">{f["confidence"]:.2f}</div></td>'
                        f'<td>{E(f["why"][:230])}<details><summary>sources</summary>{cites(f)}</details></td></tr>')
        body.append("</table></div>")

    drafts = R.get("follow_ups") or []
    if drafts:
        body.append(f"<h2>Next action: {len(drafts)} follow-up drafts ready for review</h2><div class='card'>"
                    "<p class='small'>Built only from verified findings: every quoted fact has its document and page. "
                    "Nothing is sent automatically.</p>")
        for d in drafts:
            body.append(f"<details><summary>{E(d['to'])}: {E(d['subject'])} ({d['items']} items)</summary>"
                        f"<pre style='white-space:pre-wrap;font-size:12.5px'>{E(d['body'])}</pre></details>")
        body.append("</div>")
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                   f'<title>{E(R.get("package") or "Package review")}</title><style>{CSS}</style></head><body><main>{"".join(body)}</main></body></html>')
