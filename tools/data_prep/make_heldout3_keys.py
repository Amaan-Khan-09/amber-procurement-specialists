"""Answer keys for HELD-OUT SET 3 (written 24 Nov 2026, after the accuracy fixes made from the set 1 and set 2 errors,
and before any agent run on these documents). Two public datasheets of products that bidders B1 and B4 actually offered,
against the Project Alpha generator spec, GEN-A.

  G7  Caterpillar 3516C, 60 Hz, 2000 ekW standby, EPA Tier 2 spec sheet (LEHE1376), the product B1 bid
  G8  Cummins C1750D6E / C2000D6E specification sheet (NAS-6746 with data sheet NAD-6745), the family of the product B4 bid

Every label was decided from the source text of the datasheet, per eval/answer_keys/README.md. The run on these two
documents is made once, with no tuning afterwards.
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
    "G7": ("data/submittals/cat_3516C_2000ekW_LEHE1376.pdf", {
        "R01": ("complies", 1, "2000 (2500) 2000 (2500) 1825 (2281) 1650 (2063)", "Standby 2000 ekW / 2500 kVA at 0.8 PF (also p3, 'Genset power rating with fan')."),
        "R02": ("unclear", 2, "Output voltage", "Voltage options 380 V to 13.8 kV are listed with check boxes, none marked as supplied; 60 Hz is stated (p3); phases and wires are not."),
        "R03": ("unclear", 1, "Superior motor starting capability minimizes", "Motor starting is mentioned only as a claim ('superior'); no kVA figure or voltage dip is given."),
        "R04": ("unclear", 2, "Permanent magnet (PM)", "Internal excitation and permanent magnet are both listed as options, neither marked as supplied."),
        "R05": ("unclear", 1, "Aspiration TA", "Turbocharged-aftercooled (TA) is stated; the number of cylinders and the four-cycle design are not."),
        "R06": ("unclear", 1, "Governor Type A6E4", "A governor type code is given; 'electronic' and 'isochronous' are not stated."),
        "R07": ("unclear", 2, "Standard electric starter(s)", "Electric starters are listed with heavy duty, dual and air options; the starting voltage is not stated."),
        "R08": ("complies", 3, "100% load with fan", "Standby column: 505.8 L/hr (133.6 gal/hr) at 100% load, below 145 gph."),
        "R09": ("unclear", 1, "Cooling systems available to operate in ambient temperatures up to 50", "Cooling systems are 'available' for 50 C (122 F); which one is supplied is not stated."),
        "R10": ("complies", 3, "EPA ESE (TIER 2)", "Also p1: meets U.S. EPA Stationary Emergency Use Only (Tier 2)."),
        "R11": ("unclear", 1, "Cooling systems available to operate in ambient temperatures up to 50", "Ambient capability up to 50 C is mentioned as available; altitude and any derate are not stated."),
        "R12": ("missing", None, "", "No engine speed or rpm figure anywhere (only 60 Hz)."),
        "R13": ("missing", None, "", "No pole count, pitch or brushless statement for the alternator."),
        "R14": ("missing", None, "", "Insulation class not stated (temperature-rise options only)."),
        "R15": ("unclear", 2, "Anti-condensation heater", "Listed as an alternator attachment option; voltage and phase not stated; not marked as supplied."),
        "R16": ("unclear", 2, "Circuit breaker", "Circuit breaker, 3-pole and 4-pole and LSI trip units are listed as options; none marked as supplied."),
        "R17": ("missing", None, "", "No voltage regulation figure."),
        "R18": ("missing", None, "", "No harmonic distortion figure."),
        "R19": ("missing", None, "", "No fuel tank mentioned (fuel consumption only)."),
        "R20": ("unclear", 2, "Jacket water heater", "Listed in the equipment table; quantity, wattage and voltage not stated; not marked as supplied."),
        "R21": ("missing", None, "", "No enclosure mentioned; an industrial grade muffler is listed as an engine option."),
    }),
    "G8": ("data/submittals/cummins_C2000D6E_spec_sheet.pdf", {
        "R01": ("complies", 5, "2000 kWe (2500 kVA) EMERGENCY STANDBY POWER (ESP)", "Standby rating 2000 kWe / 2500 kVA; power factor 0.8 on p7."),
        "R02": ("unclear", 2, "AVAILABLE VOLTAGES (60 Hz LINE-TO-NEUTRAL / LINE-TO-LINE)", "277/480 V is one of many voltages offered, none marked as supplied; 60 Hz and 3-phase 4-wire sensing are stated."),
        "R03": ("unclear", 1, "Several alternator sizes offer selectable motor starting", "Motor starting is described only as selectable by alternator size; no kVA or voltage dip is given."),
        "R04": ("complies", 2, "Exciter type  Permanent Magnet Generator (PMG)", ""),
        "R05": ("complies", 2, "Four Cycle; Vee; 16 Cylinder", "Aspiration 'Turbocharged and Charge Air Cooled' on p5."),
        "R06": ("complies", 3, "Integrated digital electronic isochronous governor", ""),
        "R07": ("complies", 2, "Starting voltage  24 volts, negative ground", ""),
        "R08": ("complies", 5, "Fuel Consumption  US gph  41.5  75  108  139.8", "139.8 gph at 100% of 2000 kWe standby, below 145."),
        "R09": ("unclear", 2, "Standard cooling system  High ambient cooling system", "Standard cooling is high ambient (40 C / 104 F); enhanced high ambient (50 C / 122 F) is an option; which is supplied is not stated."),
        "R10": ("complies", 1, "EPA TIER 2 NSPS CERTIFIED (STATIONARY EMERGENCY)", ""),
        "R11": ("deviates", 7, "derates at 3.3% per 305 m", "Even the enhanced 50 C cooling system derates 3.3% per 305 m from sea level, and the standard one derates 10% per 10 C above 40 C: full rating is not kept at 300 ft and 122 F."),
        "R12": ("complies", 5, "Rated speed  rpm  1800", ""),
        "R13": ("complies", 2, "Brushless, 4-pole, drip proof, revolving field", "Stator 2/3 pitch on the next line."),
        "R14": ("complies", 2, "Insulation system  Class H", ""),
        "R15": ("unclear", 2, "120/240V 225W anti- condensation heater", "Listed as an option; phase not stated; not marked as supplied."),
        "R16": ("unclear", 2, "Set mounted circuit breakers up to 3200 Amps", "Listed as an option; poles and trip type not stated; not marked as supplied."),
        "R17": ("complies", 2, "Voltage regulation, no load to full load  ± 0.5%", ""),
        "R18": ("complies", 2, "< 5% no load to full linear load", "Stated as less than 5%, which meets 'shall not exceed 5%'."),
        "R19": ("missing", None, "", "No fuel tank mentioned."),
        "R20": ("unclear", 2, "240V thermo-statically controlled coolant", "A 240 V coolant heater is listed as an option; quantity, wattage and phase not stated; not marked as supplied."),
        "R21": ("missing", None, "", "No enclosure offered on this sheet; silencers and louvres are listed as options."),
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
        case = {"case_id": cid, "split": "heldout", "heldout_set": 3, "tool": "check_submittal", "spec": SPEC, "tag": "GEN-A",
                "submittal": sub, "labeller": "Project author, with AI assistance, from the source PDF, per eval/answer_keys/README.md. "
                "Held-out set 3: labelled 24 Nov 2026, after the accuracy fixes made from the set 1 and set 2 errors, BEFORE any agent run "
                "on this document.", "labelled_on": "2026-11-24", "reviewed_by": "", "labels": rows}
        (ROOT / f"eval/answer_keys/{cid}.json").write_text(json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8")
        counts = {v: sum(1 for x in labels.values() if x[0] == v) for v in ("complies", "deviates", "missing", "unclear")}
        print(cid, counts, "| all quotes verified" if not bad else f"| {bad} to fix")


if __name__ == "__main__":
    main()
