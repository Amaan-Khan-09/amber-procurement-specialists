"""Write the Project Alpha UPS specification (Section 26 33 53) and merge the two public Vertiv documents into one
submittal package, the way a supplier would send them.

The spec is a short project spec written in the CSI format, adapted in structure and wording from the public-domain
US federal guide spec UFGS 26 33 53 (Static Uninterruptible Power Supply). It is FICTIONAL project text.

Outputs: data/specs/project_alpha/26_33_53_static_ups_ALPHA.pdf (+ .txt)
         data/submittals/vertiv_EXL_S1_package.pdf  (needs the two Vertiv PDFs from fetch_data.py)
"""
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/specs/project_alpha"

SPEC = [
    ("h1", "PART 1 - GENERAL"),
    ("h2", "1.1 SUMMARY"),
    ("p", "A. Section includes four (4) single-module static uninterruptible power supply (UPS) units, tags UPS-A to UPS-D, "
          "each feeding one data hall power block, as scheduled on Drawing E-601."),
    ("h2", "1.2 SUBMITTALS"),
    ("p", "A. Product Data: Manufacturer's catalog data for each UPS, including electrical ratings, efficiency, heat "
          "dissipation, dimensions and weights, and one-line diagram."),
    ("p", "B. Where product data covers more than one voltage or frequency, mark the configuration supplied for this project."),
    ("h1", "PART 2 - PRODUCTS"),
    ("h2", "2.1 UPS MODULE"),
    ("p", "A. Rating: Each UPS shall have a continuous output rating of not less than 1200 kVA and 1200 kW at unity power "
          "factor, at 480 volts."),
    ("p", "B. Ambient Rating: The full rating in paragraph A shall be available at an ambient temperature of 40 degrees C."),
    ("p", "C. System Voltage: Input, bypass and output shall be 480 volts, 3-phase, 3-wire plus ground, 60 Hz."),
    ("p", "D. Topology: Double-conversion (online) design, classified VFI under IEC 62040-3."),
    ("p", "E. Efficiency: Double-conversion AC-to-AC efficiency shall be not less than 96 percent at 100 percent load."),
    ("p", "F. Input Characteristics: Input power factor shall be not less than 0.99 and input current distortion (THDi) "
          "shall not exceed 5 percent at full load."),
    ("p", "G. Output Voltage Regulation: Steady-state output voltage shall be held within plus or minus 1 percent for "
          "balanced load changes from 0 to 100 percent."),
    ("p", "H. Overload: The inverter shall carry 125 percent of rated load for not less than 10 minutes."),
    ("p", "I. Static Bypass: Provide an automatic static bypass switch within the UPS."),
    ("p", "J. Maintenance Bypass: Provide a manual maintenance bypass, furnished with the UPS."),
    ("p", "K. Batteries: Valve-regulated lead-acid or lithium-ion, sized for not less than 10 minutes at full load."),
    ("p", "L. Paralleling: The UPS shall be capable of operating in parallel with at least 3 additional units of the same rating."),
    ("p", "M. Listing: The UPS shall be listed to UL 1778."),
    ("p", "N. Seismic: The UPS shall be certified for seismic installation in accordance with the International Building Code."),
    ("h2", "2.2 PHYSICAL REQUIREMENTS"),
    ("p", "A. Dimensions: Each UPS shall fit within 110 inches wide, 40 inches deep and 84 inches high."),
    ("p", "B. Heat Dissipation: Heat released at full load shall not exceed 150,000 BTU per hour."),
    ("h1", "PART 3 - EXECUTION"),
    ("h2", "3.1 INSTALLATION"),
    ("p", "A. Install the UPS in accordance with the manufacturer's written instructions."),
]


def text() -> str:
    return "\n".join(t for _, t in SPEC)


def render() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "26_33_53_static_ups_ALPHA.txt").write_text(text(), encoding="utf-8")
    doc = pymupdf.open()
    W, H, M = 612, 792, 54
    page = None
    y = 0
    n = 0
    header = "PROJECT ALPHA - PHASE 1 DATA HALL          SECTION 26 33 53  STATIC UNINTERRUPTIBLE POWER SUPPLY"

    def new_page():
        nonlocal page, y, n
        n += 1
        page = doc.new_page(width=W, height=H)
        page.insert_text((M, 36), header, fontsize=8, fontname="helv")
        page.insert_text((W / 2 - 40, H - 30), f"26 33 53 - {n}", fontsize=8, fontname="helv")
        y = 60

    new_page()
    for kind, t in SPEC:
        bold = kind in ("h1", "h2")
        indent = 0 if bold else 18
        size, font = (10.5 if kind == "h1" else 10, "hebo") if bold else (9.5, "helv")
        scratch = pymupdf.open().new_page(width=W, height=H)
        spare = scratch.insert_textbox(pymupdf.Rect(M + indent, 0, W - M, H), t, fontsize=size, fontname=font)
        assert spare >= 0
        h = H - spare + 4
        if y + h > H - 50:
            new_page()
        rc = page.insert_textbox(pymupdf.Rect(M + indent, y, W - M, y + h), t, fontsize=size, fontname=font)
        assert rc >= 0
        y += h + (6 if bold else 2)
    doc.save(OUT / "26_33_53_static_ups_ALPHA.pdf")
    pdf_text = " ".join(" ".join(p.get_text().split()) for p in pymupdf.open(OUT / "26_33_53_static_ups_ALPHA.pdf"))
    missing = [t[:50] for _, t in SPEC if " ".join(t.split())[:45] not in pdf_text]
    assert not missing, missing
    print(f"wrote spec: {n} pages, {len(SPEC)} paragraphs, all present")


def merge() -> None:
    a = ROOT / "data/submittals/vertiv_EXL_S1_300-1200kW.pdf"
    b = ROOT / "data/submittals/vertiv_EXL_S1_site_planning_1000-1200kVA_SL-26092.pdf"
    if not (a.exists() and b.exists()):
        print("skip package: run tools/data_prep/fetch_data.py first")
        return
    out = pymupdf.open()
    out.insert_pdf(pymupdf.open(a))
    out.insert_pdf(pymupdf.open(b))
    dst = ROOT / "data/submittals/vertiv_EXL_S1_package.pdf"
    out.save(dst)
    print(f"wrote package: {out.page_count} pages (brochure p1-14, site planning p15-17)")


if __name__ == "__main__":
    render()
    merge()
