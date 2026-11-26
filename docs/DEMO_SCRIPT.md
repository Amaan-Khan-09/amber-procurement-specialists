# Demo video script (5 minutes maximum)

One purchase decision, end to end, from vendor lookup to a verdict backed by exact words. Everything on screen comes
from this repository. **Real**: the datasheets, the spec, the federal registry lookups. **Fictional**: the bidder
companies, their bids, packets and replies (every page says so).

## Before you record

1. `.venv\Scripts\activate`, then `python -m amber.web`; open http://127.0.0.1:8000 and click **Case file**.
2. For step 5, warm up once in a terminal: `python -m amber.case run --fresh --crash-at reconcile` (about 1.5 minutes),
   then `python -m amber.case run` (about 35 seconds). Cut while each runs. Neither calls a model.
3. Browser zoom 110 %, one colour mode, notifications off.

## The script

| Step | Time | On screen | Say |
|---|---|---|---|
| | 0:00 | Title | "Buying four 2000 kW generators means finding suppliers, checking they may be bought from, and reading bids and datasheets against a spec. Our specialists do that and show the exact words behind every answer." |
| 1 | 0:20 | **Public records** section; open one award link | "Discovery starts with real federal records: who has actually supplied 2000 kW sets, with their legal identifier. A record is not a qualification. And look at the exclusion column: it says *unavailable*, because the official list needs a key we do not have. The agent never reports that as clean." |
| 2 | 0:50 | **One decision** steps 2 and 3 | "Now one bid. Tidewater is ranked first in our own vendor list, which is made-up data, and passes pre-qualification only after its reply. The bid names model DQKAB, and exactly one datasheet is about it." |
| 3 | 1:20 | **One decision**: the evidence record for the fuel tank | "Does its fuel tank meet the spec? The datasheet says nothing. The bid offers a 12-hour tank: a deviation. The reply says it supplies a 24-hour UL 2085 tank *in place of* the 12-hour one. So the bid's line is marked superseded, the reply controls, with its exact words, page and date. Two replies that disagreed without saying that would stay a conflict." |
| 4 | 2:00 | Below it: **B3 R09** | "The same method exposes a problem. Kohler's datasheet says its radiator is rated 122 degrees. Its footnote says an enclosed silencer takes 9 degrees off, and this bid puts the silencers inside. 122 minus 9 is 113, below the spec. An engineer confirms that, with both quotes side by side." |
| 5 | 2:40 | **Decision** and **Ranges**; then the terminal | "The award stays with a person; cost is a range with its assumptions. It is long-running work: I stop a run inside a step and start it again, and it resumes there." |
| 6 | 3:25 | **Measured** section | "Against our own previous version, on the same 256 cases: engineer hand-offs from 40 to 30 percent, correct decisions from 94 to 111, wrong decisions 1 and 1, no missed escalations. It costs something: more clarifications that were not needed." |
| 6 | 4:05 | Fresh unseen table | "Then two datasheets nobody had seen, labelled after we froze the code. Hand-offs fell from 23 to 15 of 42, and it made one new mistake: it read a fuel flow figure as fuel consumption. We fixed it, added a test, and show both numbers." |
| 6 | 4:35 | **Got worse** list | "Every case that got worse is listed. Our answer keys are our own and not yet reviewed by a person: that is the limit of these numbers." |

## Do not say

* "No supplier is excluded." The federal check was **not performed** (no SAM.gov key).
* "10 points fewer hand-offs." It is 9.8 (102 to 77 of 256).
* "13 to 6 against datasheets alone." That compared two changes at once; with the same routing it is 8 to 6.
* "The AI approves the purchase", or that a clarification solved anything: none has been answered and verified yet.
* Real company names for the fictional bidders.
