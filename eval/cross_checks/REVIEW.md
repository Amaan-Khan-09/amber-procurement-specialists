# Review packet: are the answer keys right?

The answer keys were written by the project author, with AI assistance. A model of a different family (`qwen3.8-27b`) then labelled the same datasheets **blind**: it never saw the keys or our pipeline. This packet lists every cell where the two disagree (42 of 142) and a random sample of 12 cells where they agree. Please decide each one yourself from the datasheet, then fill `human_review.csv`.

## How to review (about 2 minutes a cell)
1. Open the datasheet named in the cell (download them with `python tools/data_prep/fetch_data.py`, or use the copies the author gave you) and go to the page given.
2. Read the requirement. Decide from the **datasheet alone**, without looking at the two labels first if you can:
   - `complies`: the datasheet clearly states something that meets it
   - `deviates`: it clearly states something that does not meet it
   - `missing`: it says nothing about it
   - `unclear`: it is mentioned (an option that is not marked as supplied, a claim without numbers) but you cannot tell whether it is met without asking the supplier
3. Rules of thumb: options (voltages, tanks, heaters, breakers) comply only if the *selected* one is marked; check units (kW and kVA are different, 1 gph = 3.785 L/h); the spec asks for *standby* ratings.
4. Write your label in `human_review.csv` (columns `human_label`, `human_note`, `reviewer_name`).

Do not change `key` or `model` columns. Your answers are used to report how often the key agrees with an independent person.

## 54 cells

### G2 R03: DISAGREE
- **Datasheet:** `kohler_KD2000_G5-626.pdf`
- **Requirement:** Motor starting capability shall be not less than 3000 kVA with a maximum voltage dip of 30% for 2000 kW sets.
- **Key says `complies`** (p.3: "480 V  KH07801TO4D  9957"). Note: 9957 kVA peak motor starting at 35% dip; spec asks >=3000 kVA at 30% dip. Different dip basis but >3x margin.
- **Blind model says `deviates`** (p.3: "480 V ... 9957")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G2 R06: DISAGREE
- **Datasheet:** `kohler_KD2000_G5-626.pdf`
- **Requirement:** Governor shall be electronic speed-sensing capable of isochronous frequency regulation from no load to full rated load.
- **Key says `complies`** (p.2: "KODEC Electronic"). Note: Electronic governor; frequency regulation no-load to full-load: Isochronous.
- **Blind model says `unclear`** (mentioned or stated without a verifiable quote)
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G2 R07: DISAGREE
- **Datasheet:** `kohler_KD2000_G5-626.pdf`
- **Requirement:** Starting system shall be 24 volt, 2-wire, negative ground, gear engaging electric starter.
- **Key says `complies`** (p.3: "Standard: 2 @ 9 kW, 24;"). Note: Two 24 V DC starter motors; negative ground.
- **Blind model says `deviates`** (p.3: "Battery voltage (DC) 12")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G2 R09: DISAGREE
- **Datasheet:** `kohler_KD2000_G5-626.pdf`
- **Requirement:** Unit-mounted radiator cooling system sized to maintain safe operation at 122°F maximum ambient temperature.
- **Key says `deviates`** (p.2: "Enclosure with enclosed silencer reduces ambient temperature"). Note: Radiator rated 50 C (122 F), but the footnote reduces it by 5 C with an enclosed silencer, which the spec requires: 45 C (113 F) < 122 F.
- **Blind model says `complies`** (p.2: "Ambient temperature, °C (°F) ... 50 (122)")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G2 R10: agreed (sample)
- **Datasheet:** `kohler_KD2000_G5-626.pdf`
- **Requirement:** Engine emissions compliance with applicable EPA Tier levels for non-road engines.
- **Key says `complies`** (p.1: "Tier 2 EPA-Certified for Stationary Emergency Applications")
- **Blind model says `complies`** (p.1: "Tier 2 EPA-Certified for Stationary Emergency Applications")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G2 R11: DISAGREE
- **Datasheet:** `kohler_KD2000_G5-626.pdf`
- **Requirement:** Operate at ambient conditions of 300 ft altitude and 10 to 122°F ambient temperature.
- **Key says `unclear`** (p.1: "complete ratings definitions, and site condition derates"). Note: Site derates deferred to TIB-101; altitude capability not stated; enclosed ambient capability below 122 F (see R09).
- **Blind model says `deviates`** (p.2: "Ambient temperature, °C (°F) ... 50 (122)")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G2 R12: agreed (sample)
- **Datasheet:** `kohler_KD2000_G5-626.pdf`
- **Requirement:** Engine speed shall not exceed 1800 rpm.
- **Key says `complies`** (p.2: "Rated rpm  1800")
- **Blind model says `complies`** (p.2: "Rated rpm ... 1800")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G2 R15: DISAGREE
- **Datasheet:** `kohler_KD2000_G5-626.pdf`
- **Requirement:** Provide a 120 V, single-phase space heater to prevent condensation in the generator.
- **Key says `unclear`** (p.4: "Generator Heater"). Note: Generator heater is a standard feature, but its voltage and phase are not stated.
- **Blind model says `complies`** (p.4: "Generator Heater")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G2 R16: agreed (sample)
- **Datasheet:** `kohler_KD2000_G5-626.pdf`
- **Requirement:** Provide 3-pole generator output circuit breaker(s) with solid-state trip units.
- **Key says `unclear`** (p.5: "Electronic Trip with Short"). Note: Electronic-trip breakers are unticked options; pole count not stated; nothing marked as selected.
- **Blind model says `unclear`** (mentioned or stated without a verifiable quote)
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G2 R19: DISAGREE
- **Datasheet:** `kohler_KD2000_G5-626.pdf`
- **Requirement:** Provide a UL 2085 listed in-skid fuel tank with usable capacity for at least 24 hours of operation at full standby load.
- **Key says `deviates`** (p.6: "tank meets UL 142 requirements"). Note: Sub-base tank is UL 142, spec requires UL 2085; tank is an unticked option and runtime not stated.
- **Blind model says `complies`** (p.1: "Fuel Tank Capacity, L (gal.) 8577-16383 (2266-4328)")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G2 R20: DISAGREE
- **Datasheet:** `kohler_KD2000_G5-626.pdf`
- **Requirement:** Provide two 5000 W, 480 V, 1-phase jacket-water heaters.
- **Key says `unclear`** (p.5: "Block Heater; 9000 W, 480 V, (Select 1 Ph or 3 Ph)"). Note: One 9000 W heater offered as an option vs two 5000 W 'or approved equal': needs engineer's judgement.
- **Blind model says `deviates`** (p.5: "Block Heater, 9000 W, 208 V, (Select 1 Ph or 3 Ph)")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G2 R21: DISAGREE
- **Datasheet:** `kohler_KD2000_G5-626.pdf`
- **Requirement:** Provide a weatherproof and rodent-proof outdoor enclosure entirely enclosing the generator set, with silencers installed inside.
- **Key says `unclear`** (p.6: "Lift base or tank-mounted, aluminum construction"). Note: Sound Level 1/2 enclosures with internal silencers are unticked options; rodent-proofing not stated.
- **Blind model says `complies`** (p.6: "aluminum construction enclosure with internal-mounted, exhaust silencers.")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G4 R02: DISAGREE
- **Datasheet:** `cummins_s-6786.pdf`
- **Requirement:** Electrical output shall be 480Y/277 volt, 3-phase, 4-wire, 60 Hz.
- **Key says `unclear`** (p.2: "255/440  •  277/480  •  347/600"). Note: 277/480 is one of several available voltages; none is marked as supplied.
- **Blind model says `complies`** (p.2: "277/480")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G4 R07: agreed (sample)
- **Datasheet:** `cummins_s-6786.pdf`
- **Requirement:** Starting system shall be remote 24 volt DC electric starter.
- **Key says `complies`** (p.2: "Starting voltage  24 V, negative ground")
- **Blind model says `complies`** (p.2: "Starting voltage 24 V, negative ground")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G4 R09: DISAGREE
- **Datasheet:** `cummins_s-6786.pdf`
- **Requirement:** Cooling system shall be unit mounted radiator cooled and maintain safe operation at 122°F maximum ambient temperature
- **Key says `unclear`** (p.2: "High ambient (40 °C) cooling system"). Note: Standard is 40 C; the 50 C (122 F) system is an option and is not marked as supplied.
- **Blind model says `deviates`** (p.2: "Standard cooling system High ambient (40 °C) cooling system")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G4 R11: DISAGREE
- **Datasheet:** `cummins_s-6786.pdf`
- **Requirement:** Operate at ambient conditions of 300 ft altitude and ambient temperature range of 10 to 122°F
- **Key says `unclear`** (p.1: "enhanced high ambient (50 °C)"). Note: Altitude and derates are not stated; ambient capability depends on the optional 50 C cooling system.
- **Blind model says `deviates`** (p.2: "Standard cooling system High ambient (40 °C) cooling system")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G4 R12: DISAGREE
- **Datasheet:** `cummins_s-6786.pdf`
- **Requirement:** Engine speed shall not exceed 1800 rpm
- **Key says `missing`**. Note: Engine speed is not stated (the only '1800' is battery amps).
- **Blind model says `complies`** (p.1: "60 Hz")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G4 R19: DISAGREE
- **Datasheet:** `cummins_s-6786.pdf`
- **Requirement:** Provide a UL 2085 listed in-skid diesel fuel tank with usable capacity for not less than 24 hours of operation at full standby load.
- **Key says `unclear`** (p.1: "Dual wall sub-base fuel tanks are also available"). Note: Optional; UL 2085 and runtime are not stated.
- **Blind model says `missing`**
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G4 R20: DISAGREE
- **Datasheet:** `cummins_s-6786.pdf`
- **Requirement:** Provide two 5000 W, 480 V single-phase jacket-water heaters.
- **Key says `unclear`** (p.2: "208 V and 240V, 1 Phase, 5 kW"). Note: 5 kW coolant heater offered at 208/240 V only (not 480 V); quantity not stated; option not marked as supplied.
- **Blind model says `deviates`** (p.2: "208 V and 240V, 1 Phase, 5 kW thermosiphon coolant heater")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G5 R01: DISAGREE
- **Datasheet:** `mtu_16V4000_DS2250_60Hz_50C.pdf`
- **Requirement:** Generator set continuous standby capacity shall meet the scheduled rating of 2000 kW and 2500 kVA at 0.8 PF.
- **Key says `complies`** (p.1: "2,250 kWe/60 Hz/Standby"). Note: 2250 kW / 2812 kVA standby at 0.8 PF at every voltage: exceeds 2000/2500.
- **Blind model says `deviates`** (p.1: "2,250 kWe/60 Hz/Standby")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G5 R07: DISAGREE
- **Datasheet:** `mtu_16V4000_DS2250_60Hz_50C.pdf`
- **Requirement:** Starting system shall be 24 volt, 2-wire, negative ground, gear engaging electric starter.
- **Key says `complies`** (p.2: "Electric starting motor - 24V")
- **Blind model says `unclear`** (mentioned or stated without a verifiable quote)
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G5 R09: DISAGREE
- **Datasheet:** `mtu_16V4000_DS2250_60Hz_50C.pdf`
- **Requirement:** Unit-mounted radiator cooling system sized to maintain safe operation at 122°F maximum ambient temperature.
- **Key says `complies`** (p.3: "Ambient capacity of radiator: °C (°F)  50 (122)"). Note: Unit-mounted radiator rated 50 C (122 F); no enclosure footnote on this sheet.
- **Blind model says `unclear`** (chunks disagree: deviates p1; complies p3)
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G5 R11: DISAGREE
- **Datasheet:** `mtu_16V4000_DS2250_60Hz_50C.pdf`
- **Requirement:** Operate at ambient conditions of 300 ft altitude and 10 to 122°F ambient temperature.
- **Key says `unclear`** (p.4: "Consult your local mtu Distributor for altitude derations"). Note: Nominal at 25 C and 300 m; altitude and temperature derates deferred to the distributor.
- **Blind model says `deviates`** (p.1: "50 °C")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G5 R14: DISAGREE
- **Datasheet:** `mtu_16V4000_DS2250_60Hz_50C.pdf`
- **Requirement:** Generator insulation shall be NEMA Class F or better.
- **Key says `missing`**. Note: Insulation class not stated (only 130 C temperature rise).
- **Blind model says `deviates`** (p.2: "130 °C standby temperature rise")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G6 R03: DISAGREE
- **Datasheet:** `kohler_2000ROZD4_spec_sheet.pdf`
- **Requirement:** Motor starting capability shall be not less than 3000 kVA with a maximum voltage dip of 30% for 2000 kW sets.
- **Key says `complies`** (p.2: "7000 (60 Hz), 6600 (50 Hz)"). Note: Peak motor starting at 35% dip: 7000 / 12500 kVA for the 480 V alternators; >2x margin over 3000 kVA at 30% dip.
- **Blind model says `unclear`** (mentioned or stated without a verifiable quote)
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G6 R07: DISAGREE
- **Datasheet:** `kohler_2000ROZD4_spec_sheet.pdf`
- **Requirement:** Starting system shall be 24 volt, 2-wire, negative ground, gear engaging electric starter.
- **Key says `complies`** (p.2: "Starter motor rated voltage (DC)  Dual, 24")
- **Blind model says `unclear`** (mentioned or stated without a verifiable quote)
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G6 R08: DISAGREE
- **Datasheet:** `kohler_2000ROZD4_spec_sheet.pdf`
- **Requirement:** Average fuel consumption at full standby load must not exceed 145 gph for a 2000 kW set.
- **Key says `complies`** (p.3: "100%  508.8(134.5)  442.9(117.0)"). Note: 60 Hz column: 134.5 gph at 100% standby <= 145.
- **Blind model says `unclear`** (chunks disagree: deviates p2; complies p3)
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G6 R09: DISAGREE
- **Datasheet:** `kohler_2000ROZD4_spec_sheet.pdf`
- **Requirement:** Unit-mounted radiator cooling system sized to maintain safe operation at 122°F maximum ambient temperature.
- **Key says `deviates`** (p.3: "Ambient temperature, C ( F)  40 (105)  50 (122)"). Note: Columns are 60 Hz | 50 Hz: the 60 Hz standard radiator is 40 C (105 F); 50 C (122 F) is the 50 Hz column.
- **Blind model says `complies`** (p.3: "Ambient temperature, C ( F) 40 (105) 50 (122)")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G6 R10: DISAGREE
- **Datasheet:** `kohler_2000ROZD4_spec_sheet.pdf`
- **Requirement:** Engine emissions compliance with applicable EPA Tier levels for non-road engines.
- **Key says `unclear`** (p.1: "engine is certified by the Environmental"). Note: EPA certified, but tier and stationary-emergency category not stated.
- **Blind model says `complies`** (p.1: "The 60 Hz generator set engine is certified by the Environmental Protection Agency (EPA).")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G6 R14: DISAGREE
- **Datasheet:** `kohler_2000ROZD4_spec_sheet.pdf`
- **Requirement:** Generator insulation shall be NEMA Class F or better.
- **Key says `complies`** (p.2: "Class H, Synthetic,")
- **Blind model says `unclear`** (mentioned or stated without a verifiable quote)
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G6 R17: DISAGREE
- **Datasheet:** `kohler_2000ROZD4_spec_sheet.pdf`
- **Requirement:** Maintain voltage regulation within plus 2% from no load to rated load.
- **Key says `complies`** (p.2: "Voltage regulation, no-load to full-load"). Note: +/-0.25% (the symbol prints as a box in the PDF text).
- **Blind model says `unclear`** (mentioned or stated without a verifiable quote)
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G6 R19: DISAGREE
- **Datasheet:** `kohler_2000ROZD4_spec_sheet.pdf`
- **Requirement:** Provide a UL 2085 listed in-skid fuel tank with usable capacity for at least 24 hours of operation at full standby load.
- **Key says `unclear`** (p.4: "Day Tanks"). Note: Only day tanks listed as an accessory: no sub-base tank, listing or runtime stated.
- **Blind model says `missing`**
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G7 R01: agreed (sample)
- **Datasheet:** `cat_3516C_2000ekW_LEHE1376.pdf`
- **Requirement:** Generator set continuous standby capacity shall meet the scheduled rating of 2000 kW and 2500 kVA at 0.8 PF.
- **Key says `complies`** (p.1: "2000 (2500) 2000 (2500) 1825 (2281) 1650 (2063)"). Note: Standby 2000 ekW / 2500 kVA at 0.8 PF (also p3, 'Genset power rating with fan').
- **Blind model says `complies`** (p.1: "Standby ... 2000 (2500)")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G7 R02: agreed (sample)
- **Datasheet:** `cat_3516C_2000ekW_LEHE1376.pdf`
- **Requirement:** Generator set output shall be 480Y/277 V, 3-phase, 4-wire, 60 Hz power.
- **Key says `unclear`** (p.2: "Output voltage"). Note: Voltage options 380 V to 13.8 kV are listed with check boxes, none marked as supplied; 60 Hz is stated (p3); phases and wires are not.
- **Blind model says `unclear`** (mentioned or stated without a verifiable quote)
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G7 R05: DISAGREE
- **Datasheet:** `cat_3516C_2000ekW_LEHE1376.pdf`
- **Requirement:** Engine shall be an 8, 12, or 16 cylinder, 4-cycle diesel engine, either turbocharged/aftercooled or normally aspirated.
- **Key says `unclear`** (p.1: "Aspiration TA"). Note: Turbocharged-aftercooled (TA) is stated; the number of cylinders and the four-cycle design are not.
- **Blind model says `complies`** (p.1: "Cat® 3516C ... Aspiration TA")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G7 R09: DISAGREE
- **Datasheet:** `cat_3516C_2000ekW_LEHE1376.pdf`
- **Requirement:** Unit-mounted radiator cooling system sized to maintain safe operation at 122°F maximum ambient temperature.
- **Key says `unclear`** (p.1: "Cooling systems available to operate in ambient temperatures up to 50"). Note: Cooling systems are 'available' for 50 C (122 F); which one is supplied is not stated.
- **Blind model says `complies`** (p.1: "Cooling systems available to operate in ambient temperatures up to 50°C (122°F)")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G7 R11: DISAGREE
- **Datasheet:** `cat_3516C_2000ekW_LEHE1376.pdf`
- **Requirement:** Operate at ambient conditions of 300 ft altitude and 10 to 122°F ambient temperature.
- **Key says `unclear`** (p.1: "Cooling systems available to operate in ambient temperatures up to 50"). Note: Ambient capability up to 50 C is mentioned as available; altitude and any derate are not stated.
- **Blind model says `deviates`** (p.1: "Cooling systems available to operate in ambient temperatures up to 50°C (122°F)")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G7 R13: DISAGREE
- **Datasheet:** `cat_3516C_2000ekW_LEHE1376.pdf`
- **Requirement:** Generator shall be 4-pole, brushless, and two-thirds pitch wound.
- **Key says `missing`**. Note: No pole count, pitch or brushless statement for the alternator.
- **Blind model says `unclear`** (mentioned or stated without a verifiable quote)
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G7 R14: DISAGREE
- **Datasheet:** `cat_3516C_2000ekW_LEHE1376.pdf`
- **Requirement:** Generator insulation shall be NEMA Class F or better.
- **Key says `missing`**. Note: Insulation class not stated (temperature-rise options only).
- **Blind model says `unclear`** (mentioned or stated without a verifiable quote)
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G8 R01: DISAGREE
- **Datasheet:** `cummins_C2000D6E_spec_sheet.pdf`
- **Requirement:** Generator set continuous standby capacity shall meet the scheduled rating of 2000 kW and 2500 kVA at 0.8 PF.
- **Key says `complies`** (p.5: "2000 kWe (2500 kVA) EMERGENCY STANDBY POWER (ESP)"). Note: Standby rating 2000 kWe / 2500 kVA; power factor 0.8 on p7.
- **Blind model says `unclear`** (chunks disagree: complies p1; deviates p5)
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G8 R07: DISAGREE
- **Datasheet:** `cummins_C2000D6E_spec_sheet.pdf`
- **Requirement:** Starting system shall be 24 volt, 2-wire, negative ground, gear engaging electric starter.
- **Key says `complies`** (p.2: "Starting voltage  24 volts, negative ground")
- **Blind model says `unclear`** (mentioned or stated without a verifiable quote)
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G8 R08: DISAGREE
- **Datasheet:** `cummins_C2000D6E_spec_sheet.pdf`
- **Requirement:** Average fuel consumption at full standby load must not exceed 145 gph for a 2000 kW set.
- **Key says `complies`** (p.5: "Fuel Consumption  US gph  41.5  75  108  139.8"). Note: 139.8 gph at 100% of 2000 kWe standby, below 145.
- **Blind model says `unclear`** (chunks disagree: complies p5; deviates p6)
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G8 R10: agreed (sample)
- **Datasheet:** `cummins_C2000D6E_spec_sheet.pdf`
- **Requirement:** Engine emissions compliance with applicable EPA Tier levels for non-road engines.
- **Key says `complies`** (p.1: "EPA TIER 2 NSPS CERTIFIED (STATIONARY EMERGENCY)")
- **Blind model says `complies`** (p.1: "EPA TIER 2 NSPS CERTIFIED")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G8 R13: agreed (sample)
- **Datasheet:** `cummins_C2000D6E_spec_sheet.pdf`
- **Requirement:** Generator shall be 4-pole, brushless, and two-thirds pitch wound.
- **Key says `complies`** (p.2: "Brushless, 4-pole, drip proof, revolving field"). Note: Stator 2/3 pitch on the next line.
- **Blind model says `complies`** (p.2: "Design Brushless, 4-pole... Stator 2/3 pitch")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G8 R14: agreed (sample)
- **Datasheet:** `cummins_C2000D6E_spec_sheet.pdf`
- **Requirement:** Generator insulation shall be NEMA Class F or better.
- **Key says `complies`** (p.2: "Insulation system  Class H")
- **Blind model says `complies`** (p.1: "class H insulation")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G8 R16: agreed (sample)
- **Datasheet:** `cummins_C2000D6E_spec_sheet.pdf`
- **Requirement:** Provide 3-pole generator output circuit breaker(s) with solid-state trip units.
- **Key says `unclear`** (p.2: "Set mounted circuit breakers up to 3200 Amps"). Note: Listed as an option; poles and trip type not stated; not marked as supplied.
- **Blind model says `unclear`** (mentioned or stated without a verifiable quote)
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### G8 R20: DISAGREE
- **Datasheet:** `cummins_C2000D6E_spec_sheet.pdf`
- **Requirement:** Provide two 5000 W, 480 V, 1-phase jacket-water heaters.
- **Key says `unclear`** (p.2: "240V thermo-statically controlled coolant"). Note: A 240 V coolant heater is listed as an option; quantity, wattage and phase not stated; not marked as supplied.
- **Blind model says `deviates`** (p.2: "240V thermo-statically controlled coolant heater")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### U1 U01: DISAGREE
- **Datasheet:** `vertiv_EXL_S1_package.pdf`
- **Requirement:** Continuous output rating shall be at least 1200 kVA and 1200 kW at unity power factor, 480 V.
- **Key says `complies`** (p.15: "1200  1200  480  1499  1574  1600"). Note: US site planning sheet lists the 1200 kVA / 1200 kW module at 480 VAC.
- **Blind model says `unclear`** (chunks disagree: complies p2; deviates p3; deviates p12; complies p15)
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### U1 U03: DISAGREE
- **Datasheet:** `vertiv_EXL_S1_package.pdf`
- **Requirement:** Input, bypass, and output electrical configuration shall be 480 V, 3-phase, 3-wire plus ground at 60 Hz.
- **Key says `unclear`** (p.12: "Nominal output voltage (V)  400 (380/415 selectable)"). Note: The package contradicts itself: the brochure (India edition) offers 400 V (380/415), 50 Hz with 60 Hz selectable and never 480 V; the US site planning sheet p15 says 480 VAC 3-wire plus ground. No configuration is marked as supplied.
- **Blind model says `deviates`** (p.12: "Nominal output voltage (V) 400 (380/415 selectable). 3Ph or 3Ph + N")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### U1 U05: DISAGREE
- **Datasheet:** `vertiv_EXL_S1_package.pdf`
- **Requirement:** Double-conversion AC-to-AC efficiency shall be at least 96% at 100% load.
- **Key says `complies`** (p.15: "≥96.3%  ≥96.3%  148502  6700"). Note: US sheet: at least 96.3% at 100% rated load; brochure says up to 97%.
- **Blind model says `unclear`** (chunks disagree: complies p2; complies p4; deviates p6; complies p12; complies p13; complies p15)
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### U1 U08: agreed (sample)
- **Datasheet:** `vertiv_EXL_S1_package.pdf`
- **Requirement:** Inverter must carry 125 percent of rated load for at least 10 minutes
- **Key says `complies`** (p.12: "110% continuous, 125% for 10mins, 150% for 1min")
- **Blind model says `complies`** (p.12: "Inverter Overload Capacity* 110% continuous, 125% for 10mins, 150% for 1min")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### U1 U10: DISAGREE
- **Datasheet:** `vertiv_EXL_S1_package.pdf`
- **Requirement:** Provide a manual maintenance bypass furnished with the UPS
- **Key says `deviates`** (p.12: "Manual Maintenance Bypass Included 300-500 kW Not included 600-1200 kW"). Note: Not included for 600-1200 kW; p17 shows the maintenance bypass panelboard 'Furnished by Others'.
- **Blind model says `unclear`** (chunks disagree: complies p4; deviates p12)
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### U1 U15: agreed (sample)
- **Datasheet:** `vertiv_EXL_S1_package.pdf`
- **Requirement:** Each UPS shall fit within a maximum width of 110 inches, depth of 40 inches, and height of 84 inches.
- **Key says `unclear`** (p.16: "104.5 x 36.0 x 79.1"). Note: The base 1200 kVA unit is 104.5 x 36.0 x 79.1 in, but installed options (back-feed disconnect, inductors) widen it up to 128.1 in and no options are marked as selected.
- **Blind model says `unclear`** (chunks disagree: deviates p12; complies p16)
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear

### U1 U16: DISAGREE
- **Datasheet:** `vertiv_EXL_S1_package.pdf`
- **Requirement:** Heat dissipation at full load shall not exceed 150,000 BTU per hour.
- **Key says `complies`** (p.15: "148502  6700"). Note: 148,502 BTU/h, just under the limit.
- **Blind model says `deviates`** (p.15: "1200 1200 480 1499 1574 1600 1443 1600 480 3110 4000 ≥96.3% ≥96.3% 148502")
- **You say:** [ ] complies  [ ] deviates  [ ] missing  [ ] unclear
