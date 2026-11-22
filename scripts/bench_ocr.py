"""Benchmark an OCR engine on pages with a known answer, with digits as the thing that matters.

1. Text pages: the page also has a real text layer, which is the ground truth. The page is rendered to an image,
   OCR'd, and the numbers are compared: recall (true numbers found) and INVENTED numbers (in the OCR text but nowhere
   on the page). Invented numbers are the dangerous failure.
2. Scanned drawings, checked by eye: the strings that must be read exactly (a model number misread here before).

usage: python scripts/bench_ocr.py --provider ollama [--model qwen3-vl:4b]
       python scripts/bench_ocr.py --provider gemini --cached-only   (drawings only, from the existing cache: free)
"""
import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SUB = ROOT / "data/submittals"

TEXT_PAGES = [("kohler_KD2000_G5-626.pdf", 1), ("kohler_KD2000_G5-626.pdf", 2), ("kohler_KD2000_G5-626.pdf", 3),
              ("cummins_s-6786.pdf", 2), ("vertiv_EXL_S1_site_planning_1000-1200kVA_SL-26092.pdf", 1)]
DRAWINGS = [("kohler_KD1000_submittal_WPC6593.pdf", 60, ["KD1000", "ADV-8868", "KD27V12"]),
            ("cummins_DQKAB_submittal_CSDG.pdf", 62, ["3744-4992W", "1400W", "208-240-480V", "120-240V"])]


def numbers(text: str) -> set[str]:
    out = set()
    for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", text):
        n = m.group(0).replace(",", "")
        if len(n.replace(".", "")) >= 2:  # single digits are too common to tell us anything
            out.add(n.rstrip("."))
    return out


def squash(s: str) -> str:
    s = s.translate(str.maketrans({"–": "-", "—": "-", "‑": "-", "−": "-"}))
    return re.sub(r"\s+", "", s).upper()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="ollama")
    ap.add_argument("--model")
    ap.add_argument("--cached-only", action="store_true", help="only score drawings already in the OCR cache")
    a = ap.parse_args()
    from amber import ocr as ocrmod
    if a.model:
        ocrmod.VISION[a.provider] = a.model
    eng = None if a.cached_only else ocrmod.VisionOCR(provider=a.provider)
    tag = (a.model or ocrmod.VISION[a.provider]).replace("/", "_")

    if eng:
        print(f"== {tag}: text pages (truth = the PDF's own text layer)")
        tot_true = tot_found = tot_inv = tot_out = 0
        for f, n in TEXT_PAGES:
            page = pymupdf.open(SUB / f)[n - 1]
            truth = numbers(page.get_text())
            t0 = time.time()
            got = numbers(eng(page.get_pixmap(dpi=200).tobytes("png")))
            secs = time.time() - t0
            found, invented = truth & got, got - truth
            tot_true, tot_found, tot_inv, tot_out = tot_true + len(truth), tot_found + len(found), tot_inv + len(invented), tot_out + len(got)
            print(f"  {f[:28]:28} p{n}: {secs:5.0f}s  numbers found {len(found)}/{len(truth)}  invented {len(invented)}"
                  + (f"  e.g. {sorted(invented)[:6]}" if invented else ""))
        print(f"  TOTAL recall {tot_found}/{tot_true} = {tot_found / max(1, tot_true):.0%}   invented {tot_inv} of {tot_out} numbers read")

    print(f"== {tag}: scanned drawings (truth checked by eye)")
    for f, n, must in DRAWINGS:
        if a.cached_only:
            sha = hashlib.sha256((SUB / f).read_bytes()).hexdigest()[:16]
            cf = ROOT / ".cache/ocr" / f"{sha}-p{n}-{tag}.json"
            if not cf.exists():
                print(f"  {f[:28]} p{n}: not in cache")
                continue
            text, secs = json.loads(cf.read_text(encoding="utf-8"))["text"], 0.0
        else:
            t0 = time.time()
            text = eng(pymupdf.open(SUB / f)[n - 1].get_pixmap(dpi=200).tobytes("png"))
            secs = time.time() - t0
        hits = {m: squash(m) in squash(text) for m in must}
        print(f"  {f[:28]:28} p{n}: {secs:5.0f}s  " + "  ".join(f"{m}:{'ok' if h else 'MISSED'}" for m, h in hits.items()))


if __name__ == "__main__":
    main()
