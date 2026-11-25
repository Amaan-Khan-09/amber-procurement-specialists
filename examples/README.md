# Saved results

The exact results behind every number in the main README, so they can be checked without an API key:

| File | What it is |
|---|---|
| `package_GEN.json` | full package review of the four generator bids (the demo) |
| `discovery_GEN-A.json` | product discovery over the datasheet library for GEN-A |
| `BL1.json` | bid leveling of the four bids |
| `G1.json`, `G2.json` | submittal checks on the development cases |
| `G3.json`, `G4.json`, `U1.json` | held-out set 1, run once on 22 Nov 2026 |
| `G5.json`, `G6.json` | held-out set 2, run once on 24 Nov 2026 |
| `G2_local_qwen3_8b.json` | the same check as G2, run fully offline on a laptop with the 22 Nov code (it contains one false rejection, requirement R03, which today's code hands to a person) |

`package_GEN.json` and `BL1.json` keep their original model readings; the decision code was applied to them again on
26 Nov 2026 after the audit described in the main README (no model call; each file records this).

Open them in the web page (`python -m amber.web`, then **Saved results**; nothing is spent), turn the package review
into a report with `python scripts/make_report.py examples/package_GEN.json`, or re-score a case against its answer
key with `python scripts/eval_submittal.py --case G5` (scoring reads `runs/`; copy the file there first).

Quotes in these files are short excerpts (at most about 200 characters) from the public documents listed in
`data/SOURCES.md`, kept as citations. The bidders and Project Alpha are fictional.
