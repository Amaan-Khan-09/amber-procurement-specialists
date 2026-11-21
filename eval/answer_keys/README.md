# Labelling guide: submittal answer keys

You are the person who decides the right answers. The agent is scored against what you write here, so **label before anyone runs the agent on a case, and never change a label to match the agent.** If you later find you made a mistake, fix it, and write what changed and why in `notes`.

## What you do for each case
1. Open the Project Alpha spec (`data/specs/project_alpha/26_32_13_engine_generators_ALPHA.pdf`) and the submittal PDF named in the case file.
2. Look up the tag in `data/PROJECT_ALPHA.md` to get the scheduled kW and kVA: GEN-A is 2000 kW, GEN-M is 1000 kW.
3. For each requirement in `genset_requirements.json`, search the submittal and fill in the case file:
   - `expected`: one of the four verdicts below
   - `submittal_page`: the PDF page number as the viewer shows it, starting at 1
   - `submittal_quote`: the exact words copied from the submittal, short (under 25 words)
   - `notes`: anything tricky
4. Put your name and the date in `labeller` and `labelled_on`.

## The four verdicts
| Verdict | Use when | Example |
|---|---|---|
| `complies` | The submittal clearly states something that meets the requirement | Spec ≤1800 rpm; sheet says "1800 rpm" |
| `deviates` | The submittal clearly states something that does **not** meet it | Spec 480Y/277 V; sheet only offers 4160 V and above |
| `missing` | The submittal says nothing about it | Spec needs a 24 h sub-base tank; datasheet has no tank info |
| `unclear` | It is mentioned, but you can't tell whether it meets the requirement without asking the vendor | Several voltage options are listed and the selected one isn't marked |

**Rules of thumb**
- A datasheet that offers many options (voltages, alternators, tanks) complies only if the **selected** option is marked. If nothing is marked, the verdict is `unclear`.
- Check units carefully: kW vs kVA, °C vs °F, L/h vs gph (1 gph = 3.785 L/h).
- Standby vs prime rating matter. The spec asks for the **standby** rating.
- Scanned pages count. If the answer is only on a scanned page, still label it, and add `"scanned": true`.
- Takes about 30–45 minutes per case. Do the `dev` cases first.
