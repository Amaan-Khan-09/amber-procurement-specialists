"""Build the human review packet for the answer keys.

Every cell where the blind reviewer (a different model family) disagrees with our key, plus a seeded random sample of the
cells where they agree (so the human also checks the agreed ones), as a checklist with the datasheet page to open.
A person (not the author of the keys) fills in "human_label" and their name; scripts/apply_human_review.py then reports the
key's agreement with that person and what the accuracy numbers would be under the person's labels. Nothing is changed
automatically.

usage: python scripts/build_review_packet.py [--reviewer qwen3.8-27b] [--agreed-sample 12] [--seed 7]
writes eval/cross_checks/REVIEW.md and eval/cross_checks/human_review.csv
"""
import argparse
import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEYS, EXAMPLES, OUT = ROOT / "eval" / "answer_keys", ROOT / "examples", ROOT / "eval" / "cross_checks"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reviewer", default="qwen3.8-27b")
    ap.add_argument("--agreed-sample", type=int, default=12)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    rev = json.loads((OUT / f"{a.reviewer}.json").read_text(encoding="utf-8"))
    cells = []
    for cid, r in rev.items():
        key = json.loads((KEYS / f"{cid}.json").read_text(encoding="utf-8"))
        run = json.loads((EXAMPLES / f"{cid}.json").read_text(encoding="utf-8"))
        claims = {f["data"]["req_id"]: f["claim"] for f in run["findings"] if "req_id" in (f.get("data") or {})}
        for l in key["labels"]:
            ans = r["answers"][l["req_id"]]
            cells.append({"case": cid, "doc": Path(key["submittal"]).name, "req_id": l["req_id"], "requirement": claims[l["req_id"]],
                          "key": l["expected"], "key_page": l.get("submittal_page"), "key_quote": l.get("submittal_quote") or "",
                          "key_note": l.get("notes") or "", "reviewer": ans["verdict"], "reviewer_page": ans.get("page"),
                          "reviewer_quote": ans.get("quote") or "", "agree": l["expected"] == ans["verdict"]})
    disagree = [c for c in cells if not c["agree"]]
    agreed = [c for c in cells if c["agree"]]
    random.Random(a.seed).shuffle(agreed)
    sample = sorted(agreed[:a.agreed_sample], key=lambda c: (c["case"], c["req_id"]))
    chosen = sorted(disagree + sample, key=lambda c: (c["case"], c["req_id"]))

    lines = [
        "# Review packet: are the answer keys right?",
        "",
        f"The answer keys were written by the project author, with AI assistance. A model of a different family "
        f"(`{a.reviewer}`) then labelled the same datasheets **blind**: it never saw the keys or our pipeline. This packet lists "
        f"every cell where the two disagree ({len(disagree)} of {len(cells)}) and a random sample of {len(sample)} cells where they "
        "agree. Please decide each one yourself from the datasheet, then fill `human_review.csv`.",
        "",
        "## How to review (about 2 minutes a cell)",
        "1. Open the datasheet named in the cell (download them with `python tools/data_prep/fetch_data.py`, or use the copies "
        "the author gave you) and go to the page given.",
        "2. Read the requirement. Decide from the **datasheet alone**, without looking at the two labels first if you can:",
        "   - `complies`: the datasheet clearly states something that meets it",
        "   - `deviates`: it clearly states something that does not meet it",
        "   - `missing`: it says nothing about it",
        "   - `unclear`: it is mentioned (an option that is not marked as supplied, a claim without numbers) but you cannot tell "
        "whether it is met without asking the supplier",
        "3. Rules of thumb: options (voltages, tanks, heaters, breakers) comply only if the *selected* one is marked; check units "
        "(kW and kVA are different, 1 gph = 3.785 L/h); the spec asks for *standby* ratings.",
        "4. Write your label in `human_review.csv` (columns `human_label`, `human_note`, `reviewer_name`).",
        "",
        "Do not change `key` or `model` columns. Your answers are used to report how often the key agrees with an independent person.",
        "",
        f"## {len(chosen)} cells",
        "",
    ]
    for c in chosen:
        tag = "DISAGREE" if not c["agree"] else "agreed (sample)"
        lines += [
            f"### {c['case']} {c['req_id']}: {tag}",
            f"- **Datasheet:** `{c['doc']}`",
            f"- **Requirement:** {c['requirement']}",
            f"- **Key says `{c['key']}`**" + (f" (p.{c['key_page']}: \"{c['key_quote']}\")" if c["key_quote"] else "") + (f". Note: {c['key_note']}" if c["key_note"] else ""),
            f"- **Blind model says `{c['reviewer']}`**" + (f" (p.{c['reviewer_page']}: \"{c['reviewer_quote']}\")" if c["reviewer"] in ("complies", "deviates") and c["reviewer_quote"] else (f" ({c['reviewer_quote']})" if c["reviewer_quote"] else "")),
            "- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear",
            "",
        ]
    (OUT / "REVIEW.md").write_text("\n".join(lines), encoding="utf-8")
    with open(OUT / "human_review.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["case", "req_id", "datasheet", "requirement", "key", "model", "human_label", "human_note", "reviewer_name"])
        for c in chosen:
            w.writerow([c["case"], c["req_id"], c["doc"], c["requirement"], c["key"], c["reviewer"], "", "", ""])
    print(f"{len(cells)} cells compared, {len(disagree)} disagree; packet has {len(chosen)} cells -> eval/cross_checks/REVIEW.md and human_review.csv")


if __name__ == "__main__":
    main()
