# Phase 1 clean-room test sources

The expected outcomes were committed in the isolated clone before each model run. These inputs were new to the project's evaluation, but were inspected to label the targeted expectations. They are therefore not blind to the reviewer. Public PDFs are kept under ignored `data/` paths and are not committed.

| Local input | Source |
| --- | --- |
| `data/submittals/judge_generator_800kw.pdf` | Caterpillar C32, 800 ekW prime, [technical spec sheet](https://emc.cat.com/n/api/pubdirect?media_string_id=TSS-DM9952-05-GS-EPG-13436233.pdf) |
| `data/submittals/judge_ups_500kva.pdf` | Vertiv Liebert APM Plus, [50-500 kVA user manual](https://www.vertiv.com/globalassets/products/critical-power/uninterruptible-power-supplies-ups/liebert-apm-plus-50-500-kva-ups-v1.4.pdf) |
| `data/submittals/judge_switchgear_abb.pdf` | ABB, [BuyLog Section 16, low-voltage switchgear](https://library.e.abb.com/public/248acbc0a0724fd29f351be845319f43/16_BuyLog_Switchgear-LV.pdf) |
| `data/specs/judge_UMB_product_excerpt.pdf` | Pages 4-5 extracted without editing from the [University of Maryland Baltimore Section 262300](https://umaryland.edu/media/umb/af/dc/documents/division-26/262300-Low-Voltage-Switchgear.pdf), which `tools/data_prep/fetch_data.py` downloads |
| `data/bids/judge_bid.txt` | Explicitly fictional fixture authored for this test; no supplier or price is represented as real |

The complete UMB specification has 131 parsed product clauses and was not run. The two-page excerpt has 26. The test compares the excerpt against the ABB catalog using the bundled `SWGR-A` schedule row, so the mismatch with Project Alpha is a test limitation.
