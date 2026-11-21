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
python -m venv .venv && .venv/Scripts/activate          # Python 3.11+
pip install -e ".[dev]"
python tools/data_prep/fetch_data.py                     # downloads the public test documents (not committed)
cp .env.example .env                                     # then add GROQ_API_KEY (and optionally GEMINI_API_KEY)
python -m pytest -q                                      # unit tests, no network needed
python scripts/run_package.py                            # full package review on Project Alpha
python -m amber.server                                   # MCP server on stdio (--http for streamable HTTP)
```

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
| Reading **scanned** pages (OCR), cached per page | `gemini-3.8-flash` | Google |
| Private / offline mode | a small open-weight model served by Ollama (see below) | local |
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
Spend on the paid API is capped by a persistent ledger (`AMBER_GEMINI_BUDGET_USD`, default $1.50) and a Groq outage
never silently switches to a paid provider (`AMBER_FALLBACK=gemini` opts in). Set `AMBER_OCR=off` to never send a
scanned page to a vision model.

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
| BL1 | four generator bids (3 PDF + 1 email) | dev | 44 scope cells, leveled totals, award decision |

Latest development results (small `gpt-oss-20b` model, free tier): G1 67–71 %, G2 57 % correct; **0 fabricated citations**
in every run. Run-to-run variation on that model is several points. `level_bids` on BL1: 41 of 44 scope cells correct, all four base
prices and all four products right, ranking correct, award correctly withheld.
**Held-out results (G3, G4) are not in yet**: they will be run once, on the 120b model, with no tuning, and reported here.

Score any case with `python scripts/eval_submittal.py --run --case G3`.

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
* Only generator submittals have answer keys so far; UPS and switchgear specs are in progress.
