# Demo video script (5 minutes maximum)

The rules ask for up to 5 minutes showing the agent solving a realistic example from start to finish. Record the
screen and talk over it in your own words. Practise once and keep to the times. Everything below is real output from
this repo; the bids, vendors and replies are fictional documents (every page says so); the datasheets are real.

## Before you record

1. In the project folder: `.venv\Scripts\activate`, then `python -m amber.web`. The page opens at http://127.0.0.1:8000.
2. Click **Case file: one purchase, end to end** (top right) once, so it is cached; then go back.
3. In a terminal in the project folder, run once to warm up: `python -m amber.case run --fresh --crash-at reconcile`
   (about 1.5 minutes) and then `python -m amber.case run` (about 35 seconds). Neither calls a model. Clear the
   terminal. In the video, cut while each command runs.
4. Browser zoom 110 %, one colour mode for the whole video, close other tabs and notifications.

## The script

| Time | On screen | Say |
|---|---|---|
| 0:00 | Title slide | "A data center cannot switch on until its generators arrive and match the spec. Buying four 2000 kW generators means finding suppliers, checking they qualify, reading four bids and four datasheets against a 12-page spec, and chasing every gap. We built specialists Amber can call for each of those jobs, and one case file that runs them together." |
| 0:20 | Case page, **Measured change** tiles | "First the number the brief cares about: can Amber rely on this without a person checking every answer? On 256 fixed cases, our earlier version sent 58 % to an engineer. This one sends 40 %. Another 23 % go straight to the supplier as a drafted question, because only the supplier can answer them. Right answers without a person went from 105 to 150, critical errors from 2 to 1, and every case that needs judgement still goes to a person." |
| 0:55 | **Vendor discovery** | "Step one: who could supply it? Only vendors in our vendor master, only products whose datasheets we hold, and every point is shown. Tidewater ranks first: best product fit, shortest lead time, a manufacturer the spec names." |
| 1:15 | **Pre-qualification**, the B2 rows (hover the yellow cells) | "But the first-ranked vendor does not pass pre-qualification yet. Its insurance expires before our need date, the manufacturer's letter is 'available on request', and it names no service branch, while our vendor master says Norfolk, 190 miles away. Conflicting records: the agent asks, it does not pick one. Keystone fails outright on its safety record." |
| 1:45 | **Record links**, the B4 row | "Linking records. Ridgeway bid a 'C2000D6'. No document names that exactly. One datasheet is a C2000D6E, a different variant, and another bidder's quote says a C2000D6 is model DQKAB, a different document. Our earlier check called that a match. Now it is reported as ambiguous with both candidates, and Ridgeway is asked." |
| 2:10 | **Reconciled answers**: rows B1 R12, B2 R19, then the blue note on B3 R09 | "The core technique: we read each supplier's bid as evidence, against the same spec, condition by condition. Caterpillar's datasheet never states its speed; the bid commits to 1800 rpm, so that is settled, with the quote. Tidewater's bid commits to a 12-hour fuel tank where 24 hours is required, a deviation the datasheet alone could not show. And Kohler's footnote says an enclosed silencer lowers the radiator rating by 9 °F. Keystone's bid says silencers inside. 122 minus 9 is 113, below the spec. The agent links the two and lays it out for an engineer." |
| 2:50 | **Questions & replies**, then **Ranges** | "Every open item becomes a question that cites what was read. Two suppliers replied, and each reply is read only against that supplier's open items. Northline's settled 14 items and revealed a heater that does not meet the spec. Tidewater's replaced its tank at 18,000 a set, which replaces our 220,000 allowance in its leveled cost, and settled its pre-qualification. Costs and arrival dates are ranges, with every assumption listed." |
| 3:25 | **Decision** | "And the decision stays with a person. Every option is likely to arrive after the need date, so the schedule is escalated, and each bidder shows exactly what still blocks it. Tidewater is now closest to an award." |
| 3:45 | Terminal: `python -m amber.case run --fresh --crash-at reconcile`, cut, then `python -m amber.case run` | "This is long-running work, and every step saves its state. Here I stop the run inside a step on purpose and start it again: the finished steps are reused, and the interrupted one runs again. Replies that arrive days later flow back the same way." |
| 4:20 | Case page: open **Every case the agent now gets wrong on its own** | "We show our failures too. Every case it still gets wrong on its own is listed beside the key's answer. The checks on datasheets it had never seen are in the README: 76 % on the newest set, and zero invented citations." |
| 4:40 | Case page, top | "Nine MCP tools, one case file, sources on every answer. Specialists Amber can rely on, because they know which questions only a supplier or an engineer can answer." |

## Do not say

* "The AI approves the purchase." It never awards on its own, and a screen is never an approval.
* "70 % of answers go to a person" as today's figure: that was the earlier version. Say "58 % to 40 % on 256 fixed cases".
* That the 256 cases are unseen: they are a fixed development set. Only the README's held-out sets are unseen.
* Real company names for the bidders or vendors. They are fictional; the datasheets are real public documents.
* Any number that is not on the case page or in the README.
