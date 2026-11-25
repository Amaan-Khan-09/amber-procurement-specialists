# Demo video script (5 minutes maximum)

The rules ask for up to 5 minutes showing the agent solving a realistic example from start to finish. Record the
screen and talk over it in your own words. Practise once and keep to the times. Everything below is real output from
this repo; nothing is staged.

## Before you record

1. In the project folder: `.venv\Scripts\activate`, then `python -m amber.web`. The page opens at http://127.0.0.1:8000.
2. Check that **Saved results** lists `package_GEN` (the full package review) and `discovery_GEN-A` (product
   discovery). Both open instantly and spend no tokens, so the video never waits on a model.
3. Browser zoom 110 %, one colour mode for the whole video, close other tabs and notifications.
4. Have a terminal open in the project folder for the 3:55 step.

## The script

| Time | On screen (what to click) | Say |
|---|---|---|
| 0:00 | Title slide | "A data center cannot switch on until its generators, UPS and switchgear arrive and match the spec. Buying them is slow, manual and one missed line costs weeks. We built specialist agents for that job, which Amber can call." |
| 0:15 | **Overview** tab | "This is the project at a glance. Two of five equipment groups will probably be late: the switchgear has a 96 % chance of missing its date." |
| 0:30 | In the table, click **LT-002** next to Generators | "Every number has a source. This lead time comes from a contractor's published report: here is the publisher, the date, the exact words, and a link to the website." Close the panel. |
| 0:45 | **Saved results** → `package_GEN` | "Now the real job: four bids for four 2000 kW generators. The agent levelled the bids, checked all four suppliers' datasheets against our spec (and that each datasheet is for the product that was bid), and forecast delivery for each option. It took about ten minutes and two cents." |
| 1:05 | The yellow banner and the bidders table | "It does not auto-award, and it says why. B3 has the cheapest headline price, 3.98 million. Priced for what it leaves out, it is 4.49 million, eighteen thousand above B4, and the agent says that order is not settled: part of B3's total rests on readings a person has to confirm. No bid includes rigging or the load bank test." |
| 1:35 | **What each bid covers**: click a red **excluded** cell (B3, S4 or S5) | "Green is included, red is excluded. Click any cell and you see the bid's own words on the page, highlighted. Nothing here is the model's opinion: it is the document." Close the panel. |
| 2:00 | **Findings**: filter **For you to review**, type `UL 2085` in the search box, open the **B3** fuel-tank finding from the submittal check, click **View on the page**. Show the UL 142 sentence on the datasheet page, close, then **Change to…** deviates, note "tank is UL 142", **Save** | "Here the agent was not sure, so it did not guess. The spec asks for a UL 2085 tank. On the supplier's own page the tank is listed to UL 142. The second reader says it complies; the page says otherwise. That is why a person decides. I mark it as a deviation, and my decision is saved with the result." |
| 2:30 | Search `motor starting`, open the **B3** finding, click **View on the page** | "And this is why it asks. The label is in one column of this datasheet and the number it picked up is in the other. It refused to reject a product on that. Just below is the right figure: 9,957 kVA at 480 volts, at a 35 % dip, against 3,000 required at 30 %. That margin is my call, and I mark it as complying." (Press **Change to…** complies, **Save**.) |
| 3:00 | Scroll to **Vendor follow-ups**, open the B3 bid clarification, press **Copy** | "Then the next action: a clarification letter for each bidder and comments for each submittal, built only from verified quotes. Nothing is sent until a person sends it." |
| 3:20 | **Saved results** → `discovery_GEN-A` | "If a product fails, which one would fit? The agent screens every datasheet we hold on the key ratings. It only names products from documents we have, never from memory." |
| 3:55 | Terminal: `python scripts/demo_mcp_client.py` | "All of this is six MCP tools, so Amber can call any of them directly. Same answers, same sources, as JSON." |
| 4:15 | **Proof** tab | "We tested on datasheets the agent had never seen, labelled before it ran, and run once. On the newest ones, 76 % of requirements correct, up from 59 % at the start. On the two newest sets, 25 of the 26 answers it gave on its own matched our key, and the one that did not asked the vendor for information. Zero invented citations. The rest it sent to a person, which is what you want." |
| 4:40 | Overview tab again | "Agents a procurement manager can trust: they show their sources, and they say when they are unsure." |

## Do not say

* "The AI approves the purchase." It never awards on its own when there is an open risk, and a screen is never an
  approval.
* Any accuracy number that is not in the README.
* Real company names for the bidders. B1 to B4 are fictional, and every page says so. The datasheets are real public
  documents from the manufacturers.
