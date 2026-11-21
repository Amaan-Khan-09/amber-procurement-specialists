# Amber Procurement Specialists — Design

Kaya AI Grand Challenge (Edition 2), **Track 03: Vertical Agents**, Students division.
Round 1 (build) runs 9 Nov – **6 Dec 2026**. Top 10 announced 12 Dec; live finale in Mumbai 17 Dec. Working name; rename before submitting.
Rules that shape the design: original work made during the hackathon; any model allowed but **name it and report cost per run**; public data must be cited; fabricated sources, vendors, products or model numbers are heavily penalised; **no working repo + demo video = ineligible**.

## 1. The problem we pick

A data-center contractor is buying the **critical power package**: generator sets, low-voltage switchgear, UPS, and pad-mount transformers. These are the items that decide whether the building energises on time. Three jobs eat the procurement team's week:

1. **Is what the supplier sent what we specified?** Supplier datasheets (submittals) are checked against the spec line by line, by hand. Misses cause rework.
2. **Which bid is actually cheapest?** The bids cover different scopes. Exclusions hide in the fine print ("startup by others", "freight FOB factory").
3. **Which item will make us late?** Lead times for this equipment run from 30 weeks to over 2 years, and the warning signs are spread across the schedule and the purchase orders.

We build three specialists for these jobs. They work as one product: each one's output feeds the next.

## 2. The specialists

| Tool (MCP) | Input | Output |
|---|---|---|
| `check_submittal` | spec section (PDF) + submittal (PDF datasheet) | one verdict per spec requirement: `complies` / `deviates` / `missing` / `unclear`, citing **both** documents (page + paragraph / line + exact quote) |
| `level_bids` | package scope + 2–5 bids (PDF/DOCX/email text) | scope matrix (item × bidder: included / excluded / qualified / silent), cost adjustments for scope gaps, award recommendation with reasons |
| `assess_delivery_risk` | schedule (CSV/XLSX) + POs / vendor quotes + optional outputs of the two above | per item: delivery range (P10 / P50 / P90 weeks) with cited drivers, float left, risk rank, suggested action |

**How they combine (the "more than the sum" part):**
- A `deviates` result on the submittal check means a resubmittal. `assess_delivery_risk` adds the resubmittal cycle to that item's range.
- `level_bids` uses the submittal check. A cheap bid that offers a non-compliant product is flagged as "not like for like".
- `run_package_review` is a fourth tool that runs all three on one package and returns a single combined report.

**Stretch goals, only if days 1–5 are on time:**
- `prequalify_vendor`: checks public records such as the SAM.gov exclusions list, with sources.
- `find_equivalents`: only from datasheets we have actually read, never from model memory.

## 3. Shared data format (every tool, in and out)

```jsonc
{
  "tool": "check_submittal",
  "version": "1.0",
  "result": { ... },                 // tool-specific, typed (Pydantic)
  "findings": [{
    "id": "F-012",
    "claim": "Generator rated 2000 kW standby; spec requires >= 2000 kW",
    "status": "complies",
    "confidence": 0.93,
    "citations": [
      {"doc_id": "spec-263215", "page": 41, "locator": "2.3.1.a", "quote": "..."},
      {"doc_id": "sub-cat-3516", "page": 2, "locator": "Ratings table, row 3", "quote": "..."}
    ],
    "needs_human": false,
    "why": "Numeric check in code: 2000 kW >= 2000 kW"
  }],
  "needs_human": [{"finding_id": "F-019", "reason": "Spec value is a range the datasheet does not state"}],
  "run": {"models": [{"name": "...", "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0}], "latency_ms": 0}
}
```

All tools use the same `Citation`, `Finding` and `Item` types. That way one tool's output feeds the next without glue code.

## 4. How we keep it trustworthy (the judges' main criterion)

1. **The LLM reads the documents. Code makes the decisions.** The model extracts requirements and offered values as typed records: attribute, operator, value, unit, and the exact quote. Comparisons, unit conversions (pint), totals and dates are done in Python, so every verdict can be traced.
2. **Every quote is checked.** A citation is kept only if its quote is actually found on the cited page of the source text, after whitespace and case are normalised. A quote that isn't found is dropped, and the finding becomes `unclear` and goes to a person. **No source means no claim.**
3. **Confidence is built from evidence, not asked of the model.** It combines whether the quote was verified, whether the unit parsed, whether the comparison was exact or fuzzy, and whether two extraction passes agree. Below 0.7 the finding goes to a person.
4. **No built-in answers.** No document-specific rules exist anywhere in the code. We tune on a dev set, and the accuracy we report is on a held-out set we never tuned on.
5. **Only real products and vendors.** Every product, vendor and lead-time figure comes from a document in `data/` with its source. The synthetic data is labelled as synthetic.

## 5. Data (all public or self-made, all cited in `data/SOURCES.md`)

| Kind | Source | Use |
|---|---|---|
| Specs | US federal **UFGS** sections from wbdg.org (public domain): 26 32 15 engine-generator sets, 26 23 00 LV switchgear, 26 33 53 static UPS, 26 12 19.10 pad-mount transformers | spec side of `check_submittal` |
| Submittals | Public manufacturer datasheets for real models (e.g. Caterpillar / Cummins gensets, Eaton / Schneider / Vertiv UPS and switchgear) | submittal side |
| Bids | **Synthetic.** We write 3–5 realistic subcontractor proposals per package with planted exclusions and qualifications. Prices are based on public cost references. The generator script and the answer key ship with the repo | `level_bids` |
| Schedule | **Synthetic** data-center schedule (CSV), "Project Alpha", with need-by dates per equipment item | `assess_delivery_risk` |
| Lead times | Public market reports (Wood Mackenzie survey coverage, NREL 2024 distribution transformer study, trade press), cited per equipment class, with date and range | lead-time ranges |

**Answer keys** (`eval/answer_keys/`) are labelled by a person, a team member, before we run the agent on that case. Each case is tagged `dev` or `heldout`.

## 6. Models (stated per run, as the rules require)

| Mode | Model | Why |
|---|---|---|
| Cloud (default) | Groq `openai/gpt-oss-120b` (free tier) | fast, good at structured extraction, ~$0 |
| Long documents | Gemini 2.5 Flash (free tier) | 1M context, high free throughput |
| **Private / offline** | Ollama, small open-weight model on CPU (our laptop: i5-1334U, 16 GB RAM, no GPU) | no data leaves the machine. Because code does the comparisons, the accuracy gap to cloud stays small; we measure and report it |

Every run logs the model, tokens, cost (USD) and latency into `run`.

## 7. Evaluation (numbers that go in the README and the deck)

- `check_submittal`: per-verdict precision and recall against the answer key, plus the citation-valid rate (target 100%).
- `level_bids`: exclusion recall, false exclusions, and whether the award matches the key.
- `assess_delivery_risk`: rank correlation with the key's risk order, and the share of keyed dates inside the P10–P90 range.
- **Fabrication count:** vendors, products or numbers that appear in no source. Target: 0, checked automatically.
- Cost and time per run, cloud vs offline.

## 8. Build plan

The round started on 9 Nov, so code written now counts as hackathon work. We have 15 days.

| Dates | Goal |
|---|---|
| 21–22 Nov | Repo, shared schema, PDF → pages/paragraphs with locators (OCR for scanned pages), quote verifier, eval harness. Teammate labels G1–G2 |
| 23–25 Nov | `check_submittal` end to end on the dev cases; MCP server working in a real MCP client. Switchgear + UPS specs |
| 26–28 Nov | `level_bids` with synthetic bids + keys; cross-check against submittal results |
| 29 Nov–1 Dec | `assess_delivery_risk` + `run_package_review`; offline mode via Ollama |
| 2–3 Dec | Held-out eval; fix failure classes (not individual cases); cost/latency table; README |
| 4–5 Dec | Demo video (≤5 min), deck (8–10 slides); stretch goal only if everything is green |
| 6 Dec | Fresh-clone install test, submit **by afternoon IST** |

## 9. Risks

- **Groq free tier is 8k tokens per minute.** Long specs won't fit in one call. Mitigation: parse the spec into paragraphs first and send only Part 2 (Products) paragraphs in batches, with Gemini for long reads.
- **CPU-only offline mode is slow.** Mitigation: offline mode runs extraction only, on small batches. We report its real time per run honestly.
- **Bid documents are synthetic.** Mitigation: say so on slide 1 of the data section, ship the generator, and keep the planted issues realistic. The variety comes from writing them by hand.

## 10. What changed from the plan (as built, 22 Nov)

The plan above held up; these are the differences and the reasons, each one driven by a measured error.

- **Requirements are structured once per spec and cached** (`data/requirements/`, keyed by spec, equipment row and
  checklist hash). Structuring depends only on the spec, so it is done once with a capable model; every later submittal
  check, including offline on a small local model, only has to read the submittal. A 4B model could not write the
  structured list itself (it produced nothing) but could read datasheets correctly.
- **Two more guards on every claim** (section 4): the reported number must appear in its own verified quote, and a
  number whose unit is not in the quote cannot be a confident claim. The first caught a verified quote that did not
  support the value claimed ("Ambient design, F 104" for a reported 122); the second caught voltage-header numbers read as kVA.
- **Model and code disagreement goes to a person**, and any verdict that rests on the model's reading of a quote
  (for example a derate sentence) is capped below the handoff line.
- **A second look for "not stated"**: a false `missing` is a risky claim, so conditions the first pass gave up on are
  re-read with a wider net before `missing` is accepted. Bill-of-material pages are always shown to the model.
- **Qualifiers stay inside their parent condition** ("at 30% dip" is part of the motor-starting rating, not a separate check).
- **Paid-API spending is capped** by a persistent ledger, and a failed model call degrades to "not checked", never to a claim.
- **Held-out discipline**: G3, G4 and U1 are labelled but the scorer refuses to run them without `--final`.
- **Offline mode is real but slow on a laptop CPU** (minutes per call). The README reports the measured time and accuracy.
