# Devpost write-up (draft)

Paste into the Devpost project form, section by section. Amaan: edit anything that is not in your voice, then keep
every number as it is (each one is backed by the README and `examples/`). The team members' names and colleges go in
the Devpost team section, not here.

**Track:** Track 03, Vertical Agents · **Division:** Students

---

## Project name
Amber procurement specialists

## Tagline (one line)
Six procurement specialists for data-center power equipment that show their sources, say when they are unsure, and hand off to each other.

## Inspiration
A data center cannot switch on until its generators, UPS, switchgear and transformers arrive and match the spec.
Buying them is slow and manual. Engineers check a 60-page datasheet against the spec line by line, compare bids that
each leave out something different, and find out about a late delivery when it is too late. Kaya's challenge asks for
specialists a procurement team would actually pay for, and that Amber can call. We built for the three questions a
buyer asks every week: is this what we specified, which bid is really cheapest, and what will make us late?

## What it does
Six specialists, callable by Amber as MCP tools, sharing one data format so each one's output feeds the next:

* **Check a submittal**: every spec requirement against the supplier's datasheet: complies, deviates, missing or unclear, with the spec paragraph and the datasheet page quoted word for word.
* **Level bids**: what each bid includes, excludes or qualifies, priced like for like with the owner's allowances, with risky terms flagged. It also flags scope that no bidder covers.
* **Delivery risk**: P10 / P50 / P90 arrival dates, the chance of missing the need date and the latest safe order date, calculated in code from cited lead-time sources (no model).
* **Package review**: runs all of the above for one purchase and compares the bidders side by side. A failed submittal adds a resubmittal cycle to that bidder's delivery forecast. It checks that each submittal is for the product that was bid, and it recommends an award only when that is safe.
* **Find products**: screens every datasheet we hold on the key ratings, so a failed product can be replaced. It never names a product that is not in a document.
* **Follow-ups**: letters to suppliers about every gap, built only from verified quotes and never sent automatically.

There is also a web page for project managers: a 3D view of the site coloured by delivery risk, a source viewer that
opens the cited page with the quoted words highlighted, a spec-versus-datasheet side-by-side view, a keyboard-driven
review queue for the items the agent handed to a person, and a Proof tab that scores the saved runs against the
answer keys.

## How we built it
Python, the MCP SDK, PyMuPDF and pint. **The model reads; code decides**: the model extracts values and quotes, while
comparisons, unit conversion, totals, rankings and dates are computed in code. Every quote is searched for on the
page it cites and dropped if it is not found; a number must appear in its own quote; a check cannot pass while its
own evidence says "not included". Confidence is built from evidence, not asked of the model, and anything under 0.70
goes to a person. A failed model call is never turned into a claim.

Models: `gpt-oss-120b` on Groq's free tier for everything (open weights), plus Gemini 3.8 Flash only to read scanned
pages, behind a hard spending cap. The same checks also run fully offline on a laptop with a local model.

## How we tested it
Answer keys were written from the source documents **before** the agent ran. Held-out documents were run once, with no
tuning afterwards. On datasheets the agent had never seen: 59 % of requirements correct before our fixes, 67 % on the next set, and
**76 % (32 of 42) on the newest set**, labelled before the run and run once. **25 of the 26 answers it gave on its own
matched our key**; the one that did not asked the vendor for information. **Zero invented citations** in every
scored run. The rest it handed to a person, which is the point. A full purchase review takes about 10 minutes and costs
about 2 cents.

## Handing off to a person, honestly
About two answers in three go to a person, and we say so. 27 % of the requirements are genuinely unclear in the datasheet, so no
honest system can settle them. To help the person, a model of another family reads each datasheet blind and its verdict sits beside
ours: when it contradicts an answer, that answer is right only 38 % of the time (84 % when it agrees), so the queue shows the
contested ones first. We also tried a cheaper version that only shows the second model our quoted evidence; it did not work, and we
say so in the README.

## Challenges
Datasheets are messy: two-column pages, units in a header row, a "Not included" in the same line as the word we were
looking for. Each real mistake in our first held-out run became a rule in code and a test (for example a check can no
longer pass on a quote that says "not included"). Then we labelled fresh documents to measure the fix honestly.

## What we are proud of
Trust. You can click any answer and see the exact words highlighted on the real page. We publish our held-out results,
including the weak points: about three answers in four go to a person, and we say so.

## What we learned
In procurement, being confidently wrong costs more than asking. Designing for "I am not sure, here are the sources"
mattered more than raw accuracy.

## What is next
Switchgear and transformer answer keys, vendor discovery and pre-qualification from public records, and fewer
hand-offs as more labelled documents let us tune safely.

## Built with
Python · MCP (Model Context Protocol) · Groq · gpt-oss-120b · Gemini · PyMuPDF · pint · Starlette · Ollama (offline mode)

## Try it
Code and README: https://github.com/Amaan-Khan-09/amber-procurement-specialists

Live demo, nothing to install (read-only): https://amaan-khan-09.github.io/amber-procurement-specialists/demo/

No API key is needed to explore: `pip install -e .`, then `python -m amber.web` opens the page with the saved results.

## Data statement
Project Alpha and the bidders are fictional and labelled as such. Specifications are public guide specs (edited the way a
specifier would); datasheets are public manufacturer documents; lead times come from published industry reports, each
cited (`data/SOURCES.md`).
