# Pitch deck outline (8 to 10 slides)

Judging: accuracy, customer value, trustworthiness, build quality. One idea per slide, big text, screenshots from
`runs/package_GEN.html` instead of long bullets. The submission also needs the names and colleges of all team members.

1. **Title**: "Amber procurement specialists". Track 03, Students division. Team names and CMR Institute of Technology.
2. **The problem**: Data-center and construction buying is slow and error-prone. Teams compare bids by hand, check
   datasheets against specs line by line, and discover late deliveries too late. One missed exclusion or one late
   switchgear can cost weeks.
3. **Our answer**: six specialists, one product. Check the submittal. Level the bids. Forecast delivery. Review a whole
   package. Find products that fit. Draft the vendor follow-ups. They share one data format, so each one's output feeds
   the next. Callable by Amber as MCP tools, and usable by a manager through a web page.
4. **How they work together** (diagram): bids in → scope matrix and leveled cost → each bidder's datasheet checked
   against the spec → a failed check adds a resubmittal cycle to that bidder's delivery forecast → one comparison table.
5. **Why you can trust it** (the heart of the deck):
   - the model reads, code decides (units, totals, dates);
   - no source, no claim: every quote is found on its cited page or dropped;
   - confidence from evidence; unsure goes to a person;
   - failures never become claims.
6. **Demo, three screenshots**: the source viewer (a cited datasheet page with the quote highlighted); the scope
   matrix; the review queue with a person's decision.
7. **Results** (held-out documents, labelled before the run, run once): 67 % of requirements correct on the latest
   set (59 % before our fixes); every answer it gave on its own right (11 of 11); zero fabricated citations in every
   run; bid leveling: 41 of 44 scope cells right, all four base prices exact, 2 of 4 leveled totals exact (the other two off by $30k and $122k because of three misread scope cells), ranking right, award correctly withheld. Say how the keys were made.
8. **Cost and speed**: open-weight gpt-oss-120b on Groq's free tier (Gemini 3.8 Flash only to read new scanned pages,
   opt-in). About $0.007 and 3 minutes per submittal check; a full package review $0.02 in 9 minutes; delivery
   forecast and follow-up drafts free (no model). Private mode runs on a laptop.
9. **Honest limits and what is next**: cross-requirement footnotes, scanned pages need a person, UPS and switchgear next,
   more equipment, more lead-time sources.
10. **Close**: "Agents a procurement manager can trust, because they show their sources and say when they are unsure."
    Link to the repo.
