# Pitch deck outline (8 to 10 slides)

Judging: accuracy, customer value, trustworthiness, build quality. One idea per slide, big text, screenshots from
`runs/package_GEN.html` instead of long bullets. The submission also needs the names and colleges of all team members.

1. **Title**: "Amber procurement specialists". Track 03, Students division. Team names and CMR Institute of Technology.
2. **The problem**: Data-center and construction buying is slow and error-prone. Teams compare bids by hand, check
   datasheets against specs line by line, and discover late deliveries too late. One missed exclusion or one late
   switchgear can cost weeks.
3. **Our answer**: three specialists, one product. Check the submittal. Level the bids. Forecast delivery. They share
   one data format, so each one's output feeds the next. Callable by Amber as MCP tools.
4. **How they work together** (diagram): bids in → scope matrix and leveled cost → each bidder's datasheet checked
   against the spec → a failed check adds a resubmittal cycle to that bidder's delivery forecast → one comparison table.
5. **Why you can trust it** (the heart of the deck):
   - the model reads, code decides (units, totals, dates);
   - no source, no claim: every quote is found on its cited page or dropped;
   - confidence from evidence; unsure goes to a person;
   - failures never become claims.
6. **Demo, three screenshots**: a `deviates` finding with both quotes; the scope matrix; the delivery chart with the need-date line.
7. **Results**: answer-key accuracy on held-out documents (fill in after the final run), zero fabricated citations,
   scope matrix 41/44, all prices and rankings right. Say how the keys were made and that they were written before the runs.
8. **Cost and speed**: models named (Groq gpt-oss-120b, Gemini 3.8 Flash for scans), about a cent per submittal check,
   delivery forecast is free (no model), private mode on a laptop.
9. **Honest limits and what is next**: cross-requirement footnotes, scanned pages need a person, UPS and switchgear next,
   more equipment, more lead-time sources.
10. **Close**: "Agents a procurement manager can trust, because they show their sources and say when they are unsure."
    Link to the repo.
