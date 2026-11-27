"""Rebuild the fictional, freely distributable PDFs used in the first-upload walkthrough."""
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1] / "examples" / "judge_own_data"


def pdf(name: str, pages: list[str]) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    for words in pages:
        page = doc.new_page(width=612, height=792)
        page.insert_textbox(fitz.Rect(54, 55, 558, 740), words, fontsize=11, fontname="helv",
                            lineheight=1.4)
    doc.set_metadata({"title": name, "author": "Amber Procure sample data", "creationDate": ""})
    doc.save(ROOT / name, garbage=4, deflate=True, no_new_id=True)


def main() -> None:
    pdf("transformer_spec.pdf", ["FICTIONAL TRAINING PROJECT - COMPLETE TRANSFORMER PRODUCT SPECIFICATION\n"
        "All requirements below apply to the single transformer being reviewed.\n\n"
        "PART 2 - PRODUCTS\n"
        "2.1 Continuous rating shall be at least 500 kVA at 40 C ambient.\n"
        "2.2 Primary voltage shall be 13.8 kV.\n"
        "2.3 Secondary voltage shall be 480Y/277 V.\n"
        "2.4 Insulation system shall be rated at least 220 C.\n"
        "2.5 Outdoor enclosure shall be NEMA 3R.\n"
        "2.6 Acceptable manufacturer: Sample Electrics or equal. Engineer shall approve any equal."])
    pdf("transformer_offer.pdf", ["FICTIONAL SUPPLIER DATA - TR600 TRANSFORMER FAMILY\n"
        "These are published family ratings; this is not a project shop drawing.\n\n"
        "TR600 technical data\n"
        "Continuous rating: 600 kVA at 30 C ambient.\n"
        "Primary voltage: 13.8 kV.\n"
        "Secondary voltage: 480Y/277 V.\n"
        "Insulation system: 180 C.\n"
        "Manufacturer: Example Power.\n\n"
        "Enclosure choices: NEMA 1 indoor; NEMA 3R outdoor. Selection for this order is not marked."])
    pdf("ups_spec.pdf", ["FICTIONAL TRAINING PROJECT - COMPLETE UPS PRODUCT SPECIFICATION\n"
        "PART 2 - PRODUCTS\n"
        "2.1 UPS output rating shall be at least 100 kW.\n"
        "2.2 Efficiency shall be at least 95% at 100% load in normal double conversion mode.\n"
        "2.3 Overload capacity shall be at least 125% for 10 minutes.\n"
        "2.4 Battery runtime shall be at least 15 minutes at full load.\n"
        "2.5 Input voltage shall be 480 V, three phase."])
    pdf("ups_offer.pdf", ["FICTIONAL SUPPLIER DATA - UPS120\n"
        "Output rating: 120 kW.\n"
        "Efficiency: 95.5% at 100% load in normal double conversion mode.\n"
        "Overload: <125% for <=10 minutes.\n"
        "Input: 480 V three phase.\n"
        "Battery runtime requires a project battery selection; no runtime is stated here."])


if __name__ == "__main__":
    main()
