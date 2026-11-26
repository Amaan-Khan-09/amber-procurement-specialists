"""Answers of the earlier versions on a fresh datasheet set, produced by their own code.

Copies the keys, the saved readings and the second reader's file into a checkout of commit 1d14f3e, runs that code's
datasheet answers (it computes the 9cd1b4e routing and its own), and stores them for scripts/eval_handoffs.py.

usage: git worktree add ../amber-base-1d14f3e 1d14f3e ; python scripts/score_fresh_earlier.py ../amber-base-1d14f3e G12 G13
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "eval" / "handoff_set" / "frozen" / "fresh6_1d14f3e.json"
RUNNER = """
import json, sys
sys.path.insert(0, 'scripts')
import eval_handoffs as E
want = sys.argv[1].split(',')
ds = E.datasheet_answers()
rows = [{'id': i, **{v: ds[v][i] for v in ('v1', 'v2', 'v3')}} for i in ds['v3'] if i.split('/')[0] in want]
open(sys.argv[2], 'w', encoding='utf-8').write(json.dumps({'commit': '1d14f3e', 'results': rows}, indent=1))
print(len(rows), 'answers')
"""


def main() -> None:
    old = Path(sys.argv[1]).resolve()
    cases = sys.argv[2:]
    head = subprocess.run(["git", "-C", str(old), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    changed = subprocess.run(["git", "-C", str(old), "status", "--porcelain", "--", "amber"], capture_output=True, text=True).stdout.strip()
    assert head.startswith("1d14f3e") and not changed, f"the checkout must be clean 1d14f3e code (is {head}, changed: {changed})"
    for c in cases:
        for rel in (f"eval/answer_keys/{c}.json", f"examples/{c}.json"):
            shutil.copyfile(ROOT / rel, old / rel)
        sub = json.loads((ROOT / f"eval/answer_keys/{c}.json").read_text(encoding="utf-8"))["submittal"]
        shutil.copyfile(ROOT / sub, old / sub)
    shutil.copyfile(ROOT / "eval/cross_checks/qwen3.8-27b.json", old / "eval/cross_checks/qwen3.8-27b.json")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-c", RUNNER, ",".join(cases), str(OUT)], cwd=old, check=True)


if __name__ == "__main__":
    main()
