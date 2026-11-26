"""The blind review sheet for a person: is each expected answer right? Nothing shows which version produced anything.

Selected (from eval/handoff_set/results.json):
  changed     the candidate now decides on its own and the original baseline did not give the same decision
  critical    any wrong decision or missed escalation, in any version
  disputed    the independent reader disagrees with the key on a case the candidate does not match, the labeller's own
              judgement calls, and routes that rest on a keyword in the labeller's note
  sample      a random sample (fixed seed) of cases that did not change
Rows are shuffled and numbered; the map from item number to case id and the versions' answers stays in
eval/review/mapping.json, which the reviewer does not need and should not open.

usage: python scripts/build_blind_review.py <output folder>   then   python scripts/apply_blind_review.py <filled csv>
"""
import csv
import json
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import eval_handoffs as E  # noqa: E402

KEYS = ROOT / "eval" / "answer_keys"
JUDGEMENT_CALLS = {"G2/R03", "G6/R03", "G2/R07", "G5/R07", "G6/R07", "G8/R07", "G2/R09", "G2/R19", "G2/R20", "G4/R20",
                   "G4/R12", "G5/R01", "G5/R09", "G1/R13", "G2/R06", "G2/R13", "G3/R06", "G3/R13", "G5/R13", "G6/R13"}
SEED, SAMPLE = 20261127, 20
GUIDE = """# Blind answer-key review

For each row in `review.csv`: open the document named, go to the page(s), and decide yourself whether the **expected
answer** is right. You are checking our answer key, not any program output.

* `expected_answer`: complies / deviates / missing / unclear (bids: included / excluded / qualified / silent / alternate).
* `expected_route`: decide (the documents settle it) / ask_supplier (only the supplier can) / engineer (needs judgement).
* In `your_answer` and `your_route` write your own view, even if it is the same. Leave blank only if you cannot judge;
  say why in `comment`. Put your name in `reviewer`.
* "unclear" = the topic appears but the document does not settle it (an option not marked, a value without its basis).
  "missing" = the document says nothing about it.

Please do not open anything else in the project while reviewing. When done, send back `review.csv`.
"""


def main() -> None:
    out = Path(sys.argv[1])
    res = json.loads((ROOT / "eval/handoff_set/results.json").read_text(encoding="utf-8"))["results"]
    rows = [r for r in res if r["group"] != "prequal" and r["group"] != "link" and r["group"] != "decision"]
    reader = {}
    for name in ("targeted_qwen3.8-27b.json", "qwen3.8-27b.json"):
        f = ROOT / "eval/cross_checks" / name
        if f.exists():
            for cid, v in json.loads(f.read_text(encoding="utf-8")).items():
                reader.setdefault(cid, {}).update(v["answers"])
    chosen: dict[str, set] = {}
    for r in rows:
        why = set()
        a, b = r["v2"], r["v4"]
        if b["route"] == "decide" and (a["route"], a["answer"]) != (b["route"], b["answer"]):
            why.add("changed")
        if any(r[v]["outcome"] in ("incorrect decision", "missed escalation") for v in ("v1", "v2", "v3", "v4") if v in r):
            why.add("critical")
        second = ((reader.get(r.get("case", ""), {}).get(r.get("req_id")) or {}).get("verdict"))
        if r["id"] in JUDGEMENT_CALLS or (second and second != r["expected"] and b["answer"] != r["expected"]):
            why.add("disputed")
        if why:
            chosen[r["id"]] = why
    rest = [r["id"] for r in rows if r["id"] not in chosen]
    for i in random.Random(SEED).sample(rest, min(SAMPLE, len(rest))):
        chosen[i] = {"sample"}
    by_id = {r["id"]: r for r in rows}
    order = sorted(chosen)
    random.Random(SEED + 1).shuffle(order)

    pkg = json.loads((KEYS / "package_GEN.json").read_text(encoding="utf-8"))
    bids = json.loads((KEYS / "bids_genset.json").read_text(encoding="utf-8"))
    docs_needed, sheet, mapping = set(), [], {}
    claims = {}
    for f in ("genset_requirements.json", "ups_requirements.json"):
        for q in json.loads((KEYS / f).read_text(encoding="utf-8"))["requirements"]:
            claims[(f, q["req_id"])] = q
    for n, cid in enumerate(order, 1):
        r = by_id[cid]
        row = {"item": n, "document": "", "second_document": "", "requirement": "", "spec_ref": "", "expected_answer": r["expected"],
               "expected_route": r["expected_route"], "evidence_page": "", "evidence_quote": "", "key_note": "",
               "your_answer": "", "your_route": "", "comment": "", "reviewer": ""}
        if r["group"] == "bid scope":
            row["document"] = Path(bids["bids"][r["bid"]]).name
            row["second_document"] = Path(bids["bid_form"]).name
            row["requirement"] = f"Bid scope item {r['scope_id']} (see the bid form)"
            row["key_note"] = str((bids.get("why") or {}).get(r["scope_id"], ""))[:300] if isinstance(bids.get("why"), dict) else ""
            docs_needed |= {bids["bids"][r["bid"]], bids["bid_form"]}
        else:
            case_id = r.get("case") or pkg["bidders"][r["bid"]]["datasheet_case"]
            key = json.loads((KEYS / f"{case_id}.json").read_text(encoding="utf-8"))
            q = claims[(key.get("checklist", "genset_requirements.json"), r["req_id"])]
            row["requirement"] = q["requirement"]
            row["spec_ref"] = f"{Path(key['spec']).name} {q.get('spec_locator', '')} p{q.get('spec_page', '')}"
            row["document"] = Path(key["submittal"]).name
            docs_needed |= {key["submittal"], key["spec"]}
            if r["group"] == "package":
                p = next(x for x in pkg["requirements"] if x["bid"] == r["bid"] and x["req_id"] == r["req_id"])
                bid = pkg["bidders"][r["bid"]]["bid"]
                row.update(second_document=Path(bid).name, evidence_quote=p.get("bid_quote", ""), key_note=p.get("notes", ""))
                docs_needed.add(bid)
            else:
                lab = next(x for x in key["labels"] if x["req_id"] == r["req_id"])
                row.update(evidence_page=lab.get("submittal_page") or "", evidence_quote=lab.get("submittal_quote", ""),
                           key_note=lab.get("notes", ""))
        sheet.append(row)
        mapping[n] = {"id": cid, "selected_as": sorted(chosen[cid])}

    out.mkdir(parents=True, exist_ok=True)
    (out / "documents").mkdir(exist_ok=True)
    for d in sorted(docs_needed):
        if (ROOT / d).exists():
            shutil.copyfile(ROOT / d, out / "documents" / Path(d).name)
    with (out / "review.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(sheet[0]))
        w.writeheader()
        w.writerows(sheet)
    (out / "READ_ME_FIRST.md").write_text(GUIDE, encoding="utf-8")
    (ROOT / "eval/review").mkdir(parents=True, exist_ok=True)
    (ROOT / "eval/review/mapping.json").write_text(json.dumps({"seed": SEED, "items": mapping}, indent=1), encoding="utf-8")
    from collections import Counter
    c = Counter(w for m in mapping.values() for w in m["selected_as"])
    print(f"{len(sheet)} rows -> {out}  ({dict(c)}); {len(docs_needed)} documents")


if __name__ == "__main__":
    main()
