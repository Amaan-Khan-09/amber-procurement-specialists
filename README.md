# Amber procurement specialists

Kaya AI Grand Challenge, India Edition 2 · **Track 03: Vertical Agents** · Students division

Procurement specialists for a construction or data-center project (all eight on the challenge's list), exposed as **MCP tools** so Amber (or any
MCP client) can call them. They work on the critical-power package (generators, UPS, switchgear, transformers)
and share one data format, so one tool's output is the next tool's input.

| Tool | Question it answers | Output |
|---|---|---|
| `check_submittal` | Does the supplier's product submittal meet the spec? | one finding per spec requirement: `complies` / `deviates` / `missing` / `unclear`, citing the spec paragraph **and** the submittal page with exact quotes |
| `level_bids` | Which bid is really cheapest, and what does each one leave out? | scope matrix (included / excluded / qualified / silent / alternate), leveled totals, commercial risks, lead times, and an award only when it is safe |
| `assess_delivery_risk` | Which items will make us late? | P10 / P50 / P90 arrival dates, chance of missing the need date, latest order date, actions; **no model calls** |
| `run_package_review` | All of the above for one package | one comparison table per bidder: leveled cost, scope gaps, submittal verdict, arrival range |
| `find_products` | Which products could meet this spec (for example, to replace one that fails)? | candidates from the datasheets we hold, ranked likely fits / needs a closer look / does not fit, each key rating quoted from the datasheet; never a product from model memory, never an approval |
| `draft_follow_ups` | What do we send the vendors now? | submittal review comments, bid clarification requests and expediting requests, built only from verified quotes; **no model calls**, never sent automatically |
| `run_case` | Buy this equipment: where does the purchase stand, and who has to act? | a resumable case file: vendors found and pre-qualified, records linked, each supplier's bid and replies reconciled with its datasheet, cost and arrival ranges, every item routed (decided / ask the supplier / engineer), draft questions, award options with their blockers |
| `discover_vendors` | Who could supply it? | vendors from the vendor master ranked on audited points (product fit with datasheet quotes, manufacturer named by the spec, bid and lead time, service distance, on-time history); those that cannot supply it set aside with the record that says why |
| `prequalify_vendors` | May we buy from them? | meets / fails / needs verification for every criterion of the spec and the owner's policy, each with its quote; conflicting records and self-certifications flagged, never accepted |

A **web page for project managers** (`python -m amber.web`) runs the same specialists from a browser: see below.

## How it stays trustworthy

The judging criteria weigh trust heavily, so every rule below is enforced in code and covered by tests (`pytest`).

1. **The model reads; code decides.** The model extracts values and quotes. Comparisons, unit conversion (pint),
   totals, rankings and dates are computed in Python, so each verdict can be traced.
2. **No source, no claim.** A citation is kept only if its quote is found on the cited page of the source
   (exact, normalised, table-row or fuzzy; numbers must match exactly). A quote that is not found is dropped.
   The reported number must also appear *in its own quote*, and a number whose unit is not in the quote cannot be
   a confident claim (both rules came from real errors, see `tests/test_checks.py`).
3. **Confidence is built from evidence**, not asked of the model. Anything under 0.70 is handed to a person
   (`needs_human`), including anything read from a scanned page, any model judgement, and any case where the
   model's reading and the code's arithmetic disagree.
4. **kW and kVA are never mixed**; a datasheet that offers many options (voltages, heaters) passes only if the
   selected option is marked.
5. **Silence is double-checked.** "The bid does not mention X" is re-checked in code against the bid's own text.
6. **A failed model call is never a claim.** It degrades to "not checked" with zero confidence, never to "missing".
7. **Nothing is invented.** Products, vendors and lead times come only from documents under `data/`, each cited.
   There are no built-in answers: the agent works on documents it has never seen.

## One purchase, end to end: the case file (26 Nov 2026)

`python -m amber.case run` runs the generator purchase as a **case file** (`amber/case.py`): 13 steps, from finding
vendors to the award options, each saving its output and the memory the steps share (`runs/cases/GEN/state.json`,
`steps/`, `journal.jsonl`). A step whose inputs have not changed is reused, so a run stopped inside a step
(`--crash-at reconcile`) resumes there, and supplier replies that arrive later (`--replies`) flow back into the
answers, the pre-qualification and the leveled cost. The live demo shows it as one page: **`case.html`**
(built by `amber/case_page.py` from `examples/case_GEN/`). Scorecard against every criterion: `docs/SCORECARD.md`.

What it adds, with what a judge can check:

* **Who acts on each item.** "Handed to a person" was one queue. It is now three routes (`amber/triage.py`): decided by
  the agent; **a question to the supplier**, only when the document does not settle it *and* an independent reading of
  the whole document by a model of another family agrees; or **an engineer**, when the evidence needs judgement.
* **The supplier's own documents as evidence.** Each bid (and later each reply) is read against the same requirements
  as the datasheet (`scripts/read_commitments.py`) and reconciled **condition by condition**: a bid that commits to
  1800 rpm settles what the datasheet leaves blank; B2's bid commits to a **12-hour** tank where 24 h is required (a
  deviation the datasheet could not show); a UL 2085 tank listed under "Options (not included in total)" is not
  counted as supplied; records that disagree stay a conflict for the supplier to resolve.
* **Related sections.** Kohler's footnote "Enclosure with enclosed silencer reduces ambient temperature capability by
  5 °C (9 °F)" is linked to B3's "silencers inside": 122 °F − 9 °F = 113 °F, below the spec, laid out for an engineer.
* **Record linking with ambiguity.** B4 offers a "C2000D6": no document names it exactly; one sheet is the C2000D6**E**
  variant and B2's bid equates C2000D6 with model DQKAB, a different document. It is reported as ambiguous with both
  candidates, not silently picked (the earlier check called it a match). The bid form cites paragraph 2.1.K.1 for the
  annunciator, which in the spec is the fuel tank: reported as a wrong reference, not linked.
* **Vendor discovery and pre-qualification** (`amber/vendors.py`). Tidewater ranks first in discovery (best product
  fit, shortest lead time) and **does not pass pre-qualification** until its reply: insurance that expires before the
  need date, a manufacturer letter "available on request", and no named service branch where the vendor master says
  Norfolk, 190 miles away. The spec's own criteria (1.4.A acceptable manufacturers, 1.4.G ten years) are checked
  alongside the owner's policy. The vendor master, policy, packets and replies are **fictional**, like the bids.
* **Honest ranges.** Leveled cost as a range (allowances, items read as "qualified", clauses with no upper bound such as
  a metals surcharge); arrival P10/P50/P90 from weighted, cited reports with the dissenting source kept; assumptions
  and missing inputs listed.

### Hand-offs, measured before and after

A fixed set of **256 cases** that both versions handle (`eval/handoff_set/cases.json`, built from answer keys written
before this code): 184 datasheet requirements, 22 package-level requirements, 4 product links, 44 bid scope cells, 2
decisions. Categories: routine, missing information, conflicting records, should escalate. Same saved model readings;
**before** = the routing at commit 48b321c, **now** = this code (`python scripts/eval_handoffs.py`).

| | Before | Now |
|---|---|---|
| sent to an engineer | 148 (58 %) | **102 (40 %)** |
| sent to the supplier as a drafted question | 0 | 59 (23 %) |
| correct autonomous (acted alone, right action) | 105 | **150** |
| justified hand-off (needs judgement, or the agent was wrong) | 51 | 44 |
| unnecessary hand-off (agent right, no judgement needed) | 97 | **58** |
| incorrect autonomous | 3 | 4 |
| of which critical (accepts what fails or is not shown, rejects what complies) | 2 | **1** |
| right action overall | 210 (82 %) | 218 (85 %) |

By group: datasheet answers to an engineer **128 → 94 of 184 (70 % → 51 %)**; package level (bid + datasheet) right
action **15 → 21 of 22** and engineer hand-offs 13 → 6; product links 3 → 4 of 4 right (the critical wrong link is
gone). By category: missing information, unnecessary hand-offs 57 → 22; conflicting records, right action 5 → 11 of 12;
**should escalate: 17 of 17 still go to an engineer**. The extra incorrect autonomous answer is minor: bid cells our
saved reading calls "qualified" where the key says "included" now become a question to the supplier instead of an
engineer review. The remaining critical error is a saved bid reading (B2 S2 read as included; key: qualified), the same
in both versions. These documents were seen during development, so this is a repair record on a fixed set, not a
held-out score. The new pre-qualification specialist, scored separately (before: no specialist): 36 of 36 criteria
right, 33 decided or asked alone, 3 owner checks left to a person (**mock data**). After the two (mock) replies, the
case's own queue moves from 45 engineer items and 43 supplier questions to 40 and 27; the replies are read 17 of 18
right against their key (the miss, a claim of full rating "with the 50 C cooling package" that the same reply leaves
unconfirmed, went to an engineer, not through).

## Quick start

```bash
python -m venv .venv                                     # Python 3.11+
source .venv/bin/activate                                # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python tools/data_prep/fetch_data.py                     # downloads the public test documents (not committed)
python -m pytest -q                                      # 147 tests, no API key and no network needed
python -m amber.web                                      # the web page: http://127.0.0.1:8000 (opens the browser)
python scripts/demo_mcp_client.py                        # starts the MCP server and calls a tool (no key needed)
cp .env.example .env                                     # add GROQ_API_KEY for the steps below
python scripts/run_package.py                            # full package review on Project Alpha
python scripts/make_report.py runs/package_GEN.json      # the same result as an HTML page
python -m amber.server                                   # MCP server on stdio (--http for streamable HTTP)
```

Notes for a fresh clone:

* **Live demo, nothing to install (read-only):** https://amaan-khan-09.github.io/amber-procurement-specialists/demo/
  It is a static copy of the web page (`docs/demo/`) that runs on the saved results: overview, the 3D view, every
  source, the review queue (your decisions stay in your browser) and the Proof tab. Our own documents open as page
  images with the quoted words highlighted. Manufacturers' datasheets are copyrighted, so the demo never republishes
  them: it shows the short excerpt the agent cited and links to the manufacturer's page. Rebuild it with
  `python scripts/build_static_demo.py` (publish: GitHub Pages, branch `main`, folder `/docs`).
* **No API key needed to see the results.** `examples/` holds the saved results behind every number in this README
  (the package review, product discovery, every scored case). `python -m amber.web` lists them under Saved results,
  and the Overview, delivery forecast and source viewer work with no key at all.

* One public file (the Kohler KD1000 submittal, case G3) is on a site that refuses automated downloads; the fetch
  script prints its link and the exact path to save it under after downloading it in a browser.
* Scanned pages are read from a local cache that is not in the repository (it is derived from copyrighted documents).
  On a fresh clone they are reported as unread and sent to a person, unless you set `AMBER_OCR=gemini` (about $0.41 to
  read all 87 scanned test pages once).
* The structured requirements for the three Project Alpha specs are committed (`data/requirements/`), so no model is
  needed to re-derive them.

### The web page

`python -m amber.web` starts a local page at http://127.0.0.1:8000 for a project manager who does not use an MCP client:

* **Package review, Check a submittal, Find products, Level bids, Delivery risk:** choose documents from `data/` or upload a PDF
  (or a bid e-mail as .txt), choose the model, run. Progress shows the model calls as they happen.
* **Overview:** the project at a glance: a 3D view of the site's power equipment (transformers, switchgear, UPS,
  generators) coloured by each group's chance of arriving late, with the dates and sources one hover or click away,
  and the hand-off chain between the specialists. The 3D view turns a full 360° by itself (drag to turn it by hand,
  hover a block to pause it). No model calls.
* **Every answer shows its sources, one click away:** "View on the page" opens the original PDF page with the quoted
  words highlighted (all 376 citations in our saved runs are located on their page), a bid e-mail with the quote
  marked, or a lead-time record with its publisher, date and a link to the website. Any cited page has a shareable
  link.
* **Review mode:** "Review N items one by one" walks through everything the agent handed to a person, one item at a
  time, with the spec and datasheet quotes in front of you. Keys: `A` agrees, `1`-`4` set the verdict, arrows move
  between items. This is what makes a cautious agent quick to work with.
* **Proof tab:** the evaluation scored from the saved runs against the answer keys by the same scorer as the command
  line (`scripts/build_proof.py` refreshes the stored score; the page recomputes it when a run or a key changes).
* **Side by side:** any requirement can open the spec page and the supplier's page next to each other, both quotes
  highlighted.
* **Checks learned from how procurement teams work:** scope that no bid includes is flagged (and every bidder is
  asked to price it), and the package review checks in code that each submittal is for the product that was bid,
  so a substitution cannot slip through.
* **"For you to review"** lists only what the agent handed to a person. For each item you can agree, or change the
  verdict, and add a note. Decisions are saved beside the result (`runs/web/reviews/`).
* **Vendor follow-ups** are drafted from the gaps: copy or download them, then send them yourself.
* **Saved results:** every run (from the page or the command line) opens again without spending tokens. Running the
  same documents twice opens the saved result unless you choose "Run again".

It binds to 127.0.0.1 only. API keys stay in `.env`: the page is told only whether a provider is set up, never a
key, and the paid model is not offered there. Held-out test documents whose one scored run has not happened yet are
hidden from the page, so the accuracy figures below stay honest.

MCP client config (e.g. Claude Desktop or Amber):

```json
{"mcpServers": {"amber": {"command": "python", "args": ["-m", "amber.server"], "cwd": "/path/to/amber-procure"}}}
```

File arguments are paths under `data/`; paths outside it are refused.

## Models, cost and time

| Use | Model | Provider |
|---|---|---|
| Reading specs, submittals and bids (default) | `openai/gpt-oss-120b` (reasoning effort low) | Groq |
| Lighter runs and development | `openai/gpt-oss-20b` | Groq |
| Same model when Groq is out of capacity (optional, free tiers, only if a key is set) | `gpt-oss-120b` on each host | OpenRouter, then Cerebras, then NVIDIA (build.nvidia.com), then Hugging Face Inference Providers |
| Reading **scanned** pages (OCR): only when `AMBER_OCR=gemini`; cached per page and reused by default | `gemini-3.8-flash` | Google |
| Structuring a spec into requirements (once per spec, cached) | `gemini-3.8-flash` | Google |
| Private / offline mode | `qwen3:8b` served by Ollama on a laptop's integrated GPU (measured below) | local |
| Delivery forecast | none (pure code) | local |

Measured on Project Alpha (cost is estimated at list prices from token counts; every run reports its own models, tokens,
cost and latency in the `run` field of the result):

| Run | Tokens (in / out) | Cost | Time |
|---|---|---|---|
| `check_submittal`, 21 requirements, 120b | 24k / 8k | about $0.008 | 3.5 min on Groq's free tier (rate-limit waits dominate) |
| `check_submittal`, same, 20b | 30k / 7k | about $0.005 | 4 min on the free tier |
| `level_bids`, 4 bids | 30k / 8k | about $0.005 | 1 min |
| `assess_delivery_risk` | none | $0 | under 1 s |
| OCR of 87 scanned pages (one time, then cached) | | $0.41 | 17 min |

Times are on free API tiers, which allow 8,000 tokens per minute; a paid tier is several times faster.
### Private (offline) mode: what we measured

`AMBER_PROVIDER=ollama python -m amber.server` runs everything locally: no document, prompt or answer
leaves the machine, and a scanned page is never sent to a vision model. Structuring a spec into typed requirements is
done once per spec and cached (`data/requirements/`, built with `scripts/build_requirements.py`), so the local model
only has to read each submittal.

Measured on our own laptop: Intel Core i5-1334U, 16 GB RAM, **integrated Intel Iris Xe graphics only**, Ollama with
the Vulkan backend (`OLLAMA_VULKAN=1`, `OLLAMA_IGPU_ENABLE=1`). Full check of dev case G2, 21 requirements:

| Setup | Time | Correct | Sent to a person | False approvals | Fabricated citations |
|---|---|---|---|---|---|
| First attempt: `qwen3:4b` on the CPU, 16k context (the laptop was swapping) | ~5 h | 38 % | 19 % | 1 | 0 |
| `qwen3:4b` on the Iris Xe GPU, 4k context, small schema-constrained prompts | 14.5 min | 57 % | 67 % | 1 | 0 |
| **`qwen3:8b` on the Iris Xe GPU (default)** | **20 min** | **67 %** | 43 % | 1 | 0 |

Cost is $0. What made it practical: a 4k context window (a 16k one alone needed ~2.4 GB and pushed the laptop into
swapping), at most three conditions and ~3,500 characters of excerpts per call, JSON-schema-constrained decoding, and
the integrated GPU. The remaining false approval is the radiator-footnote case listed under known limits; it is the
same one the cloud models miss. A workstation GPU would be several times faster; we have not tested one.

Spend on the paid API is capped by a persistent ledger (`AMBER_GEMINI_BUDGET_USD`, default $1.50) and a Groq outage
never silently switches to a paid provider (`AMBER_FALLBACK=gemini` opts in).

**Scanned pages.** By default OCR is *cache-only*: scan text read earlier is reused, and a new scanned page is never
sent anywhere; it is reported as unread and goes to a person. Set `AMBER_OCR=gemini` (or `groq` / `ollama`) to read new
scans, or `AMBER_OCR=off` to ignore scans entirely. We tested OCR on the laptop's GPU (`qwen3-vl:4b`): it writes at
5.4 tokens/s, about 6 minutes per dense datasheet page, and the variant we tried spent its output on hidden reasoning
and returned nothing, so we do not offer local OCR. Gemini read all 87 scanned test pages once, for $0.41, and read the
two drawings we checked by eye exactly (`python scripts/bench_ocr.py --provider gemini --cached-only`).

## Evaluation

Answer keys (`eval/answer_keys/`) were written from the source PDFs by the project author with AI assistance,
**before** the agent was run on that case. Each label has the page and the exact quote; every quote was re-checked
against its page. They have had a blind cross-check by a model of another family (it agrees with them on 100 of 142 cells, 70 %, kappa 0.57, see below) and are waiting for a human reviewer. How to read them: `eval/answer_keys/README.md`.

| Case | Document | Split | Labels |
|---|---|---|---|
| G1 | Cummins 2000 kW package, 66 pages (6 scanned) | dev | 15 complies · 2 deviates · 2 missing · 2 unclear |
| G2 | Kohler KD2000 spec sheet, 6 pages | dev | 12 · 2 · 1 · 6 |
| G3 | Kohler KD1000 project submittal, 105 pages (46 scanned) | **held out** | 14 · 2 · 0 · 5 |
| G4 | Cummins C1000 family spec sheet, 4 pages | **held out** | 8 · 1 · 5 · 7 |
| U1 | Vertiv UPS package: India brochure + US site-planning sheet, 17 pages, against a UPS spec | **held out** (new equipment class) | 9 · 2 · 1 · 4 |
| G5 | mtu 16V4000 DS2250 datasheet | **held out, set 2** (labelled after the set 1 fixes) | 11 · 1 · 6 · 3 |
| G6 | Kohler 2000ROZD-4 spec sheet | **held out, set 2** | 11 · 2 · 2 · 6 |
| G7 | Caterpillar 3516C 2000 ekW spec sheet (the product bidder B1 offered), 4 pages | **held out, set 3**: labelled 24 Nov 2026, after the accuracy fixes, **before any run**; run once | 3 · 0 · 7 · 11 |
| G8 | Cummins C2000D6E specification sheet and data sheet (the family of bidder B4's product), 7 pages | **held out, set 3**: same | 12 · 1 · 2 · 6 |
| BL1 | four generator bids (3 PDF + 1 email) | dev | 44 scope cells, leveled totals, award decision |

Latest development results (small `gpt-oss-20b` model, free tier): G1 67–71 %, G2 57 % correct; **0 fabricated citations**
in every run. Run-to-run variation on that model is several points. `level_bids` on BL1: 41 of 44 scope cells correct, all four base
prices and all four products right, ranking correct, award correctly withheld. Two of the four leveled totals are exact;
the other two are off by $30,000 and $122,000 because of three misread scope cells (B2 S2, B1 S8, B2 S8). A second reading of
the same bids, inside the full package review, scored **39 of 44** cells with the same base prices, 1 of 4 leveled totals exact,
and B3 and B4 swapped in the ranking because their leveled totals are within 0.4 % of each other. Three of the five cells
that differ from our key are in the S8 row, which the key itself marks as ambiguous; the other two are the model reading
"4 steps per 3.6" and "walk-in enclosure" strictly. The award was withheld both times. The Proof tab shows both readings.
All five differing cells are "qualified" readings. Since 26 Nov every "qualified" reading goes to a person, and the award
says when the price order depends on them (in the saved package review: B3 is $18,000 above B4, with $185,000 of B3's
total resting on such readings).
### Held-out results (run once, 22 Nov 2026, `gpt-oss-120b`, no tuning)

The held-out cases were labelled before any agent run and run exactly once (`--final`; the scorer refuses otherwise).
No call failed, so every finding is a real answer.

| Case | Correct | False approvals | False rejections | Fabricated citations | Sent to a person | Cost | Time |
|---|---|---|---|---|---|---|---|
| G4 Cummins C1000 spec sheet | 15 / 21 (71 %) | 0 | 1 | 0 | 29 % | $0.006 | 2.7 min |
| U1 Vertiv UPS package (new equipment class) | 8 / 16 (50 %) | 2 | 0 | 0 | 56 % | $0.005 | 2.2 min |
| G3 Kohler 105-page project submittal | 11 / 21 (52 %) | 0 | 0 | 0 | 48 % | $0.008 | 4.2 min |
| **All held-out** | **34 / 58 (59 %)** | **2** | **1** | **0** | | **$0.02** | |

What this means, plainly: most errors are cautious ones (an answer sent to a person as `unclear` instead of a firm
verdict), there were **no fabricated citations**, and there were two false approvals, both on the UPS case:

* U02 "full rating at 40 °C": approved from the operating range "0-40 °C", missing a separate row that derates the unit
  to 1080 kW at 40 °C. This was a capped model judgement, so it was already **sent to a person**, not auto-approved.
* U10 "maintenance bypass furnished": approved at high confidence because the quote contains the required words
  ("Manual Maintenance Bypass Included 300-500 kW"), although the same row says "Not included 600-1200 kW". **This is
  the one automatic false approval in 58 held-out requirements.**

After this run we added a guard: a check cannot pass while its own evidence says "not included", "excluded", "by
others" or "optional" (`tests/test_checks.py::test_required_words_next_to_a_negation_do_not_pass`). The held-out
numbers above are from **before** that fix and were not re-run, because re-running after a fix would no longer be a
held-out measurement.

### Held-out set 2: after the fixes (run once, 24 Nov 2026, `gpt-oss-120b`, no tuning)

To measure the fixes honestly we needed documents the agent had never seen. Two more public generator datasheets were
labelled on 23 Nov, **after** the fixes and **before** any agent run, then run exactly once.

| Case | Correct | False approvals | False rejections | Fabricated citations | Sent to a person | Decided alone, and right | Cost | Time |
|---|---|---|---|---|---|---|---|---|
| G5 mtu 16V4000 DS2250 datasheet | 13 / 21 (62 %) | 0 | 0 | 0 | 71 % | 6 / 6 | $0.006 | 2.9 min |
| G6 Kohler 2000ROZD-4 spec sheet | 15 / 21 (71 %) | 1 (sent to a person) | 0 | 0 | 76 % | 5 / 5 | $0.007 | 3.5 min |
| **Set 2** | **28 / 42 (67 %)** | **0 automatic** | **0** | **0** | | **11 / 11** | **$0.013** | |

Plainly: accuracy on unseen documents went from 59 % to 67 %, and **every answer the agent gave on its own was right
(11 of 11)**. The price is caution: about three answers in four go to a person, mostly as `unclear` where the label is
`missing` (the agent found related words but no value, and asks rather than guesses). The one false approval (G6 R09,
radiator rated for 122 °F) was a capped model judgement and was **sent to a person**, not auto-approved.

### Accuracy work after set 2 (24 Nov 2026): what we tried, what helped, what did not

`python scripts/replay_decisions.py` re-runs the code's decision stage (quote check, comparison, guards, hand-off) over every
saved run **without a model**, so a change can be measured on all 142 labelled requirements in 8 seconds and every verdict
it changes is listed with whether the change is right. The model only reads; everything after is code, so this is faithful
(it reproduces the saved verdicts exactly on G1, G2, G5 and G6).

| Change | Effect on the replay | Kept? |
|---|---|---|
| Numbers: `1590--2000` was read as 1590 and -2000; the decimal comma `0,50` as 50; qualifiers such as "up to 8 units" were treated as a label | +2 correct | yes |
| A quote the model shortened with "..." is accepted only if every piece is on the page, in order | no change on saved runs | yes (tests) |
| A text requirement with only some of its words in the evidence is "unclear", never an automatic "deviates" | removes the only wrong automatic verdict | yes |
| Require related words to occur together before a document counts as "mentioning" a requirement | +6 true "missing", but 6 new wrong automatic "missing" (datasheets that list the feature only as an option) | **no, reverted** |
| Re-read, with the model, the best passages for conditions the document mentions but the model gave up on | found nothing on two development datasheets, +12 % tokens | **off by default** (`AMBER_TARGETED_READ=on`) |
| Treat `anti-condensation` and `anti- condensation` as the same word | no verdict moved | **no, reverted** |

Net on the replay: **99 / 142 correct (70 %), 0 false rejections (was 1), and all 42 automatic answers right (was 40 of 41)**.
Be careful with these numbers: the same document re-run through the model varies by about three requirements (G1 scored 14
and then 17 of 21 on identical code), so a one-point change in a single run is noise. Only the labels that moved in the
replay, where the model's reading is held fixed, are attributable to a change. **Held-out set 3** (G7 Caterpillar 3516C,
G8 Cummins C2000D6E) was labelled on 24 Nov 2026 before any run, specifically to test these changes on documents nobody had
seen; it was then run once, with no tuning afterwards (below).

### Held-out set 3: fresh documents, after the accuracy fixes (run once, 25 Nov 2026, `gpt-oss-120b`, no tuning)

Two datasheets nobody had seen, labelled from their source text on 24 Nov before any run (the commit history shows the
order), run once. No model call failed, no provider was switched, and the code was not touched between the labelling and
the run.

| Case | Correct | False approvals | False rejections | Fabricated citations | Sent to a person | Decided alone, and right | Cost | Time |
|---|---|---|---|---|---|---|---|---|
| G7 Caterpillar 3516C 2000 ekW spec sheet | 17 / 21 (81 %) | 0 | 0 | 0 | 62 % | 7 / 8 | $0.008 | 3.7 min |
| G8 Cummins C2000D6E spec and data sheet | 15 / 21 (71 %) | 0 | 0 | 0 | 67 % | 7 / 7 | $0.006 | 2.6 min |
| **Set 3** | **32 / 42 (76 %)** | **0** | **0** | **0** | | **14 / 15** | **$0.014** | |

Accuracy on unseen documents has gone 59 % (set 1) to 67 % (set 2) to **76 % (set 3)**, with zero invented citations and no
false approvals in the last two sets that were not handed to a person. Read it with the noise in mind (a document varies by
about three requirements between identical runs): the direction is clear, a single point is not.

The one automatic answer that disagrees with our key is G7 R11 (ambient and altitude): the agent said "not stated" (a
request to the vendor), our key says "unclear" because the sheet says cooling systems are *available* for 50 C. It errs in
the safe direction, and we did not change the code to fix it, because that would break the rule that makes the 76 % mean
something. The other 9 wrong answers were all handed to a person: six were "unclear" where the key says "missing" or
"complies" (the agent saw related words, or only some of the required words, and asked), and three were the model's own
judgement or a partial reading, capped for review.

Score any case with `python scripts/eval_submittal.py --run --case G3`.

### Product discovery (24 Nov 2026, `gpt-oss-120b`)

`python scripts/run_discovery.py GEN-A` screened the 10 datasheets in the library for the 2000 kW generator: the 3 UPS
documents were set aside in code as other equipment, and the 7 generator datasheets were screened on 5 key ratings
(19 model calls, $0.014, 7 minutes, cached afterwards). One **likely fits** (the Cummins DQKAB, which also passed its
full check with no deviation), two **do not fit** (a 1000 kW unit and a shop drawing set of a different rating and
voltage, both shown failing the rating with quotes), and four **need a closer look**, each naming the rating the
datasheet does not show clearly. No product outside the library was named.

### Faults found by auditing the saved package review (26 Nov 2026)

We read every answer the saved package review gave on its own against the answer keys. Two things were wrong.

* **A false rejection.** B3 was rejected for motor starting "1110 kVA". The 1110 is the battery's cold-cranking amps: the
  datasheet has two columns, the page text is read line by line across both, and the model joined the motor-starting label
  to the number beside it with "...". The real figure is 9,957 kVA. Now a rejection may not rest on words that are not one
  run of text in the PDF's own order, and a quote shortened with "..." never passes on its own
  (`tests/test_accuracy.py::test_a_number_borrowed_from_the_next_column_cannot_reject_a_product`). On the replay of all 184
  labelled requirements this changes no verdict.
* **Over-confident bid readings**: the five "qualified" cells above, now handed to a person.

The saved package review and bid comparison were decided again from **the same model readings**, with no new model call
(each says so inside the file), so nothing was re-rolled. The result is less dramatic and more honest: B3 is now "review",
not "reject". Our key says its fuel tank deviates (UL 142 where UL 2085 is required); the agent did not catch that on this
reading and neither did the independent reader. It is in the person's queue, as `unclear`, with the datasheet page.

### A second round: where answers get lost (26 Nov 2026)

We traced all 53 wrong answers on the saved runs, rebuilding what the model was shown (no model call needed):

| Where it went wrong | Answers |
|---|---|
| the key says `missing`; we answered `unclear` because related words occur (cautious by design) | 16 |
| the evidence was shown, the model quoted something else | 14 |
| the evidence was **not in the passages shown** to the model | 9 |
| the right words were quoted; the rules decided differently | 9 |
| the evidence was shown, the model reported nothing | 5 |

Four rules came out of it. On the replay of all 184 requirements (same model readings) they move **131 to 133 correct, and
every answer decided alone, 56 of 56, matches the key** (before: 56 of 57). These documents had been seen, so this is a
repair record, not an accuracy measurement.

* A passage that was quoted but holds no comparable value is `unclear`, never `missing`. This was the one wrong automatic
  answer on held-out set 3 (G7 R11); the table above for that set still shows the run as it happened.
* An item behind an empty tick box, or on a list of available choices, cannot `comply` on its own.
* "EPA" with no Tier no longer satisfies the emissions requirement, and a 120 V single-phase item must be a *heater*.
* Account identifiers and keys are removed from provider error messages before they are stored in a result.

Still true: the requirement "24 V, 2-wire, negative ground, gear-engaging starter" is judged on the 24 V starter only.

**Layout-aware reading (experimental, off by default: `AMBER_READING=layout`).** For datasheets up to 24 pages the model
is given whole pages with the columns kept apart, table rows kept together and tick boxes visible, and the second look
starts with the pages not yet read. One live run on a development datasheet (G2) scored 18 of 21 with 7 of 7 automatic
answers right (earlier runs of that sheet with the plain reading: 17 and 15). One run proves nothing: it stays off until
it has been compared with the plain reading on datasheets neither has seen.

## What goes to a person, and the independent reader

About two answers in three go to a person (64 % on the newest set as it ran, 70 % over all 184 labelled requirements with today's rules). Two facts put
that in proportion. First, **27 % of the requirements are genuinely unclear in the datasheet** (our keys mark 50 of 184 as
`unclear`: an option listed but not marked as supplied, a claim without numbers), so only the supplier can answer them: any
honest system hands those over. Second, what is inside the rest (`python scripts/handoff_breakdown.py`, current code, all labelled
answers):

| What the answer is | Answers | Right |
|---|---|---|
| decided by the agent alone | 56 | 56 (100 %) |
| unclear: related words found, but no value | 63 | 34 (54 %) |
| complies: the model's judgement of a verified quote | 33 | 25 (76 %) |
| number found, its unit not printed beside it | 8 | 8 (100 %) |
| other hand-offs (a quote without a comparable value, a reported value not in its own quote, only some required words found, model and code disagree) | 24 | 10 (42 %) |

The "judgement" answers are right three times in four, so they are not "just glance": one in four is a derating footnote or an
unmarked option that needs a person.

**The independent reader.** A model of another family (Qwen 3.8 27B) reads each whole datasheet **blind** (it never sees our answers
or our keys) and answers every requirement; the result is shown next to each answer on the page, and answers it contradicts are
filtered as "contested" and put first in the review queue. It never changes a verdict. On 142 labelled requirements from 7
datasheets (`python scripts/analyze_agreement.py`):

| Our pipeline's answer | Independent reader | Answers | Pipeline right |
|---|---|---|---|
| decided by the agent alone | agrees | 34 | 34 (100 %) |
| handed to a person | **agrees** | 50 | **42 (84 %)** |
| handed to a person | **disagrees** | 50 | **20 (40 %)** |

So a contested answer is far more likely to be wrong, and that is what the queue order uses. Agreement is not strong enough to approve
anything on its own (84 % is well short of the answers the agent decides alone), so everything it does not settle still goes to a
person. Two negative results, kept because they shape the design: (1) a cheaper second opinion that only sees the *quoted evidence*
did **not** work (agreement 14 right of 20, disagreement 20 of 24: the second model shares the first one's blind spots, such as a
derating footnote or an unmarked option elsewhere in the sheet), so it is not used; (2) where the pipeline says "unclear" and the reader
gives a concrete verdict (complies or deviates) the reader is right only 7 of 23 times, so it never overrules (when it says "missing" it
is right 13 of 15). These figures are the saved readings decided with today's rules, as on the Proof tab. The reader costs about 8,000 to 18,000 tokens a datasheet on its own free allowance and reads one page-chunk a
minute on a free tier, so it is run for datasheets of up to 20 pages (`scripts/cross_check_keys.py`); the 66- and 105-page packages are
not cross-read.

## Data

Everything is public or made by us, and cited in `data/SOURCES.md`.

* **Project Alpha** is a fictional 6 MW data hall (owner, site, dates, equipment schedule): `data/PROJECT_ALPHA.md`.
* **Specs**: the project's generator spec is a public university master spec edited by a script
  (`tools/data_prep/make_alpha_genset_spec.py`, every choice listed); US federal guide specs for other equipment.
* **Submittals**: real public Cummins, Kohler and Vertiv documents, downloaded by `fetch_data.py`; not committed.
* **Bids** are **synthetic** (fictional companies, real public product models, planted scope gaps), made by
  `tools/data_prep/make_bids.py`; every page says so.
* **Lead times** come from four cited 2026 market reports (`data/leadtime_sources/leadtime_evidence.csv`, with
  quote, date and basis for every figure). The reports disagree, so the forecast is a weighted range, and an
  outlier source is kept and shown as dissent.

## Known limits (honest list)

* **Cross-requirement reasoning.** If a footnote on a radiator rating says an enclosed silencer cuts it by 5 °C and the
  spec separately requires an enclosure, a single requirement check can miss it (seen in G2 R09).
* **A real quote can be the wrong row.** On held-out G5 the fuel-consumption verdict matches our key (deviates), but the
  quote is the *total fuel flow* row (317 gal/hr) instead of consumption (162 gal/hr). "Zero invented citations" means every
  quote is on its page; it does not mean every quote is the best evidence. Two-column pages are the usual cause, and the new
  guard only covers rejections and shortened quotes.
* **Scanned pages** are read by a vision model. It once misread a model number, so anything resting on a scan is
  always sent to a person with the page to confirm.
* **Small models** miss facts that are stated; the 120b model is the supported default.
* Bids and the project are fictional; lead-time sources are trade publications, some secondary.
* **Cautious by design, so a person still has work to do.** On unseen documents about three answers in four go to a
  person, mostly as `unclear` where a careful reader would say `missing`. On held-out sets 2 and 3 (after our fixes)
  25 of the 26 answers the agent gave on its own matched our key, and the one that did not asked the vendor for information;
  the time saved is in reading and quoting, not in removing the review.
* **The answer keys are not yet reviewed by an independent human.** A blind model labelled 142 of the 184 requirements and disagrees with
  the keys on 42; those 42 cells plus 12 random agreed ones are a checklist for a person (`eval/cross_checks/REVIEW.md`,
  `human_review.csv`), and `scripts/apply_human_review.py` reports the result without changing any label, showing the accuracy under
  both the keys as written and the person's labels. That review is pending.
* Answer keys cover generators (six datasheets) and one UPS package. Switchgear and transformers have specs and
  delivery forecasts, but no submittal answer keys yet, and product discovery is set up for generators and UPS only.
* Product discovery screens five key ratings; a product that passes still needs the full submittal check.
* The web page is a local, single-user tool (it binds to 127.0.0.1); it is not a hosted multi-user service.
