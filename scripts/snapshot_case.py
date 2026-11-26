"""Freeze the generator case file into examples/case_GEN/ so the case page and the live demo can show it.

  1_questions_sent/   the case run from nothing: every step done, questions drafted, replies step waiting
  2_after_replies/    the same case resumed after two suppliers replied (saved readings, no model call)
  resume/             a run stopped on purpose inside 'reconcile', then resumed: its state and journal
No model calls: every reading comes from examples/. Then: python scripts/build_static_demo.py

usage: python scripts/snapshot_case.py
"""
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from amber import case as C  # noqa: E402

OUT = ROOT / "examples" / "case_GEN"


def _copy(src: Path, dst: Path) -> None:
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        C.run_case("GEN", root=root, fresh=True)
        _copy(root / "GEN", OUT / "1_questions_sent")
        C.run_case("GEN", root=root, replies=True)
        _copy(root / "GEN", OUT / "2_after_replies")
        r2 = root / "resume"
        try:
            C.run_case("GEN", root=r2, fresh=True, crash_at="reconcile")
        except C.Interrupted:
            pass
        C.run_case("GEN", root=r2)
        _copy(r2 / "GEN", OUT / "resume")
    for d in OUT.iterdir():
        st = (d / "state.json").read_text(encoding="utf-8")
        print(d.name, len(st), "bytes of state,", len(list((d / "steps").glob("*.json"))), "step outputs")


if __name__ == "__main__":
    main()
