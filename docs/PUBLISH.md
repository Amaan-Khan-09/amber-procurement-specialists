# Publishing the live demo (GitHub Pages)

Inspected on `main`: there is no `.github/` folder and no workflow, so no GitHub Actions setup is needed. The site is
the committed `docs/` folder as it is: `docs/index.html` (opens the case file), `docs/demo/` (the read-only app and
`case.html`) and `docs/.nojekyll` (serve the files unprocessed).

## The setting

Repository **Settings → Pages → Build and deployment**

1. **Source:** `Deploy from a branch`
2. **Branch:** `main`, folder **`/docs`** (the list shows `None` until you pick it)
3. Press **Save**

GitHub then runs its own "pages build and deployment" job (see the **Actions** tab). After a few minutes:

| Page | Address |
|---|---|
| Opens the case file | https://amaan-khan-09.github.io/amber-procurement-specialists/ |
| One purchase, end to end | https://amaan-khan-09.github.io/amber-procurement-specialists/demo/case.html |
| The specialists (saved results) | https://amaan-khan-09.github.io/amber-procurement-specialists/demo/ |

Publish after pushing: the page shows whatever is on `main`. To check, open all three in a private window and click one
source link on the case page.

## Before publishing a change

```
python scripts/snapshot_case.py          # the case file the page shows
python scripts/eval_handoffs.py          # the measured numbers
python scripts/build_results_report.py   # docs/RESULTS.md
python scripts/build_proof.py
python scripts/build_static_demo.py      # writes docs/demo, including case.html
```

The static demo contains no keys, no manufacturer pages (only the short quoted excerpt each answer cites) and no model
calls.
