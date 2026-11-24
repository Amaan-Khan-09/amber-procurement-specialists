"""Score every saved run against its answer key and store the result in examples/proof.json (committed).

usage: python scripts/build_proof.py
Re-checking each quote on its page takes a few minutes, so the web page's Proof tab reads this file instead of
recomputing. Run it again whenever a run in examples/ or an answer key changes; the web page also recomputes by
itself (into runs/web/proof.json) when the stored score no longer matches the files.
Needs the public datasheets (python tools/data_prep/fetch_data.py), otherwise quotes cannot be re-checked.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from amber import web  # noqa: E402


def main() -> None:
    d = web.proof_payload(refresh=True)
    if d["proof"]["fabrications"] is None:
        sys.exit("The datasheets are missing, so quotes could not be re-checked: run tools/data_prep/fetch_data.py first.")
    (ROOT / "examples" / "proof.json").write_text(json.dumps(d, indent=1), encoding="utf-8")
    P = d["proof"]
    for k, v in P["sets"].items():
        print(f"held-out set {k}: {v['correct']}/{v['n']} correct, automatic {v['auto_correct']}/{v['auto_total']}, "
              f"false approvals {v['false_approvals']}")
    print("invented citations:", P["fabrications"], "| bids:", P["bids"])


if __name__ == "__main__":
    main()
