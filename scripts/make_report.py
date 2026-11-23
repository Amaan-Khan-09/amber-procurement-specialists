"""Render a package-review result (runs/package_*.json) as one self-contained HTML page.

usage: python scripts/make_report.py runs/package_GEN.json [out.html]
No external assets: works offline, prints cleanly, follows the OS light/dark setting.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from amber.report import render  # noqa: E402


def main() -> None:
    src = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".html")
    out.write_text(render(json.loads(src.read_text(encoding="utf-8"))), encoding="utf-8")
    print("wrote", out, f"({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
