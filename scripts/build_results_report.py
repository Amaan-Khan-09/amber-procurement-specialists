"""docs/RESULTS.md from the evaluation files: every version side by side and every case that changed.

usage: python scripts/build_results_report.py   (after scripts/eval_handoffs.py and scripts/compare_package.py)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "RESULTS.md"
SET = ROOT / "eval/handoff_set"
METRICS = [("to an engineer", "Sent to an engineer"), ("supplier questions", "Question to the supplier"),
           ("clarification requests", "Focused clarification"), ("unresolved", "**Unresolved (engineer + any question)**"),
           ("correct decisions", "Correct decision made alone"), ("incorrect decisions (critical)", "Wrong decision, critical"),
           ("incorrect decisions (minor)", "Wrong decision, minor"), ("missed escalations", "Missed mandatory escalation"),
           ("well-founded questions", "Questions the key agrees are needed"), ("questions not needed", "Questions not needed"),
           ("unnecessary hand-offs", "Unnecessary hand-off"), ("right action", "Right action on any route")]
LABEL = {"v1": "v1", "v2": "v2 original", "v3": "v3 previous", "v4": "v4 candidate"}
KIND = {"confirm a reading": "judged, not computable: a term or unit the code cannot confirm",
        "contested": "the two models disagree and the disputed clause does not settle it",
        "judgement": "engineering judgement (partial or conditional statements, discarded values)",
        "absence not confirmed": "large document: absence not confirmed by a whole second reading",
        "conditional rating": "a derating footnote applies when a fitted option is fitted"}


def table(title: str, s: dict) -> str:
    if not s:
        return ""
    vs = [v for v in LABEL if v in s]
    n = s[vs[0]]["n"]
    rows = [f"### {title} (n = {n})", "", "| Outcome | " + " | ".join(LABEL[v] for v in vs) + " |", "|---" * (len(vs) + 1) + "|"]
    rows += [f"| {lab} | " + " | ".join(f"{s[v][k]} ({s[v][k] / n:.0%})" for v in vs) + " |" for k, lab in METRICS]
    return "\n".join(rows) + "\n"


def cases(rows: list[dict], a: str = "v3", b: str = "v4") -> str:
    if not rows:
        return "None.\n"
    out = [f"| Case | Key | {a} | {b} | Why ({b}) |", "|---|---|---|---|---|"]
    for r in rows:
        why = (r[b].get("why") or r[b].get("kind") or "").replace("|", "/").replace("\n", " ")[:150]
        out.append(f"| {r['id']} | {r['expected']}, {r['expected_route']} | {r[a]['answer']}, {r[a]['route']} ({r[a]['outcome']}) | "
                   f"{r[b]['answer']}, {r[b]['route']} ({r[b]['outcome']}) | {why} |")
    return "\n".join(out) + "\n"


GOOD = lambda o: o == "correct decision" or o.endswith("well-founded") or o == "justified hand-off"
BAD = ("incorrect decision", "missed escalation")


def split(rows: list[dict], a: str = "v3", b: str = "v4"):
    changed = [r for r in rows if (r[a]["answer"], r[a]["route"]) != (r[b]["answer"], r[b]["route"])]
    worse = [r for r in changed if r[b]["outcome"] in BAD or r[b]["outcome"].endswith("not needed")
             or (r[b]["outcome"] == "unnecessary hand-off" and GOOD(r[a]["outcome"]))]
    better = [r for r in changed if r not in worse and GOOD(r[b]["outcome"])]
    return better, worse, [r for r in changed if r not in better and r not in worse]


def main() -> None:
    res = json.loads((SET / "results.json").read_text(encoding="utf-8"))
    S, rows = res["summary"], res["results"]
    like = [r for r in rows if r["group"] in ("datasheet", "package", "link", "bid scope", "decision")]
    fresh = [r for r in rows if r["group"] == "fresh set 6"]
    better, worse, other = split(like)
    md = ["# Results", "", "Every number comes from `python scripts/eval_handoffs.py`. All versions read the same saved model output; "
          "earlier versions' answers are the ones their own code produced (`eval/handoff_set/frozen/`), re-scored against today's keys.", "",
          *[f"* **{LABEL[v]}**: {d}" for v, d in S["versions"].items()], "",
          "**Unresolved** is every case sent to an engineer or put to a supplier. No fixed-set case has a supplier follow-up, so no "
          "question is counted as resolved. A **wrong decision** is critical when it approves what fails or is not shown, or rejects "
          "what complies. A **missed escalation** is any case the key gives to an engineer that was decided or merely asked "
          "(tightened this round; earlier versions have none under either definition). Answer keys were written by an AI before the "
          "code they score. **No person has reviewed them yet.**", ""]
    if fresh:
        md += ["## Fresh datasheets (held-out set 6): candidate frozen first, read once", "", table("Both fresh sheets", S["fresh_set6"]),
               "Every case that differs between the previous version and the candidate:", "", cases([r for r in fresh if (r["v3"]["answer"], r["v3"]["route"]) != (r["v4"]["answer"], r["v4"]["route"])]),
               "Every wrong decision or missed escalation by any version on these sheets:", "",
               cases([r for r in fresh if any(r[v]["outcome"] in BAD for v in ("v2", "v3", "v4"))], "v2", "v4")]
    md += ["## Fixed development set (documents seen while building: a repair record, not an unseen score)", "",
           table("All like-for-like cases", S["like_for_like"])]
    for g, label in (("datasheet", "Datasheet requirements"), ("package", "Bid and datasheet together"), ("link", "Product links"),
                     ("bid scope", "Bid scope cells")):
        md.append(table(label, S["by_group"][g]))
    pc = json.loads((SET / "package_compare.json").read_text(encoding="utf-8"))
    cols = list(next(iter(pc["summary"].values())))
    md += ["## The same 22 package cases with identical routing (`python scripts/compare_package.py`)", "",
           "Performance **on cases we worked on**.", "", "| Variant | " + " | ".join(cols) + " |", "|---" * (len(cols) + 1) + "|"]
    md += [f"| {v} | " + " | ".join(str(s[c]) for c in cols) + " |" for v, s in pc["summary"].items()]
    md += ["", "## Inspected sheets, now regression material", "", table("G9 Generac", S.get("regression_set4")),
           table("G10 Multiquip and G11 Kohler (fresh last round; an error was found and fixed there)", S.get("regression_set5")),
           "## Development set: previous version to candidate", "", f"### Improved ({len(better)})", "", cases(better),
           f"### Got worse ({len(worse)})", "", cases(worse), f"### Changed, neither ({len(other)})", "", cases(other)]
    eng = [r for r in like if r["v4"]["route"] == "engineer"]
    kinds: dict = {}
    for r in eng:
        kinds.setdefault(r["v4"].get("kind"), []).append(r)
    md += [f"## Why {len(eng)} development cases still reach an engineer", "",
           "| Reason | Cases | Key agrees (an engineer, or a different answer, is needed) | Case ids |", "|---|---|---|---|"]
    md += [f"| {KIND.get(k, 'an award or schedule decision')} | {len(v)} | {sum(r['v4']['outcome'] == 'justified hand-off' for r in v)} | "
           f"{', '.join(r['id'] for r in v)} |" for k, v in sorted(kinds.items(), key=lambda kv: -len(kv[1]))]
    absent = [r for r in rows if r["v3"].get("kind") == "absence not confirmed"]
    md += ["", f"## The {len(absent)} large-document cases after the targeted second reading", "",
           "The second reader read only the pages that mention each open item (`scripts/targeted_read.py`). What it quotes is used; "
           "\"not found\" on selected pages is **not** treated as confirmation (that rule was added after it sent one must-escalate "
           "item to the supplier).", "", cases(absent)]
    md += ["## Every wrong decision or missed escalation the candidate makes", "",
           cases([r for r in rows if r["v4"]["outcome"] in BAD])]
    OUT.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: better {len(better)}, worse {len(worse)}, engineer {len(eng)}, "
          f"wrong {sum(r['v4']['outcome'] in BAD for r in rows)}")


if __name__ == "__main__":
    main()
