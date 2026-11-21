# Data sources

All accessed 21 Nov 2026. Third-party PDFs are **not committed** to the public repo, because they are copyrighted. `tools/data_prep/fetch_data.py` (to write) downloads them from these URLs and checks their hashes.

## Specifications
| File | What | Source | Status |
|---|---|---|---|
| `specs/UH_263213_engine_generators.pdf` | Owner master spec 26 32 13, Engine Generators (rev. 1/29/2018) | University of Houston: https://uh.edu/facilities-planning-construction/vendor-resources/owners-design-criteria/master-specs/pdf/26-32-13-engine-generators.pdf | **Edited into the Project Alpha spec** |
| `specs/project_alpha/26_32_13_engine_generators_ALPHA.pdf` | Project Alpha generator spec (ours) | Made by `tools/data_prep/make_alpha_genset_spec.py`. Every option and blank decision is listed in that script | ours, reproducible |
| `specs/UMB_262300_LV_switchgear.pdf` | Owner master spec 26 23 00, LV Switchgear | University of Maryland, Baltimore: https://umaryland.edu/media/umb/af/dc/documents/division-26/262300-Low-Voltage-Switchgear.pdf | to edit for Project Alpha |
| `specs/NU_262300_LV_switchgear.pdf` | Owner design guideline 26 23 00 | Northwestern University: https://northwestern.edu/facilities/docs/construction/design_guidelines/26_electrical/NU_26%202300%20-%20LOW-VOLTAGE%20SWITCHGEAR.pdf | spare / held-out |
| `specs/UFGS_26_32_15.pdf`, `UFGS_26_23_00.pdf`, `UFGS_26_33_53.pdf` | US federal guide specs (public domain) | https://www.wbdg.org/FFC/DOD/UFGS/ | 26 33 53 (UPS) to edit for Project Alpha |

## Submittals and datasheets (real, public)
| File | Product | Source |
|---|---|---|
| `submittals/cummins_DQKAB_submittal_CSDG.pdf` | Cummins 2000 kW DQKAB submittal package (66 p, record-only) | https://csdieselgenerators.com/Images/Generators/5104/new-cummins-dqkab-opu-submittal-csdg-5104-5105-1781896577.pdf |
| `submittals/kohler_KD2000_G5-626.pdf` | Kohler KD2000 spec sheet G5-626 (9/23) | https://resources.kohler.com/power/kohler/industrial/pdf/g5626.pdf |
| `submittals/kohler_KD1000_submittal_WPC6593.pdf` | Kohler KD1000 submittal (105 p; 46 scanned pages) | https://woodstockpower.com/wp-content/uploads/2024/09/WPC_PO-6593_1000-kW-KD1000_Submittal.pdf |
| `submittals/cummins_s-6786.pdf` | Cummins C600–C1000D6E spec sheet S-6786 (Rev. 5/25) | https://www.cummins.com/sites/default/files/2025-06/s-6786-spec-sheet.pdf |
| `submittals/winnipeg_generator_shop_drawings.pdf` | Kohler 45REZG submittal (City of Winnipeg bid 803-2016; 35 scanned pages) | https://legacy.winnipeg.ca/finance/findata/matmgt/documents/2016/803-2016/803-2016_Appendix_B_Generator_Shop_Drawings.pdf |
| `submittals/vertiv_EXL_S1_site_planning_1000-1200kVA_SL-26092.pdf` | Vertiv Liebert EXL S1 1000–1200 kVA site planning data | https://www.vertiv.com/globalassets/products/critical-power/uninterruptible-power-supplies-ups/liebert-exl-s1-site-planning-data-1000-1200kva-sl-26092.pdf |
| `submittals/vertiv_EXL_S1_300-1200kW.pdf` | Vertiv Liebert EXL S1 300–1200 kW brochure / specs | https://www.vertiv.com/4a5725/globalassets/products/critical-power/uninterruptible-power-supplies-ups/liebert-exl-s1-/liebert-exl-s1_300-to-1200-kw.pdf |

**Still needed:** an LV switchgear submittal or datasheet. The City of Hastings Eaton drawings returned 403. Try Eaton's Magnum DS technical data or another public bid package.

## Lead times
`leadtime_sources/leadtime_evidence.csv` has one row per published figure, with the quote, date and basis. The quotes were captured with a page-reading tool, so **a person must re-check each quote against the live page before submission.**
- Terrapin Construction Group, "Switchgear, Transformer, and Generator Lead Times in 2026" (W. Goodin, Jun 2026, updated Nov 2026)
- IndustrialSage, "Switchgear lead times 2026" (W. Garrett, 1 Sep 2026)
- Giga Energy, "Lead time delays for data centers" (R. Driver III, 13 Aug 2026)
- iRecruit.co, "How data center construction project managers manage equipment lead times" (D. Bond, 21 Jun 2026). Its generator figure (12–20 weeks) is an outlier. Keep it as dissenting evidence.
- NREL/TP-6A40-87653 (2024), "Major Drivers of Long-Term Distribution Transformer Demand": https://www.osti.gov/biblio/2309697. The PDF download failed, so it is cited for context only.

## Synthetic (made by us; labelled as such everywhere)
- `PROJECT_ALPHA.md`: the project, equipment schedule and need dates
- `bids/`: subcontractor proposals (to write)
- `schedules/`: project schedule CSV (to write)
