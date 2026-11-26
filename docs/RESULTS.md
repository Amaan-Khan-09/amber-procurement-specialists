# Results

Every number comes from `python scripts/eval_handoffs.py`. All versions read the same saved model output; earlier versions' answers are the ones their own code produced (`eval/handoff_set/frozen/`), re-scored against today's keys.

* **v1**: commit 48b321c: anything under 0.70 to one queue
* **v2 original**: commit 9cd1b4e (original baseline): decided / supplier / engineer
* **v3 previous**: commit 1d14f3e: second look at the clause
* **v4 candidate**: candidate: second look on the whole evidence record, second reading of large documents

**Unresolved** is every case sent to an engineer or put to a supplier. No fixed-set case has a supplier follow-up, so no question is counted as resolved. A **wrong decision** is critical when it approves what fails or is not shown, or rejects what complies. A **missed escalation** is any case the key gives to an engineer that was decided or merely asked (tightened this round; earlier versions have none under either definition). Answer keys were written by an AI before the code they score. **No person has reviewed them yet.**

## Fixed development set (documents seen while building: a repair record, not an unseen score)

### All like-for-like cases (n = 256)

| Outcome | v1 | v2 original | v3 previous | v4 candidate |
|---|---|---|---|---|
| Sent to an engineer | 148 (58%) | 102 (40%) | 77 (30%) | 68 (27%) |
| Question to the supplier | 18 (7%) | 59 (23%) | 57 (22%) | 56 (22%) |
| Focused clarification | 0 (0%) | 0 (0%) | 10 (4%) | 3 (1%) |
| **Unresolved (engineer + any question)** | 148 (58%) | 161 (63%) | 144 (56%) | 127 (50%) |
| Correct decision made alone | 88 (34%) | 94 (37%) | 111 (43%) | 128 (50%) |
| Wrong decision, critical | 2 (1%) | 1 (0%) | 1 (0%) | 1 (0%) |
| Wrong decision, minor | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Missed mandatory escalation | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Questions the key agrees are needed | 17 (7%) | 56 (22%) | 56 (22%) | 56 (22%) |
| Questions not needed | 1 (0%) | 3 (1%) | 11 (4%) | 3 (1%) |
| Unnecessary hand-off | 97 (38%) | 58 (23%) | 36 (14%) | 31 (12%) |
| Right action on any route | 210 (82%) | 218 (85%) | 213 (83%) | 226 (88%) |

### Datasheet requirements (n = 184)

| Outcome | v1 | v2 original | v3 previous | v4 candidate |
|---|---|---|---|---|
| Sent to an engineer | 128 (70%) | 94 (51%) | 68 (37%) | 59 (32%) |
| Question to the supplier | 10 (5%) | 44 (24%) | 43 (23%) | 42 (23%) |
| Focused clarification | 0 (0%) | 0 (0%) | 10 (5%) | 3 (2%) |
| **Unresolved (engineer + any question)** | 128 (70%) | 138 (75%) | 121 (66%) | 104 (57%) |
| Correct decision made alone | 46 (25%) | 46 (25%) | 63 (34%) | 80 (43%) |
| Wrong decision, critical | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Wrong decision, minor | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Missed mandatory escalation | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Questions the key agrees are needed | 10 (5%) | 43 (23%) | 44 (24%) | 44 (24%) |
| Questions not needed | 0 (0%) | 1 (1%) | 9 (5%) | 1 (1%) |
| Unnecessary hand-off | 87 (47%) | 54 (29%) | 30 (16%) | 25 (14%) |
| Right action on any route | 149 (81%) | 150 (82%) | 144 (78%) | 157 (85%) |

### Bid and datasheet together (n = 22)

| Outcome | v1 | v2 original | v3 previous | v4 candidate |
|---|---|---|---|---|
| Sent to an engineer | 13 (59%) | 6 (27%) | 7 (32%) | 7 (32%) |
| Question to the supplier | 2 (9%) | 3 (14%) | 2 (9%) | 2 (9%) |
| Focused clarification | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| **Unresolved (engineer + any question)** | 13 (59%) | 9 (41%) | 9 (41%) | 9 (41%) |
| Correct decision made alone | 7 (32%) | 13 (59%) | 13 (59%) | 13 (59%) |
| Wrong decision, critical | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Wrong decision, minor | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Missed mandatory escalation | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Questions the key agrees are needed | 1 (5%) | 3 (14%) | 2 (9%) | 2 (9%) |
| Questions not needed | 1 (5%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Unnecessary hand-off | 7 (32%) | 4 (18%) | 6 (27%) | 6 (27%) |
| Right action on any route | 15 (68%) | 21 (95%) | 22 (100%) | 22 (100%) |

### Product links (n = 4)

| Outcome | v1 | v2 original | v3 previous | v4 candidate |
|---|---|---|---|---|
| Sent to an engineer | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Question to the supplier | 0 (0%) | 1 (25%) | 1 (25%) | 1 (25%) |
| Focused clarification | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| **Unresolved (engineer + any question)** | 0 (0%) | 1 (25%) | 1 (25%) | 1 (25%) |
| Correct decision made alone | 3 (75%) | 3 (75%) | 3 (75%) | 3 (75%) |
| Wrong decision, critical | 1 (25%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Wrong decision, minor | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Missed mandatory escalation | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Questions the key agrees are needed | 0 (0%) | 1 (25%) | 1 (25%) | 1 (25%) |
| Questions not needed | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Unnecessary hand-off | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Right action on any route | 3 (75%) | 4 (100%) | 4 (100%) | 4 (100%) |

### Bid scope cells (n = 44)

| Outcome | v1 | v2 original | v3 previous | v4 candidate |
|---|---|---|---|---|
| Sent to an engineer | 5 (11%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Question to the supplier | 6 (14%) | 11 (25%) | 11 (25%) | 11 (25%) |
| Focused clarification | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| **Unresolved (engineer + any question)** | 5 (11%) | 11 (25%) | 11 (25%) | 11 (25%) |
| Correct decision made alone | 32 (73%) | 32 (73%) | 32 (73%) | 32 (73%) |
| Wrong decision, critical | 1 (2%) | 1 (2%) | 1 (2%) | 1 (2%) |
| Wrong decision, minor | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Missed mandatory escalation | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Questions the key agrees are needed | 6 (14%) | 9 (20%) | 9 (20%) | 9 (20%) |
| Questions not needed | 0 (0%) | 2 (5%) | 2 (5%) | 2 (5%) |
| Unnecessary hand-off | 3 (7%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Right action on any route | 41 (93%) | 41 (93%) | 41 (93%) | 41 (93%) |

## The same 22 package cases with identical routing (`python scripts/compare_package.py`)

Performance **on cases we worked on**.

| Variant | n | right action | to an engineer | correct decisions | questions | wrong decisions | missed escalations |
|---|---|---|---|---|---|---|---|
| datasheet only | 22 | 16 | 8 | 7 | 7 | 0 | 0 |
| datasheet only + look | 22 | 17 | 6 | 9 | 7 | 0 | 0 |
| combined (baseline) | 22 | 21 | 6 | 13 | 3 | 0 | 0 |
| improved (now) | 22 | 22 | 7 | 13 | 2 | 0 | 0 |

## Inspected sheets, now regression material

### G9 Generac (n = 21)

| Outcome | v1 | v2 original | v3 previous | v4 candidate |
|---|---|---|---|---|
| Sent to an engineer | 14 (67%) | 9 (43%) | 7 (33%) | 7 (33%) |
| Question to the supplier | 0 (0%) | 5 (24%) | 5 (24%) | 5 (24%) |
| Focused clarification | 0 (0%) | 0 (0%) | 2 (10%) | 2 (10%) |
| **Unresolved (engineer + any question)** | 14 (67%) | 14 (67%) | 14 (67%) | 14 (67%) |
| Correct decision made alone | 6 (29%) | 6 (29%) | 7 (33%) | 7 (33%) |
| Wrong decision, critical | 1 (5%) | 1 (5%) | 0 (0%) | 0 (0%) |
| Wrong decision, minor | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Missed mandatory escalation | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Questions the key agrees are needed | 0 (0%) | 5 (24%) | 7 (33%) | 7 (33%) |
| Questions not needed | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Unnecessary hand-off | 11 (52%) | 6 (29%) | 5 (24%) | 5 (24%) |
| Right action on any route | 18 (86%) | 18 (86%) | 20 (95%) | 20 (95%) |

### G10 Multiquip and G11 Kohler (fresh last round; an error was found and fixed there) (n = 42)

| Outcome | v1 | v2 original | v3 previous | v4 candidate |
|---|---|---|---|---|
| Sent to an engineer | 31 (74%) | 23 (55%) | 16 (38%) | 13 (31%) |
| Question to the supplier | 2 (5%) | 10 (24%) | 10 (24%) | 10 (24%) |
| Focused clarification | 0 (0%) | 0 (0%) | 2 (5%) | 1 (2%) |
| **Unresolved (engineer + any question)** | 31 (74%) | 33 (79%) | 28 (67%) | 24 (57%) |
| Correct decision made alone | 9 (21%) | 9 (21%) | 14 (33%) | 18 (43%) |
| Wrong decision, critical | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Wrong decision, minor | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Missed mandatory escalation | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| Questions the key agrees are needed | 2 (5%) | 10 (24%) | 11 (26%) | 11 (26%) |
| Questions not needed | 0 (0%) | 0 (0%) | 1 (2%) | 0 (0%) |
| Unnecessary hand-off | 25 (60%) | 17 (40%) | 11 (26%) | 8 (19%) |
| Right action on any route | 36 (86%) | 36 (86%) | 36 (86%) | 37 (88%) |

## Development set: previous version to candidate

### Improved (18)

| Case | Key | v3 | v4 | Why (v4) |
|---|---|---|---|---|
| G1/R01 | complies, decide | complies, engineer (unnecessary hand-off) | complies, decide (correct decision) | offered 2000 kW meets >= 2000 kW; offered 2500 kVA meets >= 2500 kVA; unit kVA is not shown in the quote; the unit is in the table heading 'kW (kVA)'  |
| G1/R02 | complies, decide | complies, engineer (unnecessary hand-off) | complies, decide (correct decision) | offered 277/480, 3 Phase, Wye, 4 Wire Voltage - 277/480, 3 Phase, Wye, 4 Wire meets all of: 480Y/277, 3 phase, 4 wire; offered 60 Hz meets == 60 Hz; u |
| G1/R07 | complies, decide | unclear, ask_supplier (clarification: not needed) | complies, decide (correct decision) | computed from the quote: it states 24 volt, electric starter ('Engine Starter - 24 Volt DC Motor') |
| G2/R04 | complies, decide | complies, engineer (unnecessary hand-off) | complies, decide (correct decision) | two independent readings agree, and the second one's quote computes: computed from the quote: it states pmg ('Brushless, Permanent-Magnet Pilot Excite |
| G2/R06 | complies, decide | unclear, ask_supplier (clarification: not needed) | complies, decide (correct decision) | the quote states electronic but not isochronous; the document states isochronous on page 2 ('Frequency regulation, no-load to full-load        Isochro |
| G2/R13 | complies, decide | unclear, ask_supplier (clarification: not needed) | complies, decide (correct decision) | the quote states brushless but not 4 pole, 2/3 pitch; the document states 4 pole on page 3 ('Exhaust flow at rated kW,                                 |
| G2/R14 | complies, decide | complies, engineer (unnecessary hand-off) | complies, decide (correct decision) | two independent readings agree, and the second one's quote computes: computed from the quote: it states class h ('Class H, Synthetic') |
| G3/R06 | complies, decide | unclear, ask_supplier (clarification: not needed) | complies, decide (correct decision) | the quote states electronic but not isochronous; the document states isochronous on page 6 ('Frequency regulation, no-load to-full load                |
| G3/R13 | complies, decide | unclear, ask_supplier (clarification: not needed) | complies, decide (correct decision) | offered 4 meets == 4; the quote states brushless but not 2/3 pitch; the document states 2/3 pitch on page 1 ('installed per NFPA standards.            |
| G4/R01 | complies, decide | complies, engineer (unnecessary hand-off) | complies, decide (correct decision) | offered 1000 kW meets >= 1000 kW; unit kW is not shown in the quote; the unit is in the table heading 'kWe (kVA)' (page 1); offered 1250 kVA meets >=  |
| G4/R07 | complies, decide | unclear, engineer (justified hand-off) | complies, decide (correct decision) | computed from the quote: it states 24 volt, electric starter ('Starting voltage 24 V, negative ground') |
| G5/R09 | complies, engineer | unclear, engineer (justified hand-off) | complies, engineer (justified hand-off) | offered unit mounted Radiator - unit mounted meets all of: unit mounted radiator; the line is about this requirement more than the other that cited it |
| G5/R13 | complies, decide | unclear, ask_supplier (clarification: not needed) | complies, decide (correct decision) | the quote states brushless but not 4 pole, 2/3 pitch; the document states 4 pole on page 2 ('— Oil pump                                     — 4 pole,  |
| G6/R01 | complies, decide | unclear, engineer (justified hand-off) | complies, decide (correct decision) | every 480 V row of the ratings table gives 2000 kW >= 2000 (2 row(s), e.g. '277/480    3   60  2000/2500    3007     2000/2500    3007     1820/22');  |
| G6/R07 | complies, decide | complies, engineer (unnecessary hand-off) | complies, decide (correct decision) | computed from the quote: it states 24 volt, electric starter ('Starter motor rated voltage (DC) Dual, 24') |
| G6/R13 | complies, decide | unclear, ask_supplier (clarification: not needed) | complies, decide (correct decision) | the quote states 4 pole but not brushless, 2/3 pitch; the document states brushless on page 1 ('The brushless, rotating-field generator has broadrange |
| G8/R07 | complies, decide | unclear, engineer (justified hand-off) | complies, decide (correct decision) | computed from the quote: it states 24 volt, electric starter ('Starting voltage 24 volts, negative ground') |
| U1/U10 | deviates, decide | unclear, ask_supplier (supplier question: not needed) | deviates, decide (correct decision) | the document says 'Not included 600-1200 kW' and this project's rating is 1200: not included |

### Got worse (1)

| Case | Key | v3 | v4 | Why (v4) |
|---|---|---|---|---|
| G2/R20 | unclear, ask_supplier | deviates, engineer (justified hand-off) | unclear, engineer (unnecessary hand-off) | no value found, but the submittal mentions water, heater, jacket on page(s) [2, 3, 4, 5]; no value found, but the submittal mentions water, heater, ja |

### Changed, neither (0)

None.

## Why 68 development cases still reach an engineer

| Reason | Cases | Key agrees (an engineer, or a different answer, is needed) | Case ids |
|---|---|---|---|
| the two models disagree and the disputed clause does not settle it | 33 | 17 | G1/R09, G1/R16, G1/R20, G2/R03, G2/R07, G2/R11, G2/R15, G2/R19, G2/R20, G2/R21, G3/R02, G3/R07, G3/R11, G3/R15, G3/R16, G3/R19, G3/R20, G4/R11, G4/R20, G5/R02, G5/R07, G5/R09, G6/R02, G6/R10, G7/R09, G7/R11, G8/R09, G8/R20, U1/U01, U1/U02, U1/U09, PKG/B3/R19, PKG/B3/R21 |
| engineering judgement (partial or conditional statements, discarded values) | 20 | 9 | G1/R11, G1/R15, G3/R21, G4/R15, G5/R05, G5/R11, G6/R03, G6/R11, G7/R04, G7/R05, G7/R06, G8/R02, G8/R11, U1/U05, U1/U11, U1/U15, U1/U16, PKG/B2/R21, PKG/B4/R02, PKG/B4/R21 |
| judged, not computable: a term or unit the code cannot confirm | 6 | 3 | G2/R08, G3/R01, G4/R02, G4/R09, G6/R09, PKG/B3/R02 |
| large document: absence not confirmed by a whole second reading | 5 | 4 | G1/R12, G1/R19, G1/R21, G3/R03, G3/R09 |
| a derating footnote applies when a fitted option is fitted | 2 | 2 | G2/R09, PKG/B3/R09 |
| an award or schedule decision | 2 | 2 | D-award, D-schedule |

## The 14 large-document cases after the targeted second reading

The second reader read only the pages that mention each open item (`scripts/targeted_read.py`). What it quotes is used; "not found" on selected pages is **not** treated as confirmation (that rule was added after it sent one must-escalate item to the supplier).

| Case | Key | v3 | v4 | Why (v4) |
|---|---|---|---|---|
| G1/R12 | complies, decide | unclear, engineer (justified hand-off) | unclear, engineer (justified hand-off) | no value found, but the submittal mentions speed on page(s) [10, 13, 17, 18, 19, 20] |
| G1/R16 | deviates, decide | unclear, engineer (justified hand-off) | unclear, engineer (justified hand-off) | no value found, but the submittal mentions output, state, circuit on page(s) [1, 3, 5, 7, 8, 9] |
| G1/R19 | missing, ask_supplier | unclear, engineer (unnecessary hand-off) | unclear, engineer (unnecessary hand-off) | no value found, but the submittal mentions fuel, listing on page(s) [5, 8, 10, 13, 14, 15]; no value found, but the submittal mentions fuel, capacity  |
| G1/R20 | unclear, ask_supplier | unclear, engineer (unnecessary hand-off) | unclear, engineer (unnecessary hand-off) | no value found, but the submittal mentions heater, water, count on page(s) [3, 5, 8, 9, 14, 19]; no value found, but the submittal mentions heater, wa |
| G1/R21 | missing, engineer | unclear, engineer (justified hand-off) | unclear, engineer (justified hand-off) | no value found, but the submittal mentions proof, enclosure on page(s) [8, 40]; no value found, but the submittal mentions location, silencer, inside  |
| G3/R02 | complies, decide | unclear, engineer (justified hand-off) | unclear, engineer (justified hand-off) | no value found, but the submittal mentions electrical, phase, wire on page(s) [2, 5, 12, 14, 15, 16]; offered 60 Hz meets == 60 Hz |
| G3/R03 | complies, decide | unclear, engineer (justified hand-off) | unclear, engineer (justified hand-off) | no value found, but the submittal mentions motor, starting on page(s) [1, 2, 5, 6, 12, 18] |
| G3/R07 | complies, engineer | unclear, engineer (justified hand-off) | unclear, engineer (justified hand-off) | no value found, but the submittal mentions volt, electric, starter on page(s) [1, 2, 5, 6, 10, 11] |
| G3/R09 | deviates, decide | unclear, engineer (justified hand-off) | unclear, engineer (justified hand-off) | no value found, but the submittal mentions unit, radiator, mounted on page(s) [1, 2, 5, 7, 8, 9]; offered 122 °F meets >= 122 °F |
| G3/R11 | unclear, engineer | unclear, engineer (justified hand-off) | unclear, engineer (justified hand-off) | options 0 m, 1000 m offered, only some meet >= 300 ft; the selected option is not marked; no value found, but the submittal mentions temperature, rang |
| G3/R15 | unclear, ask_supplier | unclear, engineer (unnecessary hand-off) | unclear, engineer (unnecessary hand-off) | no value found, but the submittal mentions electrical, single, phase on page(s) [2, 5, 11, 12, 13, 14] |
| G3/R16 | unclear, ask_supplier | unclear, engineer (unnecessary hand-off) | unclear, engineer (unnecessary hand-off) | no value found, but the submittal mentions circuit, breaker on page(s) [1, 5, 6, 12, 15, 16]; no value found, but the submittal mentions unit, trip, s |
| G3/R19 | deviates, decide | unclear, engineer (justified hand-off) | unclear, engineer (justified hand-off) | no value found, but the submittal mentions tank, listing on page(s) [1, 2, 5, 25, 26, 27]; offered 24 h meets >= 24 h |
| G3/R20 | unclear, ask_supplier | unclear, engineer (unnecessary hand-off) | unclear, engineer (unnecessary hand-off) | no value found, but the submittal mentions heater, water, quantity on page(s) [2, 3, 6, 7, 8, 27]; no value found, but the submittal mentions power, h |

## Every wrong decision or missed escalation the candidate makes

| Case | Key | v3 | v4 | Why (v4) |
|---|---|---|---|---|
| BID/B2/S2 | qualified, ask_supplier | included, decide (incorrect decision) | included, decide (incorrect decision) |  |

