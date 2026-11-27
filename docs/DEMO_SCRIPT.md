# Demo video script (5 minutes maximum)

The main demo needs **no live supplier reply and no model call**: it reads saved results. Real: datasheets, spec,
federal records. Fictional (say so): bidder companies, bids, packets, replies.

## Before you record

1. `.venv\Scripts\activate`, `python -m amber.web`, open http://127.0.0.1:8000 and click **Case file**.
2. Warm up the terminal once: `python -m amber.registries "Southern Power Systems Services Inc"`.
3. Browser zoom 110 %, one colour mode, notifications off.

## Script

| Step | Time | On screen | Say |
|---|---|---|---|
| | 0:00 | **Front screen** of the case page: the three quotes and 122 - 9 = 113 | "This datasheet says the radiator is good for 122 degrees, which is what the spec asks. But a footnote says an enclosed silencer takes 9 degrees off, and this supplier's bid puts the silencers inside. 113 degrees: below the spec. Our specialists read the documents together, show the exact words, and ask an engineer to confirm." (The bid is a fictional test document.) |
| 1 | 0:20 | **Public records** and the scorecard | "These are real companies from federal award records, with their legal identifiers. This one has supplied 2000 kilowatt sets. It is flagged, not passed: the federal exclusion list needs a key we don't have, so it says not verified. Nothing is assumed clean." |
| 2 | 1:00 | **Before and after**: G6 R01 | "This used to go to an engineer: the ratings table has several rows. The agent now takes the row for our 480 volt project, quotes it, and decides." |
| 2 | 1:35 | Same section: G6 R11 | "This one still goes to an engineer, and should. Full rating at 122 degrees depends on how a derating clause is read, and the model's reading and the code's check disagree. Both are shown." |
| 3 | 2:10 | **One decision**: evidence record, then B3 R09 | "Documents are read together. A reply that says 'in place of' supersedes the bid, with the exact words. And a footnote about an enclosed silencer, plus a bid that puts silencers inside, drops a radiator rating below the spec: laid out for an engineer." (The reply and bids are fictional.) |
| 4 | 2:55 | **Steps & resume**, **Decision** | "It is one case file that resumes after an interruption. The award stays with a person." |
| 5 | 3:25 | **Measured** | "On 256 cases we built against, open items fell from 144 to 127 against our previous version, engineer hand-offs from 77 to 68, and correct decisions rose from 111 to 128, with no new wrong decision." |
| 5 | 4:00 | Fresh sheets table | "Then two sheets nobody had opened. Open items fell from 30 to 27. They also showed what is still wrong: two items that needed an engineer were not sent to one, and one error turned out to be our own label." |
| 5 | 4:30 | Same page | "And a fresh cross-document test caught the agent accepting a bid's figure over a failing datasheet. We fixed it and kept both results on the record. Half the items still wait for a person or a supplier. That is where we are." |

## Do not say

* "No supplier is excluded": the check was not performed.
* "The question resolved it": no question has been answered and verified in the measured sets.
* "22 of 22" without "on cases we worked on".
* "No wrong decisions on unseen documents": there was one as labelled, two missed escalations, and one cross-document error.
