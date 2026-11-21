"""Write the spec-side requirement list for the generator spec and blank answer-key case files.

Only the SPEC side is filled in here (what the spec asks, where it says it). The SUBMITTAL side,
meaning the expected verdict, page and quote, is left blank for a person to label.
"""
import json
import re
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "data/specs/project_alpha/26_32_13_engine_generators_ALPHA.pdf"
OUT = ROOT / "eval/answer_keys"

# (id, locator, anchor text that starts the paragraph in the spec, requirement in plain words)
REQS = [
    ("R01", "2.1.C", "C. System Capacity", "Standby rating per schedule at 0.8 PF: GEN-A..D 2000 kW / 2500 kVA; GEN-M 1000 kW / 1250 kVA"),
    ("R02", "2.1.C", "C. System Capacity", "Output 480Y/277 V, 3-phase, 4-wire, 60 Hz"),
    ("R03", "2.1.C.1", "1. The engine generator set short circuit", "Motor starting at max 30% voltage dip: >= 3000 kVA (2000 kW sets), >= 1500 kVA (1000 kW sets)"),
    ("R04", "2.1.C.2", "2. A permanent magnet generator", "Permanent magnet generator (PMG) excitation"),
    ("R05", "2.1.D", "D. Diesel Engine", "Diesel engine: 8, 12 or 16 cylinder, 4-cycle, turbocharged/aftercooled or naturally aspirated"),
    ("R06", "2.1.D.3 (Governor)", "3. Governor", "Electronic governor, isochronous no load to full load"),
    ("R07", "2.1.D.5 (Starting System)", "5. Starting System", "24 V DC electric starting"),
    ("R08", "2.1.D.1 (Diesel Fuel System)", "1. Diesel Fuel System", "Fuel consumption at full standby load: <= 145 gph (2000 kW) / <= 75 gph (1000 kW)"),
    ("R09", "2.1.D.2 (Cooling System)", "2. Cooling System", "Unit-mounted radiator rated for 122 °F (50 °C) maximum ambient"),
    ("R10", "2.1.D.3 (Emissions Compliance)", "3. Emissions Compliance", "EPA Tier 2 certified, stationary emergency"),
    ("R11", "2.1.E.1", "1. Ambient conditions", "Full rating at 300 ft altitude and 10–122 °F ambient (no derate)"),
    ("R12", "2.1.E.3", "3. The rpm of the engine", "Engine speed <= 1800 rpm"),
    ("R13", "2.1.G", "G. Generator:", "Alternator 4-pole, brushless, 2/3 pitch"),
    ("R14", "2.1.G.1", "1. NEMA Class F", "Insulation NEMA Class F or better"),
    ("R15", "2.1.G.5", "5. A 120 volt, single phase space heater", "Alternator space heater, 120 V 1-phase"),
    ("R16", "2.1.H", "H. Generator Output Circuit Breaker", "3-pole output circuit breaker(s) with solid-state trip"),
    ("R17", "2.1.I.2", "2. Voltage Regulation", "Voltage regulation within ±2% no load to rated load"),
    ("R18", "2.1.I.4", "4. Total Harmonic Distortion", "Voltage THD <= 5% no load to full linear load"),
    ("R19", "2.1.K.1 (In Skid Diesel Fuel Tank)", "1. In Skid Diesel Fuel Tank", "UL 2085 sub-base fuel tank, >= 24 h at full standby load"),
    ("R20", "2.1.K.2", "2. Jacket-Water Heater", "Two 5000 W jacket-water heaters, 480 V 1-phase"),
    ("R21", "2.1.K (Generator Outdoor Housing)", "9. Generator Outdoor Housing", "Weatherproof, rodent-proof outdoor enclosure with silencer inside"),
]

CASES = [
    ("G1", "dev", "GEN-A", "data/submittals/cummins_DQKAB_submittal_CSDG.pdf"),
    ("G2", "dev", "GEN-A", "data/submittals/kohler_KD2000_G5-626.pdf"),
    ("G3", "heldout", "GEN-M", "data/submittals/kohler_KD1000_submittal_WPC6593.pdf"),
    ("G4", "heldout", "GEN-M", "data/submittals/cummins_s-6786.pdf"),
]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def main() -> None:
    pages = [norm(p.get_text()) for p in pymupdf.open(SPEC)]
    reqs = []
    for rid, loc, anchor, text in REQS:
        hits = [i + 1 for i, t in enumerate(pages) if norm(anchor) in t]
        assert hits, f"{rid}: anchor not found in spec: {anchor!r}"
        reqs.append({"req_id": rid, "spec_locator": loc, "spec_page": hits[0],
                     "spec_anchor": anchor, "requirement": text})
    OUT.mkdir(parents=True, exist_ok=True)
    spec_rel = SPEC.relative_to(ROOT).as_posix()
    (OUT / "genset_requirements.json").write_text(
        json.dumps({"spec": spec_rel, "requirements": reqs}, indent=2, ensure_ascii=False), encoding="utf-8")
    for cid, split, tag, sub in CASES:
        f = OUT / f"{cid}.json"
        if f.exists():  # never overwrite a labelled case
            continue
        case = {"case_id": cid, "split": split, "tool": "check_submittal", "spec": spec_rel, "tag": tag,
                "submittal": sub, "labeller": "", "labelled_on": "",
                "labels": [{"req_id": r["req_id"], "expected": "", "submittal_page": None,
                            "submittal_quote": "", "notes": ""} for r in reqs]}
        f.write_text(json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(reqs)} requirements; pages: {sorted({r['spec_page'] for r in reqs})}; cases: {[c[0] for c in CASES]}")


if __name__ == "__main__":
    main()
