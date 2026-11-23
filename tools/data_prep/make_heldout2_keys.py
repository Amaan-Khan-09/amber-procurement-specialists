"""Answer keys for HELD-OUT SET 2 (written 23 Nov 2026, after the fixes that followed held-out set 1, and before any
agent run on these documents). Two new public generator datasheets against the Project Alpha generator spec, GEN-A.

  G5  mtu 16V4000 DS2250 (official Rolls-Royce/mtu PG spec sheet, 60 Hz, 50 C)
  G6  Kohler 2000ROZD-4 spec sheet G5-198
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from amber import docs  # noqa: E402
from amber.verify import verify  # noqa: E402

SPEC = "data/specs/project_alpha/26_32_13_engine_generators_ALPHA.pdf"
CASES = {
    "G5": ("data/submittals/mtu_16V4000_DS2250_60Hz_50C.pdf", {
        "R01": ("complies", 1, "2,250 kWe/60 Hz/Standby", "2250 kW / 2812 kVA standby at 0.8 PF at every voltage: exceeds 2000/2500."),
        "R02": ("unclear", 1, "Voltage (L-L)  380V † ‡  416V † ‡  440V † ‡  480V", "480 V offered among 380 V-13.8 kV options; none marked as supplied."),
        "R03": ("complies", 1, "skVA@30% voltage dip  4,855  4,665  4,895  5,760", "Every option is at least 4,017 skVA at 30% dip (480 V: 5,760) >= 3000."),
        "R04": ("complies", 2, "Permanent Magnet Generator (PMG) supply to regulator", ""),
        "R05": ("complies", 3, "Arrangement  16-V", "16-V, 4-cycle (p2-3); after-cooled (after cooler pump)."),
        "R06": ("complies", 3, "electronic isochronous (ADEC)", ""),
        "R07": ("complies", 2, "Electric starting motor - 24V", ""),
        "R08": ("deviates", 3, "At 100% of power rating: L/hr (gal/hr)  614 (162)", "162 gph at full standby > 145 gph."),
        "R09": ("complies", 3, "Ambient capacity of radiator: °C (°F)  50 (122)", "Unit-mounted radiator rated 50 C (122 F); no enclosure footnote on this sheet."),
        "R10": ("unclear", 4, "Refer to Emission Data Sheet (EDS) for emissions data", "EPA tier not stated; emissions deferred to a separate data sheet."),
        "R11": ("unclear", 4, "Consult your local mtu Distributor for altitude derations", "Nominal at 25 C and 300 m; altitude and temperature derates deferred to the distributor."),
        "R12": ("complies", 3, "Rated rpm  1,800", ""),
        "R13": ("complies", 2, "Brushless, rotating field generator", "Also '2/3 pitch windings' and '4 pole, rotating field' on p2."),
        "R14": ("missing", None, "", "Insulation class not stated (only 130 C temperature rise)."),
        "R15": ("missing", None, "", "No space heater mentioned."),
        "R16": ("missing", None, "", "No output circuit breaker mentioned."),
        "R17": ("complies", 2, "± 0.25% voltage regulation no load to full load", ""),
        "R18": ("complies", 2, "5% maximum total harmonic distortion", "5% maximum meets 'shall not exceed 5%'."),
        "R19": ("missing", None, "", "No fuel tank mentioned."),
        "R20": ("missing", None, "", "No jacket-water heater mentioned."),
        "R21": ("missing", None, "", "Open power unit only (sound data Level 0 OPU); no enclosure mentioned."),
    }),
    "G6": ("data/submittals/kohler_2000ROZD4_spec_sheet.pdf", {
        "R01": ("complies", 1, "277/480  3  60  2000/2500  3007", "Both 480 V alternator rows rate 2000/2500 kW/kVA standby at 0.8 PF."),
        "R02": ("unclear", 1, "277/480  3  60  2000/2500  3007", "277/480 offered among 380-4160 V options; none marked as supplied."),
        "R03": ("complies", 2, "7000 (60 Hz), 6600 (50 Hz)", "Peak motor starting at 35% dip: 7000 / 12500 kVA for the 480 V alternators; >2x margin over 3000 kVA at 30% dip."),
        "R04": ("complies", 1, "The pilot-excited, permanent-magnet generator (PMG) provides", ""),
        "R05": ("complies", 2, "Turbocharged, Intercooled", "4-Cycle; cylinder arrangement 16V."),
        "R06": ("complies", 1, "An electronic, isochronous governor delivers precise frequency", ""),
        "R07": ("complies", 2, "Starter motor rated voltage (DC)  Dual, 24", ""),
        "R08": ("complies", 3, "100%  508.8(134.5)  442.9(117.0)", "60 Hz column: 134.5 gph at 100% standby <= 145."),
        "R09": ("deviates", 3, "Ambient temperature, C ( F)  40 (105)  50 (122)", "Columns are 60 Hz | 50 Hz: the 60 Hz standard radiator is 40 C (105 F); 50 C (122 F) is the 50 Hz column."),
        "R10": ("unclear", 1, "engine is certified by the Environmental", "EPA certified, but tier and stationary-emergency category not stated."),
        "R11": ("deviates", 1, "TEMPERATURE: Derate 0.4% per 5.5 C (10 F) temperature above 25 C (77 F)", "Derates above 25 C, so full rating is not kept at 122 F; altitude is fine (derate only above 3300 ft)."),
        "R12": ("complies", 2, "Rated rpm  1800", ""),
        "R13": ("complies", 2, "Type  4-Pole, Rotating Field", "Brushless pilot exciter and two-thirds pitch windings on p2."),
        "R14": ("complies", 2, "Class H, Synthetic,", ""),
        "R15": ("unclear", 4, "Generator Strip Heater", "Listed accessory; voltage and phase not stated; not marked as supplied."),
        "R16": ("unclear", 4, "Line Circuit Breaker (NEMA type 1 enclosure)", "Listed accessory; poles and trip type not stated; not marked as supplied."),
        "R17": ("complies", 2, "Voltage regulation, no-load to full-load", "+/-0.25% (the symbol prints as a box in the PDF text)."),
        "R18": ("missing", None, "", "No THD figure (only 'superior voltage waveform')."),
        "R19": ("unclear", 4, "Day Tanks", "Only day tanks listed as an accessory: no sub-base tank, listing or runtime stated."),
        "R20": ("unclear", 4, "Block Heater", "Block heater listed as an accessory; quantity, wattage and voltage not stated."),
        "R21": ("missing", None, "", "Open unit with silencer kits only; no enclosure offered on this sheet."),
    }),
}


def main() -> None:
    checklist = json.loads((ROOT / "eval/answer_keys/genset_requirements.json").read_text(encoding="utf-8"))["requirements"]
    assert [r["req_id"] for r in checklist] == [f"R{i:02d}" for i in range(1, 22)]
    for cid, (sub, labels) in CASES.items():
        doc = docs.load(str(ROOT / sub))
        bad = 0
        rows = []
        for r in checklist:
            exp, page, quote, note = labels[r["req_id"]]
            if quote:
                v = verify(doc, quote, page)
                if not v or v.page != page:
                    bad += 1
                    print("CHECK", cid, r["req_id"], page, "->", v.page if v else None, "|", quote)
            rows.append({"req_id": r["req_id"], "expected": exp, "submittal_page": page, "submittal_quote": quote, "notes": note})
        case = {"case_id": cid, "split": "heldout", "heldout_set": 2, "tool": "check_submittal", "spec": SPEC, "tag": "GEN-A",
                "submittal": sub, "labeller": "Project author, with AI assistance, from the source PDF, per eval/answer_keys/README.md. "
                "Held-out set 2: labelled 23 Nov 2026, after the fixes that followed set 1, BEFORE any agent run on this document.",
                "labelled_on": "2026-11-23", "reviewed_by": "", "labels": rows}
        (ROOT / f"eval/answer_keys/{cid}.json").write_text(json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8")
        counts = {v: sum(1 for x in labels.values() if x[0] == v) for v in ("complies", "deviates", "missing", "unclear")}
        print(cid, counts, "| all quotes verified" if not bad else f"| {bad} to fix")


if __name__ == "__main__":
    main()
