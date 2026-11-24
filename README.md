# Amber procurement specialists

Kaya AI Grand Challenge, India Edition 2 · **Track 03: Vertical Agents** · Students division

Three procurement specialists for a construction or data-center project, exposed as **MCP tools** so Amber (or any
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

## Quick start

```bash
python -m venv .venv                                     # Python 3.11+
source .venv/bin/activate                                # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python tools/data_prep/fetch_data.py                     # downloads the public test documents (not committed)
python -m pytest -q                                      # 109 tests, no API key and no network needed
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
against its page. They have not yet had an independent review. How to read them: `eval/answer_keys/README.md`.

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
the other two are off by $30,000 and $122,000 because of three misread scope cells (B2 S2, B1 S8, B2 S8). The Proof tab shows this live.
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

Score any case with `python scripts/eval_submittal.py --run --case G3`.

### Product discovery (24 Nov 2026, `gpt-oss-120b`)

`python scripts/run_discovery.py GEN-A` screened the 10 datasheets in the library for the 2000 kW generator: the 3 UPS
documents were set aside in code as other equipment, and the 7 generator datasheets were screened on 5 key ratings
(19 model calls, $0.014, 7 minutes, cached afterwards). One **likely fits** (the Cummins DQKAB, which also passed its
full check with no deviation), two **do not fit** (a 1000 kW unit and a shop drawing set of a different rating and
voltage, both shown failing the rating with quotes), and four **need a closer look**, each naming the rating the
datasheet does not show clearly. No product outside the library was named.

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
* **Scanned pages** are read by a vision model. It once misread a model number, so anything resting on a scan is
  always sent to a person with the page to confirm.
* **Small models** miss facts that are stated; the 120b model is the supported default.
* Bids and the project are fictional; lead-time sources are trade publications, some secondary.
* **Cautious by design, so a person still has work to do.** On unseen documents about three answers in four go to a
  person, mostly as `unclear` where a careful reader would say `missing`. Every answer the agent gave on its own was
  right (11 of 11 on held-out set 2), but the time saved is in reading and quoting, not in removing the review.
* Answer keys cover generators (six datasheets) and one UPS package. Switchgear and transformers have specs and
  delivery forecasts, but no submittal answer keys yet, and product discovery is set up for generators and UPS only.
* Product discovery screens five key ratings; a product that passes still needs the full submittal check.
* The web page is a local, single-user tool (it binds to 127.0.0.1); it is not a hosted multi-user service.
