"""Edit the University of Houston master spec 26 32 13 (Engine Generators) into the
Project Alpha project spec, the way a specifier would: pick options, fill blanks.

Every decision is listed below so the edit is reproducible and auditable.
Output: data/specs/project_alpha/26_32_13_engine_generators_ALPHA.pdf (+ .txt)
"""
import re
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data/specs/UH_263213_engine_generators.pdf"
OUT = ROOT / "data/specs/project_alpha"

TOKEN = re.compile(r"\[[^\]]*\]\]?|_{3,}|\(\s+\)")

K, D = "KEEP", "DROP"  # keep the bracketed text / drop it entirely

# Nested options are flattened first with explicit edits (regex, replacement).
PRE = [
    (r"exceed \[_+\] gph\.\]", "exceed 145 gph.]"),
    (r"The tank shall have \[_+\] gallons of usable capacity", "The tank shall have 0 gallons of usable capacity"),
    (r"The tank shall be \[_+\] gallons capacity",
     "The tank shall have usable capacity for not less than 24 hours of operation at full standby load"),
    (r"\[5 psig\]", "5 psig"),
    (r"installed \[on\] \[inside\] enclosure", "installed inside enclosure"),
    (r"bird screen \[and motorized damper \(Level 2 only\)\] and", "bird screen and"),
    (r"\[Motor-operated intake dampers[^\]]*\]", ""),
    (r"painted \[in a color selected by the Architect\] \[in the manufacturer's standard color\.\]",
     "painted in the manufacturer's standard color.]"),
    # PART 3 nested
    (r"Install generator set \[inertia base\] on a \[6\"\]", 'Install generator set on a 6"'),
    (r"generator set \[inertia\] base", "generator set base"),
]

# Sentences rewritten after the options are resolved, so they read like a finished spec.
POST = [
    (r"is based on the Engine-Generator Equipment Schedule \(Drawing E-601\) generator and selected",
     "is scheduled on the Engine-Generator Equipment Schedule (Drawing E-601); basis-of-design sizing was selected"),
    (r"shall be rated for a continuous standby capacity of .*? while generating 480Y/277 volt",
     "shall be rated for the continuous standby capacity (kW and kVA at 0.8 PF) and output amperes "
     "scheduled on Drawing E-601 for its tag, while generating 480Y/277 volt"),
    (r"Texas Commission on Environmental Quality \(TCEQ\) Regulations and Requirements for Houston-Galveston",
     "Virginia Department of Environmental Quality (DEQ) Regulations and Requirements for Northern Virginia"),
    (r"conducted in Houston, Texas,", "conducted in Ashburn, Virginia,"),
    (r"in effect for the Houston-Galveston area", "in effect for the Northern Virginia area"),
    (r"turned over to UH Utility Services\.", "turned over to the Owner's Facilities Team."),
    (r"UH Utility Services must be present", "The Owner's Facilities Team must be present"),
    (r"capable of developing 2000 kW and 2500 kVA for motor starting",
     "capable of developing not less than 3000 kVA (2000 kW sets) and 1500 kVA (1000 kW sets) for motor starting"),
]

PART3 = {0: K, 1: K, 2: D, 3: D, 4: K, 5: D, 6: K, 7: K, 8: D, 9: K, 10: K, 11: K, 12: K, 13: K,
         14: K, 15: K, 16: K, 17: D, 18: K, 19: D, 20: "4 hours"}

# Decisions for PART 2, in order of appearance (index printed by --list).
PART2 = {
    0: "", 1: K, 2: K, 3: "s", 4: K, 5: "sound-attenuated weatherproof enclosure",
    6: K, 7: K, 8: "s",
    9: "the Engine-Generator Equipment Schedule (Drawing E-601)",
    10: "the scheduled", 11: "the scheduled", 12: "the scheduled",
    13: "480Y/277",
    14: "2000", 15: "2500", 16: D, 17: "30%",
    18: ("A permanent magnet generator (PMG) or equal shall provide excitation power to "
         "the automatic voltage regulator for immunity from voltage distortion caused by "
         "nonlinear SCR controlled loads on the generator.  The PMG shall sustain main "
         "field excitation power for optimum motor starting and to sustain short circuit "
         "current for selective operation and coordination of system overcurrent devices."),
    19: "Diesel", 20: K, 21: D, 22: D, 23: "electronic", 24: K,
    25: ("Diesel Fuel System:  Recommended No. 2 diesel fuel.  System shall be fuel injected "
         "and shall include a fuel transfer pump, automatic fuel shutoff, fuel oil/water "
         "separator, and fuel filters.  Average fuel consumption at full standby load shall "
         "not exceed 145 gph for 2000 kW sets and 75 gph for 1000 kW sets."),
    26: K, 27: D, 28: "-10°F", 29: D, 30: "122°F",
    31: "Virginia Department of Environmental Quality (DEQ)", 32: "Northern Virginia",
    33: "Northern Virginia",
    34: D, 35: "300'", 36: D, 37: "10 to 122°F",
    38: "100 hp fire pump (star-delta reduced voltage starting)",
    39: "a 1200 kVA UPS System with input filters", 40: "1600",
    41: D, 42: "four", 43: K, 44: K, 45: K, 46: K, 47: D, 48: K, 49: K, 50: K, 51: K,
    52: D, 53: "one set shall be monitored by the BAS and one set is spare.", 54: D,
    55: D, 56: "Surface", 57: D, 58: "microprocessor based annunciator with network communication",
    59: D, 60: "Low fuel in main tank warning", 61: D, 62: "Fuel in outer tank",
    63: "Spare/Customer alarm", 64: D,
    65: D, 66: "two", 67: "KIM #Hotstart (480 volt, 1-phase)", 68: D, 69: "5000W", 70: "s",
    71: '"critical"', 72: "required shall be shipped pre-installed and piped on top of the generator enclosure.",
    73: D,
    74: D,
    75: K, 76: D, 77: "2 gpm", 78: D, 79: "20 ft.", 80: D, 81: "120 volt", 82: D, 83: "1/4 hp",
    84: "400", 85: D, 86: "23", 87: D, 88: K, 89: D, 90: K, 91: D,
}


def text_of(src: Path) -> str:
    doc = pymupdf.open(src)
    t = "\n".join(p.get_text() for p in doc)
    t = re.sub(r"University of Houston Master Construction Specifications.*?Revision Date: [\d/]+\s*",
               "", t, flags=re.S)
    return re.sub(r"[ \t]*\n[ \t]*", " ", t)


def resolve(segment: str, decisions: dict | None) -> str:
    out, last = [], 0
    for k, m in enumerate(TOKEN.finditer(segment)):
        tok = m.group(0)
        if decisions is None:  # PART 1 / PART 3: keep first option, generic fill
            d = K
        else:
            if k not in decisions:
                sys.exit(f"no decision for PART 2 token {k}: {segment[m.start()-60:m.end()+20]!r}")
            d = decisions[k]
        if d == D:
            rep = ""
        elif d == K:
            inner = tok.strip("[]")
            rep = "as scheduled" if re.fullmatch(r"_+|\(\s+\)", inner) or re.fullmatch(r"_+", tok) else inner
        else:
            rep = d
        out.append(segment[last:m.start()] + rep)
        last = m.end()
    out.append(segment[last:])
    s = "".join(out)
    s = re.sub(r"\s+([,.])", r"\1", s)
    s = re.sub(r"(?<=[.:]) {2,}", "\x00", s)   # keep two spaces after a sentence
    s = re.sub(r" {2,}", " ", s)
    return s.replace("\x00", "  ")


def paragraphs(s: str) -> list[str]:
    # Break before outline markers ("PART 2", "2.1 TITLE", "A. ", "1. ", "a. ", "1) "), but only
    # where the previous text ended a sentence, so "Division 22. Engine" or "0.8 PF" never split.
    marker = r"(?:PART \d|\d\.\d+ [A-Z]{3,}|[A-Z]\. |\d{1,2}\. |[a-z]\. |\d{1,2}\) )"
    s = re.sub(r"(?<=[.:;)\]])\s+(?=" + marker + ")", "\n", s)
    s = re.sub(r"\s+(?=PART \d|\d\.\d+ [A-Z]{3,})", "\n", s)
    # list items without a full stop before them ("Overcrank shutdown b. Low coolant ...")
    s = re.sub(r"(?<!Division)(?<!Section)(?<!NFPA)(?<!Level)(?<!Class)(?<!No\.) (?=(?:[a-t]\.|\d{1,2}[.)]) [A-Z][a-z])",
               "\n", s)
    out = []
    for p in s.split("\n"):
        p = p.strip().rstrip("]").strip()
        if p and not re.fullmatch(r"(?:[A-Za-z]|\d{1,2})[.)]", p):  # drop markers left empty by dropped options
            out.append(p)
    return out


def main() -> None:
    t = text_of(SRC)
    for pat, rep in PRE:
        t, n = re.subn(pat, rep.replace("\\", "\\\\"), t)
        assert n == 1, f"PRE pattern matched {n} times: {pat}"
    i, j = t.find("PART 2 - PRODUCTS"), t.find("PART 3")
    head, p2, tail = t[:i], t[i:j], t[j:]
    if "--list" in sys.argv:
        seg = tail if "--part3" in sys.argv else p2
        for k, m in enumerate(TOKEN.finditer(seg)):
            print(k, repr(seg[max(0, m.start() - 60):m.end() + 20])[:220])
        return
    body = resolve(head, None) + resolve(p2, PART2) + resolve(tail, PART3)
    for pat, rep in POST:
        body, n = re.subn(pat, rep, body, flags=re.S)
        assert n == 1, f"POST pattern matched {n} times: {pat}"
    body = body.replace("Insert Project Name", "Project Alpha - Phase 1 Data Hall")
    body = body.replace("AE Project Number:", "AE Project Number: PA-2026-001")
    leftovers = TOKEN.findall(body)
    assert not leftovers, leftovers
    paras = paragraphs(body)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "26_32_13_engine_generators_ALPHA.txt").write_text("\n".join(paras), encoding="utf-8")

    doc = pymupdf.open()
    W, H, M = 612, 792, 54
    header = "PROJECT ALPHA - PHASE 1 DATA HALL          SECTION 26 32 13  ENGINE GENERATORS"
    page, y, n = None, 0, 0

    def new_page():
        nonlocal page, y, n
        n += 1
        page = doc.new_page(width=W, height=H)
        page.insert_text((M, 36), header, fontsize=8, fontname="helv")
        page.insert_text((W / 2 - 40, H - 30), f"26 32 13 - {n}", fontsize=8, fontname="helv")
        y = 60

    new_page()
    for p in paras:
        bold = p.startswith("PART") or re.match(r"\d\.\d+ ", p)
        indent = 0 if bold else (18 if re.match(r"[A-Z]\. ", p) else 36 if re.match(r"\d{1,2}\. ", p) else 54)
        size, font = 9.5, ("hebo" if bold else "helv")
        # insert_textbox writes NOTHING if the text overflows, so measure first with a dry run
        # on a scratch page, then place it where it fits.
        scratch = pymupdf.open().new_page(width=W, height=H)
        tall = pymupdf.Rect(M + indent, 0, W - M, H)
        spare = scratch.insert_textbox(tall, p, fontsize=size, fontname=font)
        assert spare >= 0, f"paragraph taller than a page: {p[:60]}"
        h = H - spare + 4
        if y + h > H - 50:
            new_page()
        rc = page.insert_textbox(pymupdf.Rect(M + indent, y, W - M, y + h), p, fontsize=size, fontname=font)
        assert rc >= 0, f"paragraph did not fit: {p[:60]}"
        y += h + 2
    doc.save(OUT / "26_32_13_engine_generators_ALPHA.pdf")

    # every paragraph must be present in the PDF text
    pdf_text = re.sub(r"\s+", " ", " ".join(pg.get_text() for pg in pymupdf.open(OUT / "26_32_13_engine_generators_ALPHA.pdf")))
    missing = [p[:60] for p in paras if re.sub(r"\s+", " ", p)[:50] not in pdf_text]
    assert not missing, f"missing from PDF: {missing}"
    print(f"wrote {n} pages, {len(paras)} paragraphs, all present in PDF")


if __name__ == "__main__":
    main()
