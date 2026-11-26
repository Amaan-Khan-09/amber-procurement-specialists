# Judge's scorecard

Every official criterion (Kaya AI Grand Challenge, Track 03 Vertical Agents) mapped to a demo step, a test and a file.
**Demo step** numbers refer to `docs/DEMO_SCRIPT.md`; the page is `docs/demo/case.html`. Labels: **measured**
(computed by a script here), **mock data** (fictional companies and documents), **real** (public records and
datasheets). Full tables and every case that changed: `docs/RESULTS.md`.

## The headline numbers (measured)

| | Baseline (commit 9cd1b4e) | Now |
|---|---|---|
| Sent to an engineer, fixed set of 256 cases | 102 (40 %) | **77 (30 %)** |
| Correct decisions made alone | 94 | **111** |
| Wrong decisions (all critical) | 1 | **1** |
| Missed mandatory escalations | 0 | **0** |
| Clarifications asked (none yet resolved by a verified reply) | 0 | 10 |
| Questions the key says were not needed (worse) | 3 | 11 |
| Right action on any route (worse) | 218 | 213 |
| Two fresh unseen sheets, frozen code: sent to an engineer | 23 of 42 | **15 of 42** |
| Two fresh unseen sheets, frozen code: wrong decisions (worse) | 0 | 1 |

The 10-point hand-off stretch target was **just missed (9.8 points)**. On the unseen sheets the new version **added one
wrong decision**; it was fixed afterwards with a regression test, which does not make those sheets unseen again.

## Judging criteria

| Criterion (official wording) | Demo step | Test | Artifact | Remaining gap |
|---|---|---|---|---|
| **Accuracy**: does it get the job right on realistic examples? | 6 | `tests/test_inspect.py`, `tests/test_accuracy.py` | `docs/RESULTS.md`; Proof tab (held-out sets 1 to 5) | Set 5 was read by the smaller `gpt-oss-20b`; answer keys are AI-written and unreviewed |
| **Customer value**: would a procurement manager use it tomorrow? | 1 to 5 | `tests/test_case.py` | `python -m amber.case run`; the case page | One project, one equipment package; supplier replies are **mock data** |
| **Trustworthiness**: sources cited, sensible confidence, nothing made up | 1, 3, 4 | `tests/test_evidence.py`, `tests/test_registries.py`, `tests/test_verify.py` | Evidence record; quotes verified on their page; 0 invented citations | One critical error remains (bid scope B2 S2); the federal exclusion check is **not performed** without a SAM.gov key |
| **Build quality**: easy to run, cost and speed, code quality | 5 | the whole suite (`pytest`) | README quick start; cost and tokens on every saved run | Free model allowance (200k tokens a day per model) limits live runs |

## Track 03: what the brief asks for

| What the brief asks | Demo step | Test | What it shows | Gap |
|---|---|---|---|---|
| "Rely on your specialists without a person checking every answer" | 6 | `tests/test_inspect.py` | Engineer queue 40 % to 30 % | 77 cases still reach an engineer (41 of them needed per the key); 23 judged readings and 23 model disagreements are the largest groups |
| Right on unseen problems, every finding traced to its source | 6 | `eval/handoff_set/fresh_unseen.json` | Two sheets labelled after a code freeze: correct decisions 9 to 14 of 42 | One new wrong decision; two sheets only |
| A suite covering the workflow without trading depth | 1 to 5 | `tests/test_server.py` | All eight listed specialists as nine MCP tools | UPS has checks but no case file |
| Clean hand-offs: "more than the sum of their parts" | 3, 4 | `tests/test_evidence.py` | Same routing, 22 package cases: datasheet alone 16 right and 8 to an engineer; with the bid 21 and 6; today 22 and 7 | Those 22 cases were inspected while fixing them |
| Long-running work with memory | 5 | `tests/test_case.py` | Interrupted run resumes; replies flow back | None known |
| Document reading beyond OCR | 3, 4 | `tests/test_inspect.py`, `tests/test_evidence.py` | Option ticks, derating footnotes, table-heading units, explicit supersession, conflicts | Rules cover the notations seen; a new one goes to a person |
| Honest ranges | 5 | `tests/test_delivery.py` | Cost ranges with assumptions; arrival P10/P50/P90 from cited reports | Allowances are **mock data** |
| Linking records | 2, 3 | `tests/test_case.py` | Ambiguous model reported; evidence tied to supplier, bid, tags, model, document, revision | Model designations and paragraph references only |
| Vendor discovery and pre-qualification | 1 | `tests/test_registries.py`, `tests/test_case.py` | **Real** federal award records with UEIs; source, time and match status per supplier | SAM.gov exclusions **unverified** (needs a key); the bidder companies are fictional, so no federal record exists for them |

## The most convincing reason a judge would rank another entry higher

"Thirty percent still goes to an engineer, the team wrote its own answer keys, and the one fresh test added an error."
Our reply: the share is measured against our own earlier version on identical inputs; every remaining case has a stated
reason; the error is shown with its cause and the test that now guards it. What we cannot argue away is that **no person
has reviewed the answer keys**.
