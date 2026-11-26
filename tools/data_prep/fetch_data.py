"""Download the public third-party documents used for testing into data/ (they are copyrighted, so they are
not committed). Each file is checked against the SHA-256 prefix recorded when the project was built; a vendor
may have revised a document since, so a mismatch is a warning, not an error.

usage: python tools/data_prep/fetch_data.py [--only NAME_SUBSTRING]
Sources and licences: data/SOURCES.md
"""
import argparse
import hashlib
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]

# (relative path, sha256 prefix, url)
FILES = [
    ("data/specs/UH_263213_engine_generators.pdf", "c8b03995d544c870",
     "https://uh.edu/facilities-planning-construction/vendor-resources/owners-design-criteria/master-specs/pdf/26-32-13-engine-generators.pdf"),
    ("data/specs/UMB_262300_LV_switchgear.pdf", "665da35e550c41bc",
     "https://umaryland.edu/media/umb/af/dc/documents/division-26/262300-Low-Voltage-Switchgear.pdf"),
    ("data/specs/NU_262300_LV_switchgear.pdf", "520aacd5f723204c",
     "https://northwestern.edu/facilities/docs/construction/design_guidelines/26_electrical/NU_26%202300%20-%20LOW-VOLTAGE%20SWITCHGEAR.pdf"),
    ("data/specs/UFGS_26_32_15.pdf", "e89109f2aafb2bbf", "https://www.wbdg.org/FFC/DOD/UFGS/UFGS%2026%2032%2015.pdf"),
    ("data/specs/UFGS_26_23_00.pdf", "07e60178ac34d022", "https://www.wbdg.org/FFC/DOD/UFGS/UFGS%2026%2023%2000.pdf"),
    ("data/specs/UFGS_26_33_53.pdf", "80889b29aa4d617c", "https://www.wbdg.org/FFC/DOD/UFGS/UFGS%2026%2033%2053.pdf"),
    ("data/submittals/cummins_DQKAB_submittal_CSDG.pdf", "fea77f3a450269a1",
     "https://csdieselgenerators.com/Images/Generators/5104/new-cummins-dqkab-opu-submittal-csdg-5104-5105-1781896577.pdf"),
    ("data/submittals/cummins_s-6786.pdf", "93f22fca8f1b6596",
     "https://www.cummins.com/sites/default/files/2025-06/s-6786-spec-sheet.pdf"),
    ("data/submittals/kohler_KD2000_G5-626.pdf", "3c3f80275e7b5f3a", "https://resources.kohler.com/power/kohler/industrial/pdf/g5626.pdf"),
    ("data/submittals/kohler_KD1000_submittal_WPC6593.pdf", "fd3cf1f9784b2158",
     "https://woodstockpower.com/wp-content/uploads/2024/09/WPC_PO-6593_1000-kW-KD1000_Submittal.pdf"),
    ("data/submittals/winnipeg_generator_shop_drawings.pdf", "610a189e19602330",
     "https://legacy.winnipeg.ca/finance/findata/matmgt/documents/2016/803-2016/803-2016_Appendix_B_Generator_Shop_Drawings.pdf"),
    ("data/submittals/mtu_16V4000_DS2250_60Hz_50C.pdf", "df1c4579639b7453",
     "https://www.mtu-solutions.com/content/dam/mtu/products/power-generation/powergeneration-product-list-latest/231210_PG_Spec_16V4000DS2250G04_2250kW_3D_FC_60Hz_50C.pdf"),
    ("data/submittals/kohler_2000ROZD4_spec_sheet.pdf", "d9a1b687ecabba83",
     "https://csdieselgenerators.com/Images/Generators/3592/Kohler-2000ROZD4-spec-sheet.pdf"),
    ("data/submittals/cat_3516C_2000ekW_LEHE1376.pdf", "48d615fde5bbe118",
     "https://emc.cat.com/n/api/pubdirect?media_string_id=LEHE1376-"),
    ("data/submittals/cummins_C2000D6E_spec_sheet.pdf", "4e9bd4e02761997f",
     "https://csdieselgenerators.com/Images/Generators/4579/New-Cummins-C2000D6E-spec-sheet.pdf"),
    ("data/submittals/generac_MD2000_spec_sheet.pdf", "20a12d5014313667",
     "https://generac.com/globalassets/products/business/stationary-generators/diesel-industrial-generators/spec-sheets/md2000-spec-sheet.pdf"),
    ("data/submittals/vertiv_EXL_S1_300-1200kW.pdf", "cc897db544e07399",
     "https://www.vertiv.com/4a5725/globalassets/products/critical-power/uninterruptible-power-supplies-ups/liebert-exl-s1-/liebert-exl-s1_300-to-1200-kw.pdf"),
    ("data/submittals/vertiv_EXL_S1_site_planning_1000-1200kVA_SL-26092.pdf", "0cd7a33dabfe3984",
     "https://www.vertiv.com/globalassets/products/critical-power/uninterruptible-power-supplies-ups/liebert-exl-s1-site-planning-data-1000-1200kva-sl-26092.pdf"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="only files whose path contains this text")
    a = ap.parse_args()
    failed = 0
    for rel, sha, url in FILES:
        if a.only and a.only not in rel:
            continue
        dst = ROOT / rel
        if dst.exists() and hashlib.sha256(dst.read_bytes()).hexdigest().startswith(sha):
            print(f"ok       {rel}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            r = httpx.get(url, timeout=120, follow_redirects=True,
                          headers={"User-Agent": "amber-procure-data-fetch/0.1 (research prototype)"})
            r.raise_for_status()
        except httpx.HTTPError as e:
            failed += 1
            code = getattr(getattr(e, "response", None), "status_code", None)
            why = "the site refuses automated downloads" if code in (401, 403) else str(e).splitlines()[0]
            print(f"FAILED   {rel}: {why}.\n         Open {url} in a browser and save the file as {rel}")
            continue
        dst.write_bytes(r.content)
        got = hashlib.sha256(r.content).hexdigest()
        note = "" if got.startswith(sha) else "  (content differs from the version used for the answer keys; check page numbers)"
        print(f"fetched  {rel}{note}")

    # derived test input: the two Vertiv documents merged into one submittal package (case U1)
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from make_ups_spec import merge
        merge()
    except Exception as e:  # never fail the whole fetch over the derived file
        print(f"skip     UPS package: {e}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
