"""Write the UPS requirement checklist and the answer key U1 (Vertiv EXL S1 package vs Project Alpha UPS spec).

Labels were written from the two source documents only, before any agent run on this case. HELD-OUT: the pipeline
was tuned on generator cases; UPS is a new equipment class it has never seen.
Package pages: brochure p1-14 (India edition, 400 V / 50 Hz), US site planning sheet p15-17 (480 V).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from amber import docs  # noqa: E402
from amber.verify import verify  # noqa: E402

SPEC = "data/specs/project_alpha/26_33_53_static_ups_ALPHA.pdf"
PKG = "data/submittals/vertiv_EXL_S1_package.pdf"

# (id, locator, spec anchor, requirement, expected, page, quote, note)
ROWS = [
    ("U01", "2.1.A", "A. Rating", "Output rating >= 1200 kVA and 1200 kW at 480 V",
     "complies", 15, "1200  1200  480  1499  1574  1600", "US site planning sheet lists the 1200 kVA / 1200 kW module at 480 VAC."),
    ("U02", "2.1.B", "B. Ambient Rating", "Full rating available at 40 C ambient",
     "deviates", 12, "Output active power at 40 °C (kW)  270  360  450  540  720  900  1080",
     "1200 kW is only available at 35 C; at 40 C the 1200 kVA unit gives 1080 kW (90%)."),
    ("U03", "2.1.C", "C. System Voltage", "Input, bypass and output 480 V, 3-phase, 3-wire plus ground, 60 Hz",
     "unclear", 12, "Nominal output voltage (V)  400 (380/415 selectable)",
     "The package contradicts itself: the brochure (India edition) offers 400 V (380/415), 50 Hz with 60 Hz selectable and never 480 V; the US site planning sheet p15 says 480 VAC 3-wire plus ground. No configuration is marked as supplied."),
    ("U04", "2.1.D", "D. Topology", "Double-conversion (online) topology, VFI",
     "complies", 4, "Double Conversion Mode (VFI)", "Also 'VFI-SS-111' on p12."),
    ("U05", "2.1.E", "E. Efficiency", "Double-conversion efficiency >= 96% at 100% load",
     "complies", 15, "≥96.3%  ≥96.3%  148502  6700", "US sheet: at least 96.3% at 100% rated load; brochure says up to 97%."),
    ("U06", "2.1.F", "F. Input Characteristics", "Input power factor >= 0.99 and THDi <= 5%",
     "complies", 12, "Input Power Factor ≥ 0.99", "Input current distortion THDi <= 3% in the same table."),
    ("U07", "2.1.G", "G. Output Voltage Regulation", "Output voltage regulation within +/-1% for 0-100% load changes",
     "complies", 12, "Output voltage stability by load variation 0-100% (%)", "Static +/-1 in the same row."),
    ("U08", "2.1.H", "H. Overload", "Inverter carries 125% load for at least 10 minutes",
     "complies", 12, "110% continuous, 125% for 10mins, 150% for 1min", ""),
    ("U09", "2.1.I", "I. Static Bypass", "Automatic static bypass switch within the UPS",
     "complies", 6, "unit has a dedicated static bypass switch",
     "Stated for the distributed-parallel configuration; the one-line diagram p17 also shows a bypass AC input."),
    ("U10", "2.1.J", "J. Maintenance Bypass", "Manual maintenance bypass furnished with the UPS",
     "deviates", 12, "Manual Maintenance Bypass Included 300-500 kW Not included 600-1200 kW",
     "Not included for 600-1200 kW; p17 shows the maintenance bypass panelboard 'Furnished by Others'."),
    ("U11", "2.1.K", "K. Batteries", "VRLA or lithium-ion batteries sized for at least 10 minutes at full load",
     "unclear", 2, "standard VRLA and new Li-ion batteries", "Chemistries are stated; runtime and battery sizing are not."),
    ("U12", "2.1.L", "L. Paralleling", "Parallel operation with at least 3 additional units",
     "complies", 12, "Parallel configuration up to 8 units in parallel", ""),
    ("U13", "2.1.M", "M. Listing", "Listed to UL 1778",
     "missing", None, "", "Only IEC/EN 62040-3 is mentioned; UL 1778 appears nowhere."),
    ("U14", "2.1.N", "N. Seismic", "Seismic certification per the International Building Code",
     "unclear", 3, "Seismic compliance", "A feature bullet only; no code, certificate or rating is given."),
    ("U15", "2.2.A", "A. Dimensions", "Fits within 110 in W x 40 in D x 84 in H",
     "unclear", 16, "104.5 x 36.0 x 79.1",
     "The base 1200 kVA unit is 104.5 x 36.0 x 79.1 in, but installed options (back-feed disconnect, inductors) widen it up to 128.1 in and no options are marked as selected."),
    ("U16", "2.2.B", "B. Heat Dissipation", "Heat at full load not above 150,000 BTU/h",
     "complies", 15, "148502  6700", "148,502 BTU/h, just under the limit."),
]


class NoOCR:
    cache_tag = "none"

    def __call__(self, png):
        raise RuntimeError("no OCR")


def main() -> None:
    spec_doc = docs.load(str(ROOT / SPEC))
    pkg = docs.load(str(ROOT / PKG))
    reqs, labels, bad = [], [], 0
    for rid, loc, anchor, text, exp, page, quote, note in ROWS:
        hit = next((p.number for p in spec_doc.pages if anchor.lower() in " ".join(p.text.split()).lower()), None)
        assert hit, f"{rid}: anchor not in spec"
        reqs.append({"req_id": rid, "spec_locator": loc, "spec_page": hit, "spec_anchor": anchor, "requirement": text})
        if quote:
            v = verify(pkg, quote, page)
            if not v or v.page != page:
                bad += 1
                print("CHECK", rid, page, "->", v.page if v else None, "|", quote)
        labels.append({"req_id": rid, "expected": exp, "submittal_page": page, "submittal_quote": quote, "notes": note})
    kd = ROOT / "eval/answer_keys"
    (kd / "ups_requirements.json").write_text(json.dumps({"spec": SPEC, "requirements": reqs}, indent=2, ensure_ascii=False), encoding="utf-8")
    case = {"case_id": "U1", "split": "heldout", "tool": "check_submittal", "spec": SPEC, "tag": "UPS-A", "submittal": PKG,
            "checklist": "ups_requirements.json",
            "labeller": "Project author, with AI assistance, from the source PDFs, per eval/answer_keys/README.md. "
                        "Labelled BEFORE any agent run on this case; HELD-OUT: a new equipment class the pipeline was not tuned on.",
            "labelled_on": "2026-11-22", "reviewed_by": "",
            "case_notes": ["The package merges two public Vertiv documents: the EXL S1 brochure (India edition, 2019: 400 V / 50 Hz, 14 pages) "
                           "and the US site planning sheet SL-26092 (480 V, 3 pages). Pages 1-14 are the brochure, 15-17 the site planning sheet."],
            "labels": labels}
    (kd / "U1.json").write_text(json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8")
    print("U1 labelled:", {v: sum(1 for r in ROWS if r[4] == v) for v in ("complies", "deviates", "missing", "unclear")},
          "| all quotes verified" if not bad else f"| {bad} to fix")


if __name__ == "__main__":
    main()
