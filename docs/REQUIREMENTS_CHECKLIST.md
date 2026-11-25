# Contest requirements: where each one is met

Every requirement on the Kaya AI Grand Challenge page (Track 03 and "What every entry must do"), with the evidence in
this repository a judge can check. Status: **met**, **partly met** (with the gap stated), or **to do** (before submission).

## What every entry must do

| Requirement (contest wording) | Status | Evidence |
|---|---|---|
| Return structured output (for example JSON), not only free text | met | Every tool returns `ToolResult` (`amber/schema.py`); the MCP server publishes its JSON Schema (`tests/test_server.py::test_tools_publish_a_typed_output_schema`) |
| Be callable by another agent: run as an MCP server | met | `python -m amber.server` (stdio or `--http`), six tools; `scripts/demo_mcp_client.py` calls it as an agent would |
| Show its sources for every answer: document, page, row, photo, recording or website | met | Every finding carries `citations` (document, page, paragraph or row, exact quote); quotes are verified on the page (`amber/verify.py`); award and package decisions cite the clauses they rest on (`tests/test_bids.py::test_award_answer_cites_its_evidence`); lead-time figures cite the website, date and quote (`data/leadtime_sources/leadtime_evidence.csv`) |
| Give a confidence score with each answer, and hand off to a human when it isn't sure | met | `confidence` on every finding, built from evidence; under 0.70 → `needs_human` with a reason |
| Never make things up | met | 0 fabricated citations in every scored run, dev and held-out; the scorer re-checks each citation independently (`scripts/eval_submittal.py`); numbers must appear in their own quote |
| Be easy to run, with a README and simple setup steps | met | README Quick start, verified from a fresh clone of the GitHub repo with no keys (all tests pass, MCP demo runs) |
| Name the AI models used, with a rough cost and response time per run | met | README "Models, cost and time"; every result reports models, tokens, cost and latency, and logs each model call (`run.steps`) |

## Track 03: Vertical Agents

| Requirement | Status | Evidence |
|---|---|---|
| A suite of specialists that work together as one product, each output feeding the next | met | `run_package_review`: bid leveling → submittal check per bidder → delivery forecast per bidder (a failed submittal adds a resubmittal cycle) → one comparison |
| Specialists from the list (bid leveling; schedule and delivery risk; spec and submittal compliance; product discovery; lead time prediction; vendor discovery; vendor pre-qualification; private deployment) | partly met | Built: bid leveling, spec and submittal compliance, schedule and delivery risk, lead time prediction (P10/P50/P90 from cited evidence), product discovery (`find_products`: screens the datasheets we hold on key ratings, cited; never from model memory), private deployment (offline on a laptop GPU, measured). Not built: vendor discovery, vendor pre-qualification |
| Callable by another agent (MCP or API), works on its own | met | Each specialist is its own MCP tool |
| Structured input and output | met | Typed inputs (paths, tag, checklist, lead-time dicts); typed output schema |
| Show sources; confidence; never make things up; no built-in answers | met | As above; no document-specific rules in code; held-out cases labelled before any run and run once |
| README, simple setup, models with rough cost and response time | met | As above |
| Shared data formats across the suite | met | One `ToolResult` / `Finding` / `Citation` format for all tools |
| Private deployment: works fully offline, close in accuracy to the cloud version, responds quickly, deploys with one command | met, with measured limits | `AMBER_PROVIDER=ollama python -m amber.server`; G2 offline 67 % in 20 min on an integrated GPU (README, "Private (offline) mode") |
| Data: public sources or self-made sample data, cited; no confidential data; explain any dataset | met | `data/SOURCES.md`, `data/PROJECT_ALPHA.md`; synthetic bids and project are labelled fictional on every page |

## Judging criteria

| Criterion | Where we stand |
|---|---|
| Accuracy | Held-out set 1 (run once, before fixes): 34/58 (59 %). Held-out set 2 (run once, after fixes): 28/42 (67 %). Held-out set 3 (fresh documents, labelled before the run, run once, after the accuracy fixes): 32/42 (76 %), 0 false approvals, 0 false rejections. On sets 2 and 3, 25 of 26 automatic answers matched the key; 0 fabricated citations in every run. Bid leveling 41/44 scope cells on one reading and 39/44 on a second (same documents, same model), all four base prices exact both times, award withheld both times |
| Customer value | Package review answers the real question (who to award, what is missing, what will be late) in one table; follow-up drafts for every gap; a web page for managers with a one-click source viewer (the cited page, quote highlighted) and a review queue |
| Trustworthiness | Sources on every answer, verified quotes, 0 fabricated citations, cautious handoffs, failures never become claims |
| Build quality | 121 tests, fresh-clone install verified, cost and time per run measured |

## What to submit (Round 1, by Sunday 6 December 2026)

| Item | Status |
|---|---|
| Track and challenge, and division | Track 03 Vertical Agents, Students division (in README header) |
| Code repository link with README | https://github.com/Amaan-Khan-09/amber-procurement-specialists |
| Demo video, up to 5 minutes, solving a realistic example end to end | to do (script: `docs/DEMO_SCRIPT.md`) |
| Pitch deck, 8 to 10 slides | to do (outline: `docs/PITCH_DECK.md`) |
| Names and affiliations of all team members | to do |

Also from the rules: original work created during the hackathon period (repository history starts 21 Nov 2026; Round 1
opened 9 Nov); IP terms "will be shared before launch" (check the Devpost page before submitting).
