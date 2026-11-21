# Demo video script (5 minutes maximum)

Rules say: up to 5 minutes, showing the agent solving a realistic example from start to finish. Record the screen
and talk over it. Practise once; keep to the times. Everything shown below is real output from this repo.

**Before you record**
1. Open two things side by side: a terminal in the project folder, and `runs/package_GEN.html` in a browser.
2. Run `python scripts/make_report.py runs/package_GEN.json` if the page is out of date.
3. Have these PDFs open on the page named: the Kohler KD2000 datasheet (p.6) and the generator spec (p.8).
4. Use dark or light mode, but keep the same one for the whole video. Zoom the browser to 110%.

| Time | On screen | Say (in your own words) |
|---|---|---|
| 0:00 | Title slide | "Buying a generator for a data center takes months and one missed line can cost weeks. We built three specialist agents a procurement team could use tomorrow." |
| 0:20 | Terminal: `python scripts/demo_mcp_client.py` | "They run as MCP tools, so Amber can call them directly. The server lists its four tools, and here Amber asks one of them a question." Let the table print. |
| 0:50 | Datasheet + spec side by side, then the report section "product submittal against the spec" | "Specialist one checks a supplier's datasheet against the spec, line by line. Every verdict quotes both documents, with the page." Point at one **deviates** finding: the fuel tank is UL 142 but the spec wants UL 2085. Point at the quote on each side. |
| 1:30 | Report: a finding marked "for review" | "When it is not sure, it says so and hands it to a person instead of guessing. Anything read from a scanned page, or where the model and the maths disagree, goes to a person." |
| 1:50 | Report: "What each bid covers" | "Specialist two levels four bids. They each cover something different. Green is included, red excluded, amber is a shortfall such as a 12-hour tank where 24 is required." Hover one cell to show the bid's own words. |
| 2:30 | Report: "Bidders side by side" | "The cheapest headline bid is not the cheapest once you add what it leaves out. It will not auto-award: the cheapest has an open tariff clause and the longest lead time, and two products do not meet the spec." |
| 3:00 | Report: "When will it arrive?" | "Specialist three forecasts delivery. Bars are the earliest-likely to latest-likely arrival, the dashed line is the date we need it. It is built in code from four published lead-time reports. One source disagreed wildly and it is shown as dissent, not averaged in." |
| 3:40 | Terminal: `python -m pytest -q tests/test_verify.py` | "The rule that matters most: no source, no claim. Every quote must be found on the page it cites. An invented quote, or a wrong number, is thrown away. Tests prove it." |
| 4:10 | README results table | "We measured ourselves against answer keys written from the source documents before we ran the agent. [Say the final held-out number here.] Zero fabricated citations. It names its models and reports cost per run: about a cent for a full submittal check." |
| 4:40 | README "Known limits" | "And we list where it fails: for example it can miss a footnote that interacts with a second requirement." |
| 4:55 | Title slide | "Agents a procurement manager can trust, because they show their sources and say when they are unsure." |

**Do not say** anything the repo does not do: no "AI approves the purchase", no claims about accuracy numbers that are
not in the README, no real company names for the bidders (they are fictional and the pages say so).
