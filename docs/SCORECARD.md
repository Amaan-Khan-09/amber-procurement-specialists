# Judge's scorecard

Every official criterion (Track 03 Vertical Agents) mapped to a demo step, a test and a file. Demo steps refer to
`docs/DEMO_SCRIPT.md`; the page is `docs/demo/case.html`; full tables are in `docs/RESULTS.md`. **Measured** numbers
come from scripts here; bidder companies, bids, packets and replies are **mock data**; datasheets and federal records
are **real**. The answer keys were written by an AI and **no person has reviewed them yet**.

## Headline numbers (measured)

| | original `9cd1b4e` | previous `1d14f3e` | candidate |
|---|---|---|---|
| Fixed set (256): sent to an engineer | 102 | 77 | **68** |
| Fixed set: unresolved (engineer + any question) | 161 | 144 | **127** |
| Fixed set: correct decisions alone | 94 | 111 | **128** |
| Fixed set: critical / missed escalations | 1 / 0 | 1 / 0 | 1 / 0 |
| Fixed set: right action on any route | 218 | 213 | **226** |
| Fresh sheets (42): unresolved | 35 | 30 | **27** |
| Fresh sheets: correct decisions | 6 | 11 | **13** |
| Fresh sheets: critical, as labelled (worse) | 0 | 0 | 1, a labelling error under review |
| Fresh sheets: missed escalations | 1 | 2 | 2 |

Half of the fixed set (127 of 256) and 64 % of the fresh set still wait on a person or a supplier.

## Judging criteria (official wording)

| Criterion | Demo step | Test | Artifact | Remaining gap |
|---|---|---|---|---|
| **Accuracy**: "does it get the job right on realistic examples?" | 5 | `tests/test_inspect.py`, `tests/test_accuracy.py` | `docs/RESULTS.md`, Proof tab (held-out sets 1 to 6) | Unreviewed keys; fresh sheets read by the smaller `gpt-oss-20b`; 2 missed escalations on fresh sheets |
| **Customer value**: "would a procurement manager or superintendent use it tomorrow, as a product?" | 1 to 4 | `tests/test_case.py` | `python -m amber.case run`, the case page | One project and one equipment package |
| **Trustworthiness**: "sources cited, sensible confidence scores, nothing made up" | 1, 2, 3 | `tests/test_evidence.py`, `tests/test_registries.py`, `tests/test_verify.py` | Evidence record; quotes verified on the page | Exclusion check not verified (no SAM.gov key); one critical error on the fixed set (bid cell B2 S2) |
| **Build quality**: "easy to run, cost and speed per run, code quality" | 4 | the whole suite | README quick start; tokens and cost on every saved run | Free model allowance limits live runs |

## Track 03 "what we're looking for"

| Ask | Demo step | Test | Gap |
|---|---|---|---|
| Rely on specialists "without a person checking every answer" | 5 | `tests/test_inspect.py` | 68 engineer cases; the largest group is model disagreement (33) |
| Right on unseen problems, findings traced to source | 5 | `eval/handoff_set/results.json` | Two fresh sheets only |
| Broad suite without trading depth | 1 to 4 | `tests/test_server.py` | Vendor pre-qualification of real companies covers identity, award history and screening only |
| Clean hand-offs between specialists | 2, 3 | `tests/test_evidence.py` | 22 package cases we worked on: 22 right with 7 to an engineer; datasheet alone, same routing, 17 right with 6 |
| Never make things up | 1 | `tests/test_registries.py` | None found; unverified items are shown as unverified |

## Why a judge might rank another entry higher

Half the cases are still open, the team wrote its own answer keys, and the newest fresh test still produced errors. The
honest reply is the comparison on identical inputs, every remaining case with its reason, and each error shown with its
cause. The review of the keys by a person is the gap that only the team can close.
