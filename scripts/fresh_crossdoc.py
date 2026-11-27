"""The fresh cross-document cases (eval/answer_keys/crossdoc_set6.json): datasheet only against datasheet + bid,
with identical routing, for this code and for commit 1d14f3e's code on the same saved readings.

usage: python scripts/fresh_crossdoc.py <checkout of 1d14f3e>   -> eval/handoff_set/fresh_crossdoc.json
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = """
import json, sys
sys.path.insert(0, 'scripts')
import eval_handoffs as E
from amber import case as C, docs
x = json.loads((E.KEYS / 'crossdoc_set6.json').read_text(encoding='utf-8'))
key = json.loads((E.KEYS / (x['datasheet_case'] + '.json')).read_text(encoding='utf-8'))
reqs, ds = E._reqs(key), docs.load(E.ROOT / key['submittal'])
offers = C.offers_from_run(json.loads((E.ROOT / 'examples' / (key['case_id'] + '.json')).read_text(encoding='utf-8')))
run = json.loads((E.ROOT / 'examples/commitments/XD6_bid.json').read_text(encoding='utf-8'))
bid = docs.load(E.ROOT / run['source_document']); bid.commitment = True
out = {}
for name, b in (('datasheet only', False), ('datasheet + bid', True)):
    res = C.reconcile_supplier(reqs, ds, offers, [bid] if b else [], [C.offers_from_run(run)] if b else [],
                               C.second_readings().get(key['case_id']), C.second_answers().get(key['case_id']))
    f = {i['data']['req_id']: i for i in res['findings']}
    out[name] = {r['req_id']: {'answer': f[r['req_id']]['status'], 'route': f[r['req_id']]['route']['route'],
                               'kind': f[r['req_id']]['route']['kind'], 'why': f[r['req_id']]['why'][:300]} for r in x['requirements']}
print('@@' + json.dumps(out))
"""


def answers(tree: Path) -> dict:
    p = subprocess.run([sys.executable, "-c", RUNNER], cwd=tree, capture_output=True, text=True, encoding="utf-8")
    line = next((l for l in p.stdout.splitlines() if l.startswith("@@")), None)
    if not line:
        raise RuntimeError(p.stderr[-1500:])
    return json.loads(line[2:])


def main() -> None:
    old = Path(sys.argv[1]).resolve()
    x = json.loads((ROOT / "eval/answer_keys/crossdoc_set6.json").read_text(encoding="utf-8"))
    for rel in ("eval/answer_keys/crossdoc_set6.json", "examples/commitments/XD6_bid.json", x["bid"]):
        (old / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, old / rel)
    versions = {"v3": answers(old), "v4": answers(ROOT)}
    sys.path.insert(0, str(ROOT / "scripts"))
    import eval_handoffs as E
    rows = []
    for r in x["requirements"]:
        for v, a in versions.items():
            for variant, found in a.items():
                got = found[r["req_id"]]
                rows.append({"req_id": r["req_id"], "kind_of_case": r["kind"], "expected": r["expected"],
                             "expected_route": r["expected_route"], "version": v, "variant": variant, **got,
                             "outcome": E.outcome3(r, got)[0]})
    (ROOT / "eval/handoff_set/fresh_crossdoc.json").write_text(json.dumps({"rows": rows}, indent=1), encoding="utf-8")
    for r in rows:
        print(f"{r['req_id']} {r['kind_of_case']:9} {r['version']} {r['variant']:16} {r['answer']:9} {r['route']:12} {r['outcome']}")


if __name__ == "__main__":
    main()
