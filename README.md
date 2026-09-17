# The Refund Ledger

A live, per-household tally for calendar 2026: the bigger tax refund against
what households are paying extra for gasoline (Brown University method),
tariffs (Yale Budget Lab estimate), and higher mortgage rates (pre-war
forecasts applied to actual origination flows).

Static site in `docs/`, rebuilt daily by GitHub Actions.

## Run locally

```bash
FRED_API_KEY=... python3 fetch_data.py   # optional; falls back to cached data
python3 build.py
open docs/index.html
```

`fetch_data.py` refreshes `data/cache.json` from FRED and Treasury's Fiscal
Data API. `build.py` computes the ledger and writes `docs/data.js` and
`docs/data.json`. No dependencies beyond the Python standard library.

## Hand-updated inputs

These live in `PARAMS` at the top of `build.py`, each with its source and date:

- IRS filing-season refund totals (fixed after May)
- Yale Budget Lab per-household tariff cost and vintage
- New York Fed quarterly mortgage originations
- Brown University tracker cross-check figures
- Pre-war mortgage-rate forecasts (MBA, Fannie Mae)

See `METHODOLOGY.md` for every assumption and its tag.
