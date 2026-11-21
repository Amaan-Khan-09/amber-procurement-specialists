"""Write the Project Alpha generator bid package: a bid form with the owner's leveling allowances
and four FICTIONAL bidder proposals in mixed formats (3 PDFs + 1 plain-text email).

Bidder companies are invented. The products they offer are real public models (Cat 3516C,
Cummins C2000D6, Kohler KD2000). Prices, terms and allowances are synthetic, written to be
realistic for 2026 and to contain the scope gaps a leveling agent must catch.
Answer key: eval/answer_keys/bids_genset.json (written by a person from these documents).
"""
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/bids"
FOOT = "FICTIONAL DOCUMENT for software testing (Project Alpha). Not a real offer."

CSS = """
body { font-family: sans-serif; font-size: 9.5pt; }
h1 { font-size: 15pt; margin-bottom: 2pt; } h2 { font-size: 11.5pt; margin-top: 10pt; }
table { border-collapse: collapse; width: 100%; } td, th { border: 0.5pt solid #888; padding: 3pt; font-size: 9pt; }
th { background-color: #e8e8e8; text-align: left; } .r { text-align: right; } .small { font-size: 8pt; color: #444; }
"""

DOCS = {}

DOCS["00_bid_form_generators"] = """
<h1>Project Alpha - Phase 1 Data Hall</h1>
<p><b>Bid Package BP-26-04: Standby Generators (GEN-A, GEN-B, GEN-C, GEN-D)</b><br/>Issued 2026-11-02 &nbsp; Bids due 2026-11-20</p>
<h2>1. Scope of supply</h2>
<p>Furnish four (4) 2000 kW / 2500 kVA standby diesel engine-generator sets, 480Y/277 V, 3-phase, 4-wire, 60 Hz, in
accordance with Specification Section 26 32 13 Engine Generators and the Equipment Schedule (Drawing E-601).
Bidders shall price the items below and state clearly anything excluded or qualified.</p>
<table>
<tr><th>Item</th><th>Scope item</th><th>Spec reference</th></tr>
<tr><td>S1</td><td>Generator sets, 4 x 2000 kW standby, per Section 26 32 13</td><td>2.1</td></tr>
<tr><td>S2</td><td>Outdoor sound-attenuated weatherproof enclosure, silencer inside</td><td>2.1.K.9</td></tr>
<tr><td>S3</td><td>UL 2085 sub-base fuel tank, 24 hours at full standby load</td><td>2.1.K (In Skid Diesel Fuel Tank)</td></tr>
<tr><td>S4</td><td>Remote annunciator, one per set</td><td>2.1.K.1</td></tr>
<tr><td>S5</td><td>Witnessed factory test</td><td>1.x Factory Test</td></tr>
<tr><td>S6</td><td>Freight to site (FOB jobsite, Ashburn VA)</td><td>-</td></tr>
<tr><td>S7</td><td>Offloading and rigging onto pads</td><td>-</td></tr>
<tr><td>S8</td><td>Start-up and checkout by manufacturer's representative</td><td>3.5</td></tr>
<tr><td>S9</td><td>Field load bank test (25/50/75/100 % steps)</td><td>3.6</td></tr>
<tr><td>S10</td><td>Operator training, minimum 4 hours</td><td>3.7</td></tr>
<tr><td>S11</td><td>Warranty: 5 years parts, travel and labor</td><td>1.x Warranty</td></tr>
</table>
<h2>2. Owner's leveling allowances</h2>
<p>Where a bid excludes or is silent on a scope item, the Owner will add the allowance below when comparing bids.
Where a bidder prices the item as an alternate, the bidder's own price is used instead.</p>
<table>
<tr><th>Item</th><th>Allowance used for leveling</th><th class="r">Amount (USD)</th></tr>
<tr><td>S2</td><td>Upgrade weather-protective to sound-attenuated enclosure</td><td class="r">38,000 per set</td></tr>
<tr><td>S3</td><td>Upgrade to 24-hour UL 2085 sub-base tank</td><td class="r">55,000 per set</td></tr>
<tr><td>S4</td><td>Remote annunciator</td><td class="r">3,200 per set</td></tr>
<tr><td>S5</td><td>Witnessed factory test</td><td class="r">6,000 per set</td></tr>
<tr><td>S6</td><td>Freight to site</td><td class="r">18,500 per set</td></tr>
<tr><td>S7</td><td>Offloading and rigging</td><td class="r">9,500 per set</td></tr>
<tr><td>S8</td><td>Start-up and checkout</td><td class="r">7,500 per set</td></tr>
<tr><td>S9</td><td>Field load bank test</td><td class="r">14,000 per set</td></tr>
<tr><td>S10</td><td>Operator training (4 hours)</td><td class="r">3,000 lump sum</td></tr>
<tr><td>S11</td><td>Extend warranty to 5 years parts, travel and labor</td><td class="r">24,000 per set</td></tr>
</table>
<h2>3. Commercial terms requested</h2>
<p>Prices firm for 60 days. State lead time in weeks after receipt of order (ARO) and after submittal approval.
Sales tax excluded from all bids. State any escalation, tariff or surcharge clauses.</p>
<p>Required on site: 2027-10-04 (all four sets).</p>
"""

DOCS["B1_northline_power"] = """
<h1>Northline Power Systems</h1>
<p class="small">Industrial power generation distributor - fictional company</p>
<p><b>Proposal NPS-26-1187</b> &nbsp; Date: 2026-11-18<br/>To: Project Alpha GC, Procurement &nbsp; Re: BP-26-04 Standby Generators</p>
<h2>Equipment offered</h2>
<p>Four (4) Caterpillar 3516C diesel generator sets, 2000 ekW / 2500 kVA standby, 480/277 V, 3-phase, 4-wire, 60 Hz,
1800 rpm, EPA Tier 2 certified for stationary emergency use.</p>
<table>
<tr><th>Line</th><th>Description</th><th class="r">Price (USD)</th></tr>
<tr><td>1</td><td>4 x Cat 3516C 2000 ekW gensets with level 2 sound attenuated walk-in enclosures, silencers inside</td><td class="r">4,316,000</td></tr>
<tr><td>2</td><td>4 x UL 2085 dual-wall sub-base tanks sized for 24 hrs at 100% standby load</td><td class="r">included</td></tr>
<tr><td>3</td><td>4 x remote annunciators (network type)</td><td class="r">included</td></tr>
<tr><td>4</td><td>Factory witness testing, one owner representative, Lafayette IN</td><td class="r">included</td></tr>
<tr><td>5</td><td>Freight to jobsite, Ashburn VA</td><td class="r">included</td></tr>
<tr><td>6</td><td>Start-up, commissioning and 4 hours operator training</td><td class="r">included</td></tr>
<tr><td></td><td><b>Total base bid</b></td><td class="r"><b>4,316,000</b></td></tr>
</table>
<h2>Alternates</h2>
<table>
<tr><th>Alt</th><th>Description</th><th class="r">Add (USD)</th></tr>
<tr><td>A1</td><td>Extend standard 2-year warranty to 5-year comprehensive (parts, travel, labor), all four sets</td><td class="r">96,000</td></tr>
</table>
<h2>Clarifications and exclusions</h2>
<ul>
<li>Standard warranty is 2 years / 1,500 hours; see Alternate A1.</li>
<li>Offloading, rigging and setting on pads by others.</li>
<li>Field load bank testing is excluded; resistive load bank can be rented at prevailing rates.</li>
<li>Price valid 30 days. Copper and steel content subject to metals surcharge at time of shipment.</li>
</ul>
<h2>Lead time</h2>
<p>Submittals 3 weeks ARO. Shipment 56-62 weeks after approved submittals.</p>
"""

DOCS["B2_tidewater_generator"] = """
<h1>TIDEWATER GENERATOR CO.</h1>
<p class="small">Fictional company</p>
<p><b>Quotation TGC-Q-55120</b> &nbsp; Valid until 2027-01-17<br/>Project: Project Alpha Phase 1 - BP-26-04</p>
<h2>Base offer</h2>
<p>Qty 4 - Cummins C2000D6 (model DQKAB) diesel generator set, 2000 kW / 2500 kVA standby rating, 277/480 V,
60 Hz, EPA Tier 2 stationary emergency. PowerCommand control, PMG excitation.</p>
<p>Each set includes: weather protective enclosure with critical grade silencer; 12-hour UL 2085 sub-base fuel tank;
remote annunciator; standard factory production test with certified report (witnessing available); start-up by
factory-trained technicians; on-site load bank test per specification 3.6; 4 hours of owner training;
5 year comprehensive warranty (parts, travel, labor).</p>
<table>
<tr><th>Item</th><th class="r">Unit price</th><th class="r">Qty</th><th class="r">Extended</th></tr>
<tr><td>C2000D6 genset package as described</td><td class="r">1,103,750</td><td class="r">4</td><td class="r">4,415,000</td></tr>
</table>
<h2>Terms</h2>
<ul>
<li>Freight: FOB factory, freight to site not included.</li>
<li>Unloading and setting: not included.</li>
<li>Witnessed factory test available at no charge with 4 weeks notice.</li>
<li>Pricing firm through validity date. No escalation.</li>
</ul>
<h2>Delivery</h2>
<p>50-54 weeks after receipt of approved submittals.</p>
"""

DOCS["B3_keystone_energy"] = """
<h1>Keystone Energy Equipment</h1>
<p class="small">Fictional company</p>
<p>Proposal KEE-2611-04 &nbsp; 2026-11-19</p>
<h2>Pricing summary</h2>
<table>
<tr><th>#</th><th>Item</th><th class="r">USD</th></tr>
<tr><td>1</td><td>(4) Kohler KD2000 2000 kW standby diesel generator sets, 277/480 V 60 Hz, Tier 2, in sound
attenuated aluminum enclosures (Sound Level 2), silencers inside</td><td class="r">3,980,000</td></tr>
<tr><td>2</td><td>Freight to jobsite</td><td class="r">incl.</td></tr>
<tr><td>3</td><td>Start-up and checkout by factory-authorized technician</td><td class="r">incl.</td></tr>
<tr><td>4</td><td>Owner training, 2 hours</td><td class="r">incl.</td></tr>
<tr><td>5</td><td>Field load bank test, 4 steps per 3.6</td><td class="r">incl.</td></tr>
<tr><td></td><td><b>Total</b></td><td class="r"><b>3,980,000</b></td></tr>
</table>
<h2>Options (not included in total)</h2>
<table>
<tr><th>Opt</th><th>Description</th><th class="r">Add per set</th></tr>
<tr><td>O1</td><td>UL 2085 sub-base fuel tank, 24 hr runtime at full load</td><td class="r">62,000</td></tr>
</table>
<h2>Exclusions</h2>
<ul>
<li>Fuel tanks unless Option O1 is selected.</li>
<li>Remote annunciators.</li>
<li>Witnessed factory testing (standard production test report provided).</li>
<li>Offloading and rigging.</li>
<li>Sales and use taxes.</li>
</ul>
<h2>Warranty and terms</h2>
<p>Manufacturer's standard 2-year limited warranty. Prices are subject to adjustment for tariffs, duties or trade
measures enacted after the proposal date. Lead time 68-74 weeks from order.</p>
"""

B4_EMAIL = """From: Dana Ruiz <estimating@ridgeway-power.example>
To: procurement@projectalpha-gc.example
Date: Thu, 19 Nov 2026 16:42:10 -0500
Subject: RE: BP-26-04 Standby Generators - budget number

Hi team,

As requested, our number for BP-26-04:

4 x Cummins C2000D6 2000kW standby 480V gensets with sound attenuated enclosures and 24 hr subbase tanks,
freight included, startup included.

Total: $4,240,000

Lead time approx 60 wks right now. Price firm 15 days.

Let me know if you need anything else.

Dana Ruiz
Ridgeway Power (fictional company)

-- FICTIONAL DOCUMENT for software testing (Project Alpha). Not a real offer.
"""


def render(name: str, html: str) -> None:
    path = OUT / f"{name}.pdf"
    story = pymupdf.Story(html=f"<html><body>{html}</body></html>", user_css=CSS)
    writer = pymupdf.DocumentWriter(str(path))
    rect = pymupdf.paper_rect("letter")
    area = rect + (50, 50, -50, -60)
    more = True
    while more:
        dev = writer.begin_page(rect)
        more, _ = story.place(area)
        story.draw(dev)
        writer.end_page()
    writer.close()
    doc = pymupdf.open(path)  # add the fictional-document footer to every page
    for pg in doc:
        pg.insert_text((50, rect.height - 30), FOOT, fontsize=7, fontname="helv", color=(0.4, 0.4, 0.4))
    doc.saveIncr()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, html in DOCS.items():
        render(name, html)
    (OUT / "B4_ridgeway_power_email.txt").write_text(B4_EMAIL, encoding="utf-8")
    print("wrote", sorted(p.name for p in OUT.iterdir() if p.is_file()))


if __name__ == "__main__":
    main()
