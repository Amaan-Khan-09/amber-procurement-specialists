# Results: before and after

Every number comes from `python scripts/eval_handoffs.py` (all three versions read the same saved model output).

* **v1** anything under 0.70 goes to one queue (commit 48b321c).
* **v2** the baseline for this round (commit 9cd1b4e): decided / ask the supplier / engineer, supplier documents reconciled.
* **v3** now: v2 plus a second look in code at the disputed clause and its evidence (`amber/inspect_evidence.py`, `amber/evidence.py`).

A **clarification** is never counted as a resolution here: it is scored as a question. Resolution by follow-up is scored only where a reply exists (the case file). A **wrong decision** is critical when it approves what fails or is not shown, or rejects what complies. Answer keys were written by an AI before the code they score; no person has reviewed them.

## Fixed development set (documents seen while building: a repair record)

### All like-for-like cases (n = 256)

| Outcome | v1 | v2 (baseline) | v3 (now) |
|---|---|---|---|
| Sent to an engineer | 148 (58%) | 102 (40%) | 77 (30%) |
| Focused clarification asked | 0 (0%) | 0 (0%) | 10 (4%) |
| Other question to the supplier | 18 (7%) | 59 (23%) | 57 (22%) |
| Correct decision made alone | 88 (34%) | 94 (37%) | 111 (43%) |
| Questions the key agrees are needed | 17 (7%) | 56 (22%) | 56 (22%) |
| Questions not needed | 1 (0%) | 3 (1%) | 11 (4%) |
| Wrong decision, critical | 2 (1%) | 1 (0%) | 1 (0%) |
| Wrong decision, minor | 0 (0%) | 0 (0%) | 0 (0%) |
| Missed mandatory escalation | 0 (0%) | 0 (0%) | 0 (0%) |
| Unnecessary hand-off | 97 (38%) | 58 (23%) | 36 (14%) |
| Right action on any route | 210 (82%) | 218 (85%) | 213 (83%) |

### Datasheet requirements (n = 184)

| Outcome | v1 | v2 (baseline) | v3 (now) |
|---|---|---|---|
| Sent to an engineer | 128 (70%) | 94 (51%) | 68 (37%) |
| Focused clarification asked | 0 (0%) | 0 (0%) | 10 (5%) |
| Other question to the supplier | 10 (5%) | 44 (24%) | 43 (23%) |
| Correct decision made alone | 46 (25%) | 46 (25%) | 63 (34%) |
| Questions the key agrees are needed | 10 (5%) | 43 (23%) | 44 (24%) |
| Questions not needed | 0 (0%) | 1 (1%) | 9 (5%) |
| Wrong decision, critical | 0 (0%) | 0 (0%) | 0 (0%) |
| Wrong decision, minor | 0 (0%) | 0 (0%) | 0 (0%) |
| Missed mandatory escalation | 0 (0%) | 0 (0%) | 0 (0%) |
| Unnecessary hand-off | 87 (47%) | 54 (29%) | 30 (16%) |
| Right action on any route | 149 (81%) | 150 (82%) | 144 (78%) |

### Bid and datasheet together (n = 22)

| Outcome | v1 | v2 (baseline) | v3 (now) |
|---|---|---|---|
| Sent to an engineer | 13 (59%) | 6 (27%) | 7 (32%) |
| Focused clarification asked | 0 (0%) | 0 (0%) | 0 (0%) |
| Other question to the supplier | 2 (9%) | 3 (14%) | 2 (9%) |
| Correct decision made alone | 7 (32%) | 13 (59%) | 13 (59%) |
| Questions the key agrees are needed | 1 (5%) | 3 (14%) | 2 (9%) |
| Questions not needed | 1 (5%) | 0 (0%) | 0 (0%) |
| Wrong decision, critical | 0 (0%) | 0 (0%) | 0 (0%) |
| Wrong decision, minor | 0 (0%) | 0 (0%) | 0 (0%) |
| Missed mandatory escalation | 0 (0%) | 0 (0%) | 0 (0%) |
| Unnecessary hand-off | 7 (32%) | 4 (18%) | 6 (27%) |
| Right action on any route | 15 (68%) | 21 (95%) | 22 (100%) |

### Product links (n = 4)

| Outcome | v1 | v2 (baseline) | v3 (now) |
|---|---|---|---|
| Sent to an engineer | 0 (0%) | 0 (0%) | 0 (0%) |
| Focused clarification asked | 0 (0%) | 0 (0%) | 0 (0%) |
| Other question to the supplier | 0 (0%) | 1 (25%) | 1 (25%) |
| Correct decision made alone | 3 (75%) | 3 (75%) | 3 (75%) |
| Questions the key agrees are needed | 0 (0%) | 1 (25%) | 1 (25%) |
| Questions not needed | 0 (0%) | 0 (0%) | 0 (0%) |
| Wrong decision, critical | 1 (25%) | 0 (0%) | 0 (0%) |
| Wrong decision, minor | 0 (0%) | 0 (0%) | 0 (0%) |
| Missed mandatory escalation | 0 (0%) | 0 (0%) | 0 (0%) |
| Unnecessary hand-off | 0 (0%) | 0 (0%) | 0 (0%) |
| Right action on any route | 3 (75%) | 4 (100%) | 4 (100%) |

### Bid scope cells (n = 44)

| Outcome | v1 | v2 (baseline) | v3 (now) |
|---|---|---|---|
| Sent to an engineer | 5 (11%) | 0 (0%) | 0 (0%) |
| Focused clarification asked | 0 (0%) | 0 (0%) | 0 (0%) |
| Other question to the supplier | 6 (14%) | 11 (25%) | 11 (25%) |
| Correct decision made alone | 32 (73%) | 32 (73%) | 32 (73%) |
| Questions the key agrees are needed | 6 (14%) | 9 (20%) | 9 (20%) |
| Questions not needed | 0 (0%) | 2 (5%) | 2 (5%) |
| Wrong decision, critical | 1 (2%) | 1 (2%) | 1 (2%) |
| Wrong decision, minor | 0 (0%) | 0 (0%) | 0 (0%) |
| Missed mandatory escalation | 0 (0%) | 0 (0%) | 0 (0%) |
| Unnecessary hand-off | 3 (7%) | 0 (0%) | 0 (0%) |
| Right action on any route | 41 (93%) | 41 (93%) | 41 (93%) |

## The same 22 package cases, four ways (`python scripts/compare_package.py`)

| Variant | n | right action | to an engineer | correct decisions | questions | wrong decisions | missed escalations |
|---|---|---|---|---|---|---|---|
| datasheet only | 22 | 16 | 8 | 7 | 7 | 0 | 0 |
| datasheet only + look | 22 | 17 | 8 | 7 | 7 | 0 | 0 |
| combined (baseline) | 22 | 21 | 6 | 13 | 3 | 0 | 0 |
| improved (now) | 22 | 22 | 7 | 13 | 2 | 0 | 0 |

**Correction.** We earlier wrote that reading the supplier's bid cut engineer hand-offs from 13 to 6 compared with the datasheet alone. That compared two changes at once (the routing and the extra document). With the same routing on both sides it is **8 to 6**; the gain in right actions (16 to 21 of 22) holds. The improved version gets all 22 right (the former miss, B2 R21, called a bid's 'weather protective' a deviation) at the price of one more hand-off. These 22 cases were inspected while fixing them: a repair record.

## Fresh unseen datasheets (held-out set 5)

Multiquip EGC2000C (G10) and Kohler 2000REOZMD (G11). Decision code frozen at `3eac4a0`; answer keys committed after the freeze and before any model read the sheets; read once. Reading model **openai/gpt-oss-20b** (the `gpt-oss-120b` daily free allowance ran out part-way through G10; that partial run is kept as `examples/incomplete/G10_gpt120b_incomplete.json` and is not used). Second reader: qwen/qwen3.8-27b. Both versions ran on identical readings.

### Both sheets, frozen code (the unseen result) (n = 42)

| Outcome | v1 | v2 (baseline) | v3 (now) |
|---|---|---|---|
| Sent to an engineer | 31 (74%) | 23 (55%) | 15 (36%) |
| Focused clarification asked | 0 (0%) | 0 (0%) | 2 (5%) |
| Other question to the supplier | 2 (5%) | 10 (24%) | 10 (24%) |
| Correct decision made alone | 9 (21%) | 9 (21%) | 14 (33%) |
| Questions the key agrees are needed | 2 (5%) | 10 (24%) | 11 (26%) |
| Questions not needed | 0 (0%) | 0 (0%) | 1 (2%) |
| Wrong decision, critical | 0 (0%) | 0 (0%) | 0 (0%) |
| Wrong decision, minor | 0 (0%) | 0 (0%) | 1 (2%) |
| Missed mandatory escalation | 0 (0%) | 0 (0%) | 0 (0%) |
| Unnecessary hand-off | 25 (60%) | 17 (40%) | 11 (26%) |
| Right action on any route | 36 (86%) | 36 (86%) | 36 (86%) |

### G10 Multiquip: conditional derating, container options (n = 21)

| Outcome | v1 | v2 (baseline) | v3 (now) |
|---|---|---|---|
| Sent to an engineer | 16 (76%) | 13 (62%) | 9 (43%) |
| Focused clarification asked | 0 (0%) | 0 (0%) | 1 (5%) |
| Other question to the supplier | 0 (0%) | 3 (14%) | 3 (14%) |
| Correct decision made alone | 5 (24%) | 5 (24%) | 7 (33%) |
| Questions the key agrees are needed | 0 (0%) | 3 (14%) | 4 (19%) |
| Questions not needed | 0 (0%) | 0 (0%) | 0 (0%) |
| Wrong decision, critical | 0 (0%) | 0 (0%) | 0 (0%) |
| Wrong decision, minor | 0 (0%) | 0 (0%) | 1 (5%) |
| Missed mandatory escalation | 0 (0%) | 0 (0%) | 0 (0%) |
| Unnecessary hand-off | 11 (52%) | 8 (38%) | 6 (29%) |
| Right action on any route | 16 (76%) | 16 (76%) | 17 (81%) |

### G11 Kohler: two radiator systems, multi-page tables (n = 21)

| Outcome | v1 | v2 (baseline) | v3 (now) |
|---|---|---|---|
| Sent to an engineer | 15 (71%) | 10 (48%) | 6 (29%) |
| Focused clarification asked | 0 (0%) | 0 (0%) | 1 (5%) |
| Other question to the supplier | 2 (10%) | 7 (33%) | 7 (33%) |
| Correct decision made alone | 4 (19%) | 4 (19%) | 7 (33%) |
| Questions the key agrees are needed | 2 (10%) | 7 (33%) | 7 (33%) |
| Questions not needed | 0 (0%) | 0 (0%) | 1 (5%) |
| Wrong decision, critical | 0 (0%) | 0 (0%) | 0 (0%) |
| Wrong decision, minor | 0 (0%) | 0 (0%) | 0 (0%) |
| Missed mandatory escalation | 0 (0%) | 0 (0%) | 0 (0%) |
| Unnecessary hand-off | 14 (67%) | 9 (43%) | 5 (24%) |
| Right action on any route | 20 (95%) | 20 (95%) | 19 (90%) |

**The unseen result does not pass cleanly:** v3 added one wrong decision. G10 R08: it computed a verdict from "Max Fuel Flow 158 gal/hr" as if it were fuel consumption (the key says unclear: only the prime-power consumption is stated). Fixed afterwards with a same-quantity guard and a regression test.

### The same two sheets after the fix (a repair record, NOT an unseen result) (n = 42)

| Outcome | v1 | v2 (baseline) | v3 (now) |
|---|---|---|---|
| Sent to an engineer | 31 (74%) | 23 (55%) | 16 (38%) |
| Focused clarification asked | 0 (0%) | 0 (0%) | 2 (5%) |
| Other question to the supplier | 2 (5%) | 10 (24%) | 10 (24%) |
| Correct decision made alone | 9 (21%) | 9 (21%) | 14 (33%) |
| Questions the key agrees are needed | 2 (5%) | 10 (24%) | 11 (26%) |
| Questions not needed | 0 (0%) | 0 (0%) | 1 (2%) |
| Wrong decision, critical | 0 (0%) | 0 (0%) | 0 (0%) |
| Wrong decision, minor | 0 (0%) | 0 (0%) | 0 (0%) |
| Missed mandatory escalation | 0 (0%) | 0 (0%) | 0 (0%) |
| Unnecessary hand-off | 25 (60%) | 17 (40%) | 11 (26%) |
| Right action on any route | 36 (86%) | 36 (86%) | 36 (86%) |

## Earlier unseen sheet G9 (inspected since: now a regression case)

### Generac MD2000 (n = 21)

| Outcome | v1 | v2 (baseline) | v3 (now) |
|---|---|---|---|
| Sent to an engineer | 14 (67%) | 9 (43%) | 7 (33%) |
| Focused clarification asked | 0 (0%) | 0 (0%) | 2 (10%) |
| Other question to the supplier | 0 (0%) | 5 (24%) | 5 (24%) |
| Correct decision made alone | 6 (29%) | 6 (29%) | 7 (33%) |
| Questions the key agrees are needed | 0 (0%) | 5 (24%) | 7 (33%) |
| Questions not needed | 0 (0%) | 0 (0%) | 0 (0%) |
| Wrong decision, critical | 1 (5%) | 1 (5%) | 0 (0%) |
| Wrong decision, minor | 0 (0%) | 0 (0%) | 0 (0%) |
| Missed mandatory escalation | 0 (0%) | 0 (0%) | 0 (0%) |
| Unnecessary hand-off | 11 (52%) | 6 (29%) | 5 (24%) |
| Right action on any route | 18 (86%) | 18 (86%) | 20 (95%) |

## What changed from v2 to v3 (development set)

### Improved (19)

| Case | Key | v2 | v3 | Why |
|---|---|---|---|---|
| G1/R13 | complies | complies, engineer | complies, decide (correct decision) | the quote states 4 pole, brushless but not 2/3 pitch; the document states 2/3 pitch on page 8 ('Stator                                       |
| G1/R17 | complies | complies, engineer | complies, decide (correct decision) | computed from the quote: <=0.5 % meets <= 2 % ('Voltage regulation, no load to full load ± 0.5%') |
| G1/R18 | complies | complies, engineer | complies, decide (correct decision) | computed from the quote: <=5 % meets <= 5 % ('Total Harmonic Distortion (THDV) < 5% no load to full linear load') |
| G3/R18 | complies | unclear, engineer | complies, decide (correct decision) | computed from the quote: 2.1 % meets <= 5 % ('Total Harmonic Distortion in no-load DHT (%) 2,1') |
| G4/R05 | deviates | deviates, engineer | deviates, decide (correct decision) | offered 6-cylinder Conﬁguration Four-cycle; in-line; 6-cylinder does not meet one of: 8 cylinder, 12 cylinder, 16 cylinder; computed from th |
| G4/R13 | complies | complies, engineer | complies, decide (correct decision) | offered 4 meets == 4; computed from the quote: it states brushless, 2/3 pitch ('Design Brushless, 4-pole, drip proof, revolving ﬁeld; Stator |
| G5/R03 | complies | complies, engineer | complies, decide (correct decision) | offered 5760 kVA meets >= 3000 kVA; unit kVA is not shown in the quote; the unit is in the table heading 'skVA@30% voltage dip' (page 1) |
| G5/R17 | complies | complies, engineer | complies, decide (correct decision) | computed from the quote: <=0.25 % meets <= 2 % ('± 0.25% voltage regulation no load to full load') |
| G5/R18 | complies | complies, engineer | complies, decide (correct decision) | computed from the quote: <=5 % meets <= 5 % ('5% maximum total harmonic distortion') |
| G6/R05 | complies | complies, engineer | complies, decide (correct decision) | computed from the quote: it states 16 cylinder ('Cylinder arrangement 16V'); offered 4-Cycle Engine: type 4-Cycle meets all of: 4 cycle; off |
| G6/R06 | complies | complies, engineer | complies, decide (correct decision) | the quote states electronic but not isochronous; the document states isochronous on page 1 ('An electronic, isochronous governor delivers pr |
| G6/R08 | complies | complies, engineer | complies, decide (correct decision) | offered 134.5 gph meets <= 145 gph; unit gph is not shown in the quote; the unit is in the table heading 'Diesel, Lph (gph) at % load' (page |
| G7/R08 | complies | unclear, engineer | complies, decide (correct decision) | disputed clause inspected: the independent reader's quote is on page 3; computed from the quote: 133.6 gph meets <= 145 gph |
| G8/R05 | complies | complies, engineer | complies, decide (correct decision) | offered 16 cylinder Configuration Four Cycle; Vee; 16 Cylinder meets one of: 8 cylinder, 12 cylinder, 16 cylinder; computed from the quote:  |
| G8/R13 | complies | complies, engineer | complies, decide (correct decision) | the quote states 4 pole, brushless but not 2/3 pitch; the document states 2/3 pitch on page 2 ('Stator                                       |
| G8/R15 | unclear | unclear, engineer | unclear, ask_supplier (clarification: well-founded) | the quote states heater but not 120 v, 1 phase; not stated anywhere else in the document |
| G8/R17 | complies | complies, engineer | complies, decide (correct decision) | computed from the quote: <=0.5 % meets <= 2 % ('Voltage regulation, no load to full load ± 0.5%') |
| G8/R18 | complies | complies, engineer | complies, decide (correct decision) | computed from the quote: <=5 % meets <= 5 % ('AC waveform total harmonic distortion (THDV) < 5% no load to full linear load') |
| U1/U03 | unclear | complies, engineer | unclear, ask_supplier (clarification: well-founded) | the quote states 3 phase, 3 wire but not 480 volts; not stated anywhere else in the document; offered 60 Hz meets == 60 Hz; unit Hz is not s |

### Got worse (12)

| Case | Key | v2 | v3 | Why |
|---|---|---|---|---|
| G1/R07 | complies | complies, engineer | unclear, ask_supplier (clarification: not needed) | the quote states 24 volt but not electric starter; not stated anywhere else in the document |
| G2/R06 | complies | complies, engineer | unclear, ask_supplier (clarification: not needed) | the quote states electronic but not isochronous; not stated anywhere else in the document |
| G2/R13 | complies | complies, engineer | unclear, ask_supplier (clarification: not needed) | the quote states brushless but not 4 pole, 2/3 pitch; not stated anywhere else in the document |
| G2/R21 | unclear | deviates, engineer | unclear, engineer (unnecessary hand-off) | no value found, but the submittal mentions enclosure on page(s) [2, 5, 6]; computed from the quote: it states inside |
| G3/R06 | complies | complies, engineer | unclear, ask_supplier (clarification: not needed) | the quote states electronic but not isochronous; not stated anywhere else in the document |
| G3/R13 | complies | complies, engineer | unclear, ask_supplier (clarification: not needed) | offered 4 meets == 4; the quote states brushless but not 2/3 pitch; not stated anywhere else in the document |
| G5/R13 | complies | complies, engineer | unclear, ask_supplier (clarification: not needed) | the quote states brushless but not 4 pole, 2/3 pitch; not stated anywhere else in the document |
| G6/R13 | complies | complies, engineer | unclear, ask_supplier (clarification: not needed) | the quote states 4 pole but not brushless, 2/3 pitch; not stated anywhere else in the document |
| U1/U04 | complies | complies, engineer | unclear, ask_supplier (clarification: not needed) | the quote states vfi but not double conversion, online; not stated anywhere else in the document |
| U1/U11 | unclear | unclear, ask_supplier | unclear, engineer (unnecessary hand-off) | all offered options (VRLA; Li-ion) meet one of: valve-regulated lead-acid, vrla, lithium-ion, li-ion; but the document offers it as an optio |
| PKG/B2/R21 | unclear | deviates, engineer | unclear, engineer (unnecessary hand-off) | judgement |
| PKG/B3/R21 | unclear | unclear, ask_supplier | unclear, engineer (unnecessary hand-off) | contested |

### Changed, neither (2)

| Case | Key | v2 | v3 | Why |
|---|---|---|---|---|
| G2/R20 | unclear | unclear, engineer | deviates, engineer (justified hand-off) | no value found, but the submittal mentions water, heater, jacket on page(s) [2, 3, 4, 5]; disputed clause inspected: the independent reader' |
| G4/R09 | unclear | unclear, engineer | deviates, engineer (justified hand-off) | model judgement on verified quote: 'integral set‑mounted radiator systems'; disputed clause inspected: the independent reader's quote is on  |

## Why 77 cases still reach an engineer

| Reason | Cases | The key agrees an engineer (or a different answer) is needed | Case ids |
|---|---|---|---|
| engineering judgement (partial statements, conditions, discarded values) | 23 | 12 | G1/R11, G1/R15, G3/R21, G4/R07, G4/R15, G5/R05, G5/R09, G5/R11, G6/R03, G6/R11, G7/R04, G7/R05, G7/R06, G8/R02, G8/R07, G8/R11, U1/U05, U1/U11, U1/U15, U1/U16, PKG/B2/R21, PKG/B4/R02, PKG/B4/R21 |
| the two models disagree and the disputed clause does not settle it | 23 | 11 | G2/R03, G2/R07, G2/R11, G2/R15, G2/R19, G2/R21, G4/R11, G4/R20, G5/R02, G5/R07, G6/R01, G6/R02, G6/R07, G6/R10, G7/R09, G7/R11, G8/R09, G8/R20, U1/U01, U1/U02, U1/U09, PKG/B3/R19, PKG/B3/R21 |
| the document was not read a second time (large or scanned): absence unconfirmed | 14 | 9 | G1/R12, G1/R16, G1/R19, G1/R20, G1/R21, G3/R02, G3/R03, G3/R07, G3/R09, G3/R11, G3/R15, G3/R16, G3/R19, G3/R20 |
| the evidence is judged, not computed: a term or unit the code cannot confirm from the quote | 13 | 5 | G1/R01, G1/R02, G1/R09, G2/R04, G2/R08, G2/R14, G2/R20, G3/R01, G4/R01, G4/R02, G4/R09, G6/R09, PKG/B3/R02 |
| a derating footnote changes the rating when a fitted option applies | 2 | 2 | G2/R09, PKG/B3/R09 |
| an award or schedule decision | 2 | 2 | D-award, D-schedule |

## Every wrong decision v3 still makes

| Case | Key | v2 | v3 | Why |
|---|---|---|---|---|
| BID/B2/S2 | qualified | included, decide | included, decide (incorrect decision) |  |

