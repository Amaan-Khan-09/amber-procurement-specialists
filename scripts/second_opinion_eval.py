"""Second opinion on the pipeline's concrete answers, from a different model family, measured against the answer keys.

For every finding the pipeline answered "complies" or "deviates" with a verified submittal quote, ask a model of another
family one small question: given only the requirement and the quoted evidence, is the requirement met? (yes / no /
cannot_tell). The pipeline's reasoning is NOT shown. Then measure whether agreement predicts a right answer.

usage: python scripts/second_opinion_eval.py [--model qwen/qwen3.8-27b] [--cases G1,G2,...]
Results are stored in eval/cross_checks/second_opinion_<model>.json so a re-run costs nothing.
"""
import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import replay_decisions as rd  # noqa: E402
from amber.llm import LLM, LLMError  # noqa: E402

OUT = ROOT / "eval" / "cross_checks"
SYSTEM = """You check one supplier datasheet claim at a time for a procurement team.
For each item you get a specification requirement and the exact words quoted from the supplier's datasheet. Decide ONLY from
those quoted words (no outside knowledge of the product):
- "yes": the quoted words clearly show the requirement is met.
- "no": the quoted words clearly show it is NOT met (a different value, a lower rating, the wrong type).
- "cannot_tell": the quote is about something else, lacks the value or a unit, lists options without saying which is supplied, or
  you would have to know the product to say.
Check units (kW is not kVA; C is not F). Do not guess.
Reply with JSON only: {"answers": [{"id": "<item id>", "verdict": "yes|no|cannot_tell"}]} with one entry per item."""

BATCH = 8
PACE = 25


def items_for(cid: str) -> list[dict]:
    case, _, res = rd.replay(cid)
    labels = {l["req_id"]: l["expected"] for l in case["labels"]}
    out = []
    for f in res.findings:
        rid = f.data["req_id"]
        if f.status.value not in ("complies", "deviates") or rid not in labels:
            continue
        quotes = [c.quote for c in f.citations if not c.doc_id.startswith(("26-", "equipment-schedule"))]
        if not quotes:
            continue
        out.append({"id": f"{cid}:{rid}", "case": cid, "req": rid, "claim": f.claim, "evidence": quotes[:3],
                    "pipeline": f.status.value, "human": f.needs_human, "key": labels[rid]})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen/qwen3.8-27b")
    ap.add_argument("--cases", default=",".join(rd.cases()))
    a = ap.parse_args()
    store = OUT / f"second_opinion_{a.model.split('/')[-1]}.json"
    done = json.loads(store.read_text(encoding="utf-8")) if store.exists() else {}
    items = [i for cid in a.cases.split(",") for i in items_for(cid)]
    todo = [i for i in items if i["id"] not in done]
    llm = LLM(provider="groq", model=a.model)
    last = 0.0
    for s in range(0, len(todo), BATCH):
        batch = todo[s:s + BATCH]
        user = "\n\n".join(f"Item {i['id']}\nRequirement: {i['claim']}\nQuoted from the datasheet: " + " | ".join(f'"{q}"' for q in i["evidence"])
                           for i in batch)
        wait = PACE - (time.time() - last)
        if last and wait > 0:
            time.sleep(wait)
        last = time.time()
        for attempt in range(3):
            try:
                reply = llm.json(SYSTEM, user, max_tokens=1500, purpose="second opinion")
                break
            except LLMError as e:
                print("retry:", str(e)[:100])
                time.sleep(65)
        else:
            raise SystemExit("could not get a second opinion; stopping so no partial result is stored")
        got = {x.get("id"): x.get("verdict") for x in reply.get("answers", [])}
        for i in batch:
            done[i["id"]] = got.get(i["id"], "cannot_tell")
        store.write_text(json.dumps(done, indent=1), encoding="utf-8")
        print(f"  {min(s + BATCH, len(todo))}/{len(todo)} asked")

    def agrees(i):
        return (i["pipeline"] == "complies" and done[i["id"]] == "yes") or (i["pipeline"] == "deviates" and done[i["id"]] == "no")

    print(f"\n{len(items)} concrete answers with a verified submittal quote")
    groups = defaultdict(list)
    for i in items:
        groups[("handed to a person" if i["human"] else "automatic", "second model agrees" if agrees(i) else "does not agree")].append(i)
    print(f"{'group':50} {'n':>4}  pipeline right")
    for g in sorted(groups):
        gi = groups[g]
        print(f"{g[0] + ' | ' + g[1]:50} {len(gi):>4}  {sum(x['pipeline'] == x['key'] for x in gi)}/{len(gi)} ({sum(x['pipeline'] == x['key'] for x in gi) / len(gi):.0%})")
    for x in items:
        if agrees(x) and x["pipeline"] != x["key"]:
            print(f"   both say {x['pipeline']}, key says {x['key']}: {x['id']} ({'handed to a person' if x['human'] else 'AUTOMATIC'})")
    print("tokens:", [(m.name, m.tokens_in, m.tokens_out) for m in llm.meter.models()])


if __name__ == "__main__":
    main()
