# Project Alpha (fictional test project)

All of Project Alpha is invented for testing: the owner, the site, the dates and the schedule. It is built so the real public documents in `data/specs` and `data/submittals` can be checked against it. The specs are real public guide specs, edited the way a specifier would (see `data/specs/project_alpha/EDITS.md`).

- **Facility:** Phase 1 of a 6 MW IT-load data hall, Ashburn, Virginia, USA (fictional)
- **Site conditions:** altitude 300 ft; outdoor design ambient 10 °F to 122 °F (50 °C)
- **Distribution:** 13.2 kV utility → pad-mount transformers → 480Y/277 V, 3-phase, 4-wire, 60 Hz
- **Topology:** four identical power blocks (A–D) plus one mechanical-plant generator
- **Emissions:** EPA Tier 2, stationary emergency (40 CFR 60 Subpart IIII)

## Equipment schedule (stands in for drawing E-601)

| Tag | Item | Qty | Key ratings | Spec section | Need on site |
|---|---|---|---|---|---|
| GEN-A…D | Diesel engine-generator set, outdoor sound-attenuated enclosure | 4 | 2000 kW / 2500 kVA standby at 0.8 PF, 480Y/277 V, 3-ph, 4-w, 60 Hz, 1800 rpm | 26 32 13 | 2027-10-04 |
| GEN-M | Diesel engine-generator set, outdoor enclosure (mechanical plant) | 1 | 1000 kW / 1250 kVA standby at 0.8 PF, 480Y/277 V, 3-ph, 4-w, 60 Hz | 26 32 13 | 2027-11-01 |
| UPS-A…D | Static double-conversion UPS, single module | 4 | 1200 kVA / 1200 kW, 480 V 3-ph 3-w in / 480 V 3-ph out, 60 Hz | 26 33 53 | 2027-09-06 |
| SWGR-A…D | LV metal-enclosed power circuit breaker switchgear (UL 1558) | 4 | 480Y/277 V, 4000 A main bus, 65 kA short-circuit rating | 26 23 00 | 2027-08-02 |
| TX-A…D | Pad-mount liquid-filled transformer | 4 | 3000 kVA, 13.2 kV Δ – 480Y/277 V | 26 12 19 | 2027-07-05 |

**Dates:**
- Energisation target: 2027-12-06.
- Integrated systems testing: 6 weeks before the target.
- "Need on site" = install start minus 2 weeks of float.
- **Today's date in scenarios:** 2026-12-01. Purchase orders not placed yet unless a scenario says otherwise.
