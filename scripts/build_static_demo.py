"""Build the read-only live demo into docs/demo/ (for GitHub Pages: Settings > Pages > Deploy from a branch > main, /docs).

usage: python scripts/build_static_demo.py
Needs only the committed files (examples/, data/specs/project_alpha, data/bids). The manufacturers' datasheets are
never copied: the demo shows the short verified excerpt that each answer cites, with a link to the manufacturer's page.
Re-run it after changing amber/web_index.html or any result in examples/.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from amber import demo  # noqa: E402


def main() -> None:
    out = ROOT / "docs" / "demo"
    s = demo.build(out)
    (ROOT / "docs" / ".nojekyll").write_text("", encoding="utf-8")  # serve the files as they are
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"built {out}: {s['results']} saved results, {s['citations']} citations ({s['page_images']} page images of our own "
          f"documents, {s['third_party_excerpts']} manufacturer excerpts, no manufacturer pages), {size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
