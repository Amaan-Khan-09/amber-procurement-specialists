"""Write the Project Alpha vendor data used by vendor discovery, pre-qualification and the supplier-reply loop.

Everything here is FICTIONAL and says so on every page: a vendor master (like an ERP export), the general contractor's
pre-qualification policy, three suppliers' pre-qualification packets, and two suppliers' replies to our questions.
The products named are the real public models already in data/submittals; the companies are invented (the four
bidders are the ones in data/bids). The values planted in each document are written to the answer keys in the same
run (eval/answer_keys/prequal_GEN.json, replies_GEN.json), before any specialist reads them.
"""
import csv
import json
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "vendors"
REPLIES = ROOT / "data" / "replies"
KEYS = ROOT / "eval" / "answer_keys"
FOOT = "FICTIONAL DOCUMENT for software testing (Project Alpha). Not a real company or offer."
CSS = """
body { font-family: sans-serif; font-size: 9.5pt; }
h1 { font-size: 14pt; margin-bottom: 2pt; } h2 { font-size: 11pt; margin-top: 9pt; }
table { border-collapse: collapse; width: 100%; } td, th { border: 0.5pt solid #888; padding: 3pt; font-size: 9pt; }
th { background-color: #e8e8e8; text-align: left; }
"""

DIRECTORY = [
    # vendor_id, name, role, manufacturers, classes, max_kw, sells_new, branch, state, miles, on_time, open_ncrs, updated, bid_file
    ["V-NPS", "Northline Power Systems", "distributor", "Caterpillar", "generator", 4000, "yes", "Richmond", "VA", 105, 0.88, 0, "2026-09-30", "B1_northline_power.pdf"],
    ["V-TGC", "Tidewater Generator Co.", "dealer", "Cummins", "generator", 3500, "yes", "Norfolk", "VA", 190, 0.92, 1, "2025-06-30", "B2_tidewater_generator.pdf"],
    ["V-KEE", "Keystone Energy Equipment", "distributor", "Kohler", "generator", 3000, "yes", "Baltimore", "MD", 60, 0.79, 2, "2026-08-15", "B3_keystone_energy.pdf"],
    ["V-RWP", "Ridgeway Power", "dealer", "Cummins", "generator", 2500, "yes", "Harrisburg", "PA", 150, None, 0, "2026-11-19", "B4_ridgeway_power_email.txt"],
    ["V-PEP", "Potomac Engine & Power", "distributor", "MTU", "generator", 3250, "yes", "Frederick", "MD", 45, 0.90, 0, "2026-07-01", ""],
    ["V-ODG", "Old Dominion Generator Service", "dealer", "Kohler", "generator", 1000, "yes", "Winchester", "VA", 50, 0.95, 0, "2026-10-10", ""],
    ["V-SRP", "Shenandoah Rental Power", "rental", "Caterpillar;Cummins", "generator", 2000, "no", "Manassas", "VA", 25, None, 0, "2026-05-20", ""],
    ["V-BRC", "Blue Ridge Critical Power", "distributor", "Vertiv", "ups;switchgear", None, "yes", "Sterling", "VA", 8, 0.91, 0, "2026-10-01", ""],
]

POLICY = """
<h1>Project Alpha GC - Supplier Pre-qualification Policy PQ-01</h1>
<p>Rev 2, issued 2026-10-01. Applies to suppliers of major electrical equipment for Project Alpha (bid packages BP-26-01 to
BP-26-08). A supplier is pre-qualified only when every criterion below is met and evidenced in writing.</p>
<table>
<tr><th>No.</th><th>Criterion</th></tr>
<tr><td>Q1</td><td>Commercial general liability insurance of at least $2,000,000 per occurrence, shown on a certificate of insurance.</td></tr>
<tr><td>Q2</td><td>The certificate of insurance must remain valid through the equipment need date. A certificate that expires earlier requires a renewal certificate before award.</td></tr>
<tr><td>Q3</td><td>Experience modification rate (EMR) of 1.00 or lower, three-year average, on the insurer's letter.</td></tr>
<tr><td>Q4</td><td>A current letter from the manufacturer authorizing the supplier to sell and service the product offered, attached to the response.</td></tr>
<tr><td>Q5</td><td>Emergency service response within 4 hours at the site (Ashburn, VA), 24/7, by factory-trained technicians. Name the service branch.</td></tr>
<tr><td>Q6</td><td>At least three completed projects with generator sets of 1500 kW or larger in the last five years, with references.</td></tr>
<tr><td>Q7</td><td>The supplier must not be excluded from federal procurement. The Owner checks the exclusion list (SAM.gov) before award; a supplier's self-certification is recorded but is not verification.</td></tr>
</table>
"""


def packet(name, date, mfr, years, carrier, per_occ, aggregate, expires, emr_rows, emr_avg, auth, service, projects, selfcert):
    rows = "".join(f"<tr><td>{p}</td><td>{y}</td><td>{kw}</td><td>{ref}</td></tr>" for p, y, kw, ref in projects)
    emr = "".join(f"<tr><td>{y}</td><td>{v}</td></tr>" for y, v in emr_rows)
    return f"""
<h1>{name}</h1>
<p><b>Supplier pre-qualification questionnaire - response</b><br/>Project Alpha, bid package BP-26-04 Standby Generators.
Date: {date}</p>
<h2>1. Equipment and manufacturer</h2>
<p>Manufacturer of the equipment offered: {mfr}. The manufacturer has produced engine-generator sets for {years} years.</p>
<h2>2. Insurance (certificate of insurance attached)</h2>
<table><tr><th>Coverage</th><th>Carrier</th><th>Per occurrence</th><th>Aggregate</th><th>Expires</th></tr>
<tr><td>Commercial general liability</td><td>{carrier}</td><td>{per_occ}</td><td>{aggregate}</td><td>{expires}</td></tr></table>
<h2>3. Safety record (insurer's letter)</h2>
<table><tr><th>Policy year</th><th>EMR</th></tr>{emr}<tr><td>Three-year average</td><td>{emr_avg}</td></tr></table>
<h2>4. Manufacturer authorization</h2><p>{auth}</p>
<h2>5. Emergency service</h2><p>{service}</p>
<h2>6. Completed projects, last five years</h2>
<table><tr><th>Project</th><th>Year</th><th>Set size (kW)</th><th>Reference</th></tr>{rows}</table>
<h2>7. Federal exclusion</h2><p>{selfcert}</p>
"""


PACKETS = {
    "V-NPS": packet("Northline Power Systems (fictional company)", "2026-11-18", "Caterpillar", "more than 50",
                    "Harborline Mutual (fictional)", "$5,000,000", "$10,000,000", "2028-06-30",
                    [("2024", "0.85"), ("2025", "0.80"), ("2026", "0.81")], "0.82",
                    "Attached: Caterpillar dealer authorization letter dated 2026-09-12 covering the 3516C generator set.",
                    "Service branch: Richmond, VA. 24/7 emergency response within 4 hours at the Ashburn site by factory-trained technicians.",
                    [("Data center DC-7, Richmond VA", "2025", "2500", "J. Ortiz, facilities"),
                     ("Hospital tower, Norfolk VA", "2024", "2000", "M. Chen, engineering"),
                     ("Campus central plant, Charlottesville VA", "2023", "1750", "R. Patel, utilities"),
                     ("Water treatment plant, Roanoke VA", "2022", "1500", "S. Brooks, operations"),
                     ("Office park, Glen Allen VA", "2022", "800", "T. Nguyen, property")],
                    "We certify that the company is not debarred, suspended or excluded from federal procurement."),
    "V-TGC": packet("Tidewater Generator Co. (fictional company)", "2026-11-19", "Cummins", "more than 40",
                    "Bayside Casualty (fictional)", "$2,000,000", "$4,000,000", "2027-03-31",
                    [("2024", "0.95"), ("2025", "0.90"), ("2026", "0.88")], "0.91",
                    "Cummins authorization letter: available on request.",
                    "Mid-Atlantic coverage through our partner service network, 4-hour emergency response.",
                    [("Colocation hall, Virginia Beach VA", "2025", "2250", "A. Ruiz, operations"),
                     ("Port authority terminal, Norfolk VA", "2024", "2000", "K. Ward, engineering"),
                     ("County courthouse, Suffolk VA", "2023", "1250", "L. Gray, facilities"),
                     ("Naval supply depot (contractor), Chesapeake VA", "2022", "2000", "P. Diaz, project manager")],
                    "We certify that the company is not debarred, suspended or excluded from federal procurement."),
    "V-KEE": packet("Keystone Energy Equipment (fictional company)", "2026-11-19", "Kohler", "more than 60",
                    "Ironbridge Assurance (fictional)", "$3,000,000", "$6,000,000", "2027-12-31",
                    [("2024", "1.31"), ("2025", "1.22"), ("2026", "1.19")], "1.24",
                    "Attached: Kohler distributor authorization letter dated 2026-07-01 covering the KD2000 generator set.",
                    "Service branch: Baltimore, MD. 24/7 emergency response within 4 hours at the Ashburn site by factory-trained technicians.",
                    [("Data center campus, Ashburn VA", "2025", "2000", "D. Kim, critical facilities"),
                     ("University hospital, Baltimore MD", "2024", "1500", "E. Stone, engineering"),
                     ("Logistics hub, Hagerstown MD", "2023", "2500", "F. Lopez, operations")],
                    "We certify that the company is not debarred, suspended or excluded from federal procurement."),
}

# Planted answers (status per criterion). V-RWP sent no packet.
PREQUAL_KEY = {
    "V-NPS": {"P1": "meets", "P2": "meets", "Q1": "meets", "Q2": "meets", "Q3": "meets", "Q4": "meets", "Q5": "meets",
              "Q6": "meets", "Q7": "needs_verification"},
    "V-TGC": {"P1": "meets", "P2": "meets", "Q1": "meets", "Q2": "needs_verification", "Q3": "meets",
              "Q4": "needs_verification", "Q5": "needs_verification", "Q6": "meets", "Q7": "needs_verification"},
    "V-KEE": {"P1": "meets", "P2": "meets", "Q1": "meets", "Q2": "meets", "Q3": "fails", "Q4": "meets", "Q5": "meets",
              "Q6": "meets", "Q7": "needs_verification"},
    "V-RWP": {"P1": "meets", "P2": "needs_verification", "Q1": "needs_verification", "Q2": "needs_verification",
              "Q3": "needs_verification", "Q4": "needs_verification", "Q5": "needs_verification",
              "Q6": "needs_verification", "Q7": "needs_verification"},
}
PREQUAL_NOTES = {
    ("V-TGC", "Q2"): "The certificate expires 2027-03-31, before the 2027-10-04 need date: a renewal certificate is required.",
    ("V-TGC", "Q4"): "The letter is 'available on request', not attached.",
    ("V-TGC", "Q5"): "No branch is named; the vendor master lists Norfolk VA, 190 miles away (record of 2025-06-30). Conflicting records.",
    ("V-TGC", "Q6"): "Four projects listed, three of them 1500 kW or larger (1250 kW does not count).",
    ("V-KEE", "Q3"): "Three-year average EMR 1.24 > 1.00.",
    ("V-NPS", "Q6"): "Five projects listed, four of them 1500 kW or larger.",
    ("V-RWP", "P1"): "From the bid (Cummins), via the product link; no packet was sent.",
}

B1_REPLY = """From: Northline Power Systems (fictional company)
To: Project Alpha GC, Procurement
Date: 2026-12-02
Subject: RE: BP-26-04 submittal review comments - Caterpillar 3516C (GEN-A to GEN-D)

Responses to your review comments, in your numbering:

1. Motor starting: 5,840 skVA at 30% voltage dip.
2. Excitation: permanent magnet generator (PMG) excitation is included.
3. Engine: 16 cylinder, 4 cycle, turbocharged and aftercooled.
4. Governor: electronic, isochronous from no load to full load.
5. Starting: 24 volt DC electric starter.
6. Fuel consumption at 100% standby load: 133.6 gph.
7. Cooling: the 50 C (122 F) ambient cooling package will be confirmed with the final submittal.
8. Ambient and altitude: full rated output at 300 ft and up to 122 F ambient with the 50 C cooling package.
9. Alternator: 4-pole, brushless, two thirds pitch winding; insulation class H.
10. Alternator space heater: 120 V, single phase, included.
11. Output circuit breaker: 3 pole, solid state trip unit.
12. Voltage regulation: +/-0.25% no load to rated load. Voltage THD: less than 5% no load to full linear load.
13. Jacket water heater: one 9000 W, 480 V, 1 phase heater per set.
14. Enclosure: weatherproof and rodent-proof (screened openings), silencer mounted inside the enclosure.

Regards,
Northline Power Systems

-- FICTIONAL DOCUMENT for software testing (Project Alpha). Not a real company or offer.
"""

B2_REPLY = """From: Tidewater Generator Co. (fictional company)
To: Project Alpha GC, Procurement
Date: 2026-12-03
Subject: RE: BP-26-04 clarifications and pre-qualification items - Cummins DQKAB

1. Fuel tank: we will supply a 24 hour UL 2085 sub-base fuel tank in place of the 12-hour tank, add $18,000 per set.
2. Enclosure: weatherproof and rodent-proof (rodent screens on all openings), critical grade silencer mounted inside the enclosure.
3. Insurance: renewal certificate attached. Commercial general liability $2,000,000 per occurrence, expires 2028-03-31.
4. Manufacturer authorization: Cummins authorization letter dated 2026-11-30 attached.
5. Emergency service: service branch Fredericksburg, VA, 24/7 emergency response within 4 hours at the Ashburn site by
   factory-trained technicians.

Regards,
Tidewater Generator Co.

-- FICTIONAL DOCUMENT for software testing (Project Alpha). Not a real company or offer.
"""

REPLY_KEY = {
    "case_id": "REPLIES-GEN",
    "labeller": "planted by tools/data_prep/make_vendor_data.py (the replies' author); written before any reply was read",
    "replies": {
        "B1": {"file": "data/replies/B1_northline_reply.txt", "requirements": {
            "R03": ["complies", "5,840 skVA at 30% dip >= 3000 kVA"],
            "R04": ["complies", "PMG included"],
            "R05": ["complies", "16 cylinder, 4 cycle, turbocharged and aftercooled"],
            "R06": ["complies", "electronic, isochronous"],
            "R07": ["complies", "24 volt DC electric starter"],
            "R08": ["complies", "133.6 gph <= 145"],
            "R09": ["unclear", "a non-answer: 'will be confirmed with the final submittal'"],
            "R11": ["unclear", "full rating is promised only 'with the 50 C cooling package', which item 7 leaves unconfirmed: a conditional claim"],
            "R13": ["complies", "4-pole, brushless, two thirds pitch"],
            "R14": ["complies", "class H"],
            "R15": ["complies", "120 V single phase space heater"],
            "R16": ["complies", "3 pole, solid state trip"],
            "R17": ["complies", "+/-0.25%"],
            "R18": ["complies", "THD < 5%"],
            "R20": ["deviates", "one 9000 W heater; the spec requires two 5000 W"],
            "R21": ["complies", "weatherproof, rodent-proof, silencer inside"]}},
        "B2": {"file": "data/replies/B2_tidewater_reply.txt", "requirements": {
            "R19": ["complies", "24 h UL 2085 tank, add $18,000 per set"],
            "R21": ["complies", "weatherproof, rodent-proof, silencer inside"]},
            "prequal": {"Q2": ["meets", "renewal certificate, expires 2028-03-31"],
                        "Q4": ["meets", "letter dated 2026-11-30 attached"],
                        "Q5": ["meets", "Fredericksburg VA branch, 4 hours; the vendor master still says Norfolk (record of 2025-06-30)"]},
            "price_change": {"S3": 72000, "note": "the reply prices the 24 h UL 2085 tank at $18,000 x 4 sets, replacing the owner's allowance"}},
    },
}


def render(path: Path, html: str) -> None:
    story = pymupdf.Story(html=f"<html><body>{html}</body></html>", user_css=CSS)
    writer = pymupdf.DocumentWriter(str(path))
    rect = pymupdf.paper_rect("letter")
    more = True
    while more:
        dev = writer.begin_page(rect)
        more, _ = story.place(rect + (50, 50, -50, -60))
        story.draw(dev)
        writer.end_page()
    writer.close()
    doc = pymupdf.open(path)
    for pg in doc:
        pg.insert_text((50, rect.height - 30), FOOT, fontsize=7, fontname="helv", color=(0.4, 0.4, 0.4))
    doc.saveIncr()


def main() -> None:
    (OUT / "packets").mkdir(parents=True, exist_ok=True)
    REPLIES.mkdir(parents=True, exist_ok=True)
    with (OUT / "supplier_directory.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["vendor_id", "name", "role", "manufacturers", "product_classes", "max_genset_kw", "sells_new",
                    "service_branch", "branch_state", "branch_miles_to_site", "on_time_24mo", "open_ncrs",
                    "record_updated", "bid_file", "record_note"])
        for r in DIRECTORY:
            w.writerow([("" if v is None else v) for v in r] + ["FICTIONAL vendor master record (mock ERP export)"])
    render(OUT / "prequal_policy_ALPHA.pdf", POLICY)
    for vid, html in PACKETS.items():
        render(OUT / "packets" / f"{vid}_prequal.pdf", html)
    (REPLIES / "B1_northline_reply.txt").write_text(B1_REPLY, encoding="utf-8")
    (REPLIES / "B2_tidewater_reply.txt").write_text(B2_REPLY, encoding="utf-8")
    key = {"case_id": "PQ-GEN", "split": "dev", "tool": "prequalify_vendors",
           "labeller": "planted by tools/data_prep/make_vendor_data.py (the packets' author); written before any packet was read",
           "status_vocabulary": "meets | fails | needs_verification",
           "expected_route": {"meets": "decide", "fails": "decide", "needs_verification": "ask_supplier",
                              "Q7": "engineer (the owner checks the federal exclusion list; a self-certification is not verification)"},
           "vendors": {v: {c: {"expected": s, "notes": PREQUAL_NOTES.get((v, c), "")} for c, s in crit.items()}
                       for v, crit in PREQUAL_KEY.items()}}
    (KEYS / "prequal_GEN.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    (KEYS / "replies_GEN.json").write_text(json.dumps(REPLY_KEY, indent=1), encoding="utf-8")
    print("wrote vendor master, policy, 3 packets, 2 replies and their keys")


if __name__ == "__main__":
    main()
