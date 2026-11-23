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
| 0:45 | **Saved results** → `package_GEN` | "Now the real job: four bids for four 2000 kW generators. The agent levelled the bids, checked two suppliers' datasheets against our spec, and forecast delivery for each option. It took nine minutes and two cents." |
| 1:05 | The yellow banner and the bidders table | "It does not auto-award, and it says why. B3 has the cheapest headline price, 3.98 million, but once you price what it leaves out it is 4.49 million, its product fails the spec, and it has the longest lead time." |
| 1:35 | **What each bid covers**: click a red **excluded** cell (B3, S4 or S5) | "Green is included, red is excluded. Click any cell and you see the bid's own words on the page, highlighted. Nothing here is the model's opinion: it is the document." Close the panel. |
| 2:00 | **Findings**: filter **All**, type `UL` in the search box, find the B3 fuel-tank finding, click **View on the page** | "This is why B3 fails: the spec asks for a UL 2085 tank, and the Kohler datasheet says UL 142. Both quotes, both pages, one click each." |
| 2:30 | Clear the search. Filter **For you to review**. On one item press **Agree**; on another choose **Change to…**, add a short note, **Save** | "When the agent is not sure, it does not guess: it hands the item to a person. I agree with this one and correct that one. My decisions are saved with the result, and the counter at the top tracks the review." |
| 3:00 | Scroll to **Vendor follow-ups**, open the B3 bid clarification, press **Copy** | "Then the next action: a clarification letter for each bidder and comments for each submittal, built only from verified quotes. Nothing is sent until a person sends it." |
| 3:20 | Back to the bidders table: click **Find products that fit** next to B3; then open `discovery_GEN-A` from Saved results | "If a product fails, which one would fit? The agent screens every datasheet we hold on the key ratings. It only names products from documents we have, never from memory." |
| 3:55 | Terminal: `python scripts/demo_mcp_client.py` | "All of this is six MCP tools, so Amber can call any of them directly. Same answers, same sources, as JSON." |
| 4:15 | README → "Held-out set 2" table | "We tested on datasheets the agent had never seen, labelled before it ran, and run once. 67 % of requirements correct; every answer it gave on its own was right, 11 out of 11; zero invented citations. The rest it sent to a person, which is what you want." |
| 4:40 | Overview tab again | "Agents a procurement manager can trust: they show their sources, and they say when they are unsure." |

## Do not say

* "The AI approves the purchase." It never awards on its own when there is an open risk, and a screen is never an
  approval.
* Any accuracy number that is not in the README.
* Real company names for the bidders. B1 to B4 are fictional, and every page says so. The datasheets are real public
  documents from the manufacturers.
