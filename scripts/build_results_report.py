"""docs/RESULTS.md from the evaluation files: the before-and-after tables and every case that changed.

usage: python scripts/build_results_report.py   (after scripts/eval_handoffs.py)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "RESULTS.md"
METRICS = [("to an engineer", "Sent to an engineer"), ("clarification requests", "Focused clarification asked"),
           ("supplier questions", "Other question to the supplier"), ("correct decisions", "Correct decision made alone"),
           ("well-founded questions", "Questions the key agrees are needed"), ("questions not needed", "Questions not needed"),
           ("incorrect decisions (critical)", "Wrong decision, critical"), ("incorrect decisions (minor)", "Wrong decision, minor"),
           ("missed escalations", "Missed mandatory escalation"), ("unnecessary hand-offs", "Unnecessary hand-off"),
           ("right action", "Right action on any route")]
KIND = {"confirm a reading": "the evidence is judged, not computed: a term or unit the code cannot confirm from the quote",
        "contested": "the two models disagree and the disputed clause does not settle it",
        "judgement": "engineering judgement (partial statements, conditions, discarded values)",
        "absence not confirmed": "the document was not read a second time (large or scanned): absence unconfirmed",
        "conditional rating": "a derating footnote changes the rating when a fitted option applies"}


def table(title: str, s: dict) -> str:
    n = s["v3"]["n"]
    rows = [f"### {title} (n = {n})", "", "| Outcome | v1 | v2 (baseline) | v3 (now) |", "|---|---|---|---|"]
    for k, lab in METRICS:
        rows.append(f"| {lab} | " + " | ".join(f"{s[v][k]} ({s[v][k] / n:.0%})" for v in ("v1", "v2", "v3")) + " |")
    return "\n".join(rows) + "\n"


def cases(rows: list[dict]) -> str:
    out = ["| Case | Key | v2 | v3 | Why |", "|---|---|---|---|---|"]
    for r in rows:
        why = (r["v3"].get("why") or r["v3"].get("kind") or "").replace("|", "/").replace("\n", " ")[:140]
        out.append(f"| {r['id']} | {r['expected']} | {r['v2']['answer']}, {r['v2']['route']} | {r['v3']['answer']}, {r['v3']['route']}"
                   f" ({r['v3']['outcome']}) | {why} |")
    return "\n".join(out) + "\n" if rows else "None.\n"


def main() -> None:
    res = json.loads((ROOT / "eval/handoff_set/results.json").read_text(encoding="utf-8"))
    fresh = json.loads((ROOT / "eval/handoff_set/fresh_unseen.json").read_text(encoding="utf-8"))
    S, rows = res["summary"], res["results"]
    like = [r for r in rows if r["group"] not in ("prequal", "unseen datasheet", "fresh unseen")]
    changed = [r for r in like if (r["v2"]["outcome"], r["v2"]["route"]) != (r["v3"]["outcome"], r["v3"]["route"])]
    worse = [r for r in changed if r["v3"]["outcome"] in ("incorrect decision", "missed escalation")
             or r["v3"]["outcome"].endswith("not needed") or (r["v3"]["outcome"] == "unnecessary hand-off" and r["v2"]["outcome"] != "unnecessary hand-off")]
    better = [r for r in changed if r not in worse and (r["v3"]["outcome"] == "correct decision" or r["v3"]["outcome"].endswith("well-founded"))]
    other = [r for r in changed if r not in worse and r not in better]
    eng = [r for r in like if r["v3"]["route"] == "engineer"]
    kinds: dict = {}
    for r in eng:
        kinds.setdefault(r["v3"].get("kind"), []).append(r)
    md = ["# Results: before and after", "",
          "Every number comes from `python scripts/eval_handoffs.py` (all three versions read the same saved model output).", "",
          "* **v1** anything under 0.70 goes to one queue (commit 48b321c).",
          "* **v2** the baseline for this round (commit 9cd1b4e): decided / ask the supplier / engineer, supplier documents reconciled.",
          "* **v3** now: v2 plus a second look in code at the disputed clause and its evidence (`amber/inspect_evidence.py`, `amber/evidence.py`).",
          "", "A **clarification** is never counted as a resolution here: it is scored as a question. Resolution by follow-up is "
          "scored only where a reply exists (the case file). A **wrong decision** is critical when it approves what fails or is not "
          "shown, or rejects what complies. Answer keys were written by an AI before the code they score; no person has reviewed them.", "",
          "## Fixed development set (documents seen while building: a repair record)", "", table("All like-for-like cases", S["like_for_like"])]
    for g, label in (("datasheet", "Datasheet requirements"), ("package", "Bid and datasheet together"), ("link", "Product links"),
                     ("bid scope", "Bid scope cells")):
        md.append(table(label, S["by_group"][g]))
    pc = json.loads((ROOT / "eval/handoff_set/package_compare.json").read_text(encoding="utf-8"))
    cols = list(next(iter(pc["summary"].values())))
    md += ["## The same 22 package cases, four ways (`python scripts/compare_package.py`)", "",
           "| Variant | " + " | ".join(cols) + " |", "|---" * (len(cols) + 1) + "|"]
    md += [f"| {v} | " + " | ".join(str(s[c]) for c in cols) + " |" for v, s in pc["summary"].items()]
    md += ["", "**Correction.** We earlier wrote that reading the supplier's bid cut engineer hand-offs from 13 to 6 compared with the "
           "datasheet alone. That compared two changes at once (the routing and the extra document). With the same routing on both "
           "sides it is **8 to 6**; the gain in right actions (16 to 21 of 22) holds. The improved version gets all 22 right (the "
           "former miss, B2 R21, called a bid's 'weather protective' a deviation) at the price of one more hand-off. These 22 cases "
           "were inspected while fixing them: a repair record.", "",
           "## Fresh unseen datasheets (held-out set 5)", "",
           f"Multiquip EGC2000C (G10) and Kohler 2000REOZMD (G11). Decision code frozen at `{fresh['frozen_commit']}`; answer keys committed "
           f"after the freeze and before any model read the sheets; read once. Reading model **{fresh['extraction_model']}** (the "
           "`gpt-oss-120b` daily free allowance ran out part-way through G10; that partial run is kept as "
           "`examples/incomplete/G10_gpt120b_incomplete.json` and is not used). Second reader: " + fresh["reader_model"] + ". Both versions ran on identical readings.", "",
           table("Both sheets, frozen code (the unseen result)", fresh["summary"]["all"]),
           table("G10 Multiquip: conditional derating, container options", fresh["summary"]["G10"]),
           table("G11 Kohler: two radiator systems, multi-page tables", fresh["summary"]["G11"]),
           "**The unseen result does not pass cleanly:** v3 added one wrong decision. G10 R08: it computed a verdict from "
           "\"Max Fuel Flow 158 gal/hr\" as if it were fuel consumption (the key says unclear: only the prime-power consumption is "
           "stated). Fixed afterwards with a same-quantity guard and a regression test.", ""]
    after = S.get("fresh_unseen_set5")
    if after:
        md.append(table("The same two sheets after the fix (a repair record, NOT an unseen result)", after))
    if S.get("unseen_set4"):
        md += ["## Earlier unseen sheet G9 (inspected since: now a regression case)", "", table("Generac MD2000", S["unseen_set4"])]
    md += ["## What changed from v2 to v3 (development set)", "", f"### Improved ({len(better)})", "", cases(better),
           f"### Got worse ({len(worse)})", "", cases(worse), f"### Changed, neither ({len(other)})", "", cases(other),
           f"## Why {len(eng)} cases still reach an engineer", "", "| Reason | Cases | The key agrees an engineer (or a different answer) is needed | Case ids |", "|---|---|---|---|"]
    for k, v in sorted(kinds.items(), key=lambda kv: -len(kv[1])):
        md.append(f"| {KIND.get(k, 'an award or schedule decision')} | {len(v)} | {sum(r['v3']['outcome'] == 'justified hand-off' for r in v)} | "
                  f"{', '.join(r['id'] for r in v)} |")
    wrong = [r for r in rows if r["v3"]["outcome"] in ("incorrect decision", "missed escalation")]
    md += ["", "## Every wrong decision v3 still makes", "", cases(wrong)]
    OUT.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: better {len(better)}, worse {len(worse)}, engineer {len(eng)}, wrong {len(wrong)}")


if __name__ == "__main__":
    main()
