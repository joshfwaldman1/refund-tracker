# Methodology

The ledger answers one question for calendar 2026: **did the bigger tax refund
cover what households are paying extra for gasoline, tariffs, and higher
mortgage rates?**

Every number on the page is computed by `build.py` from `data/cache.json` plus
the `PARAMS` block at the top of that file. Each parameter carries a tag:

| Tag | Meaning |
|---|---|
| published | Taken directly from an official release or a named study |
| derived | Computed from published figures; the formula is in the code |
| judgment | An analyst choice; the sensitivity table on the page shows what it moves |

No leg invents its own model. Each copies the method of a published analysis
and cites it, so that the live number is a refresh of someone else's
defensible estimate rather than a new one.

## Unit and denominator

All headline figures are per U.S. household, with aggregate dollars alongside.
The denominator is 132 million households (Census ACS 2024; Brown's tracker
implies the same). Using the CPS ASEC 2025 figure of about 135 million lowers
every per-household number by roughly 2%.

Costs and the refund boost are both spread over all households, including
non-filers and non-drivers, so the lines are comparable. Per-recipient figures
(average refund, per-borrower mortgage payment) are shown in the panels.

## Refund boost (IRS)

Extra refund dollars = total refunds issued in the 2026 filing season minus
the same week of the 2025 season, from the IRS Filing Season Statistics
release for the week ending May 8, 2026 ($324.8B vs. $275.0B). The IRS stops
weekly cumulative reporting in May, so this line is fixed until 2027.

This is a year-over-year comparison, not a comparison to a no-tax-law
counterfactual. CBO's January 2025 baseline assumed the 2017 tax cuts expired,
so against that baseline the refund boost would be larger. The page says so.

## Gasoline (Brown University method)

Brown's Climate Solutions Lab Iran War Energy Cost Tracker describes its
method as: actual retail prices (AAA, EIA) compared each day with a no-war
counterfactual "estimated based on the pre-war price and historical daily
price changes," multiplied by EIA consumption, divided by Census households.

This ledger replicates that with EIA's weekly regular-gasoline series:

1. Anchor: the last weekly price before February 28, 2026 ($2.937, week of
   Feb 23).
2. Seasonal path: for each of eight normal years (2015–2019, 2023–2025), the
   price in each week after the last February week divided by that February
   price. The counterfactual for week *k* is the anchor times the average of
   those ratios. 2020–2022 are excluded (pandemic collapse, Ukraine spike);
   Brown does not publish its base years, so this is tagged judgment.
3. Gap × gallons: household gallons per week = BLS Consumer Expenditure Survey
   2024 spending on gasoline, other fuels, and motor oil ($2,645) divided by
   the 2024 average pump price ($3.30), divided by 52. About 800 gallons a
   year.

Brown uses total EIA consumption (household plus commercial) and includes
diesel passed through in freight; this ledger counts only household gasoline
gallons, so it runs lower than Brown's figure. Brown's published numbers are
stored as a cross-check with their date.

## Tariffs (Yale Budget Lab)

The Yale Budget Lab's State of U.S. Tariffs (August 24, 2026 vintage)
estimates the tariffs in force cost the average household about $1,100 a year
under current law. The ledger accrues that at $1,100 / 365 per day from
January 1, 2026. The accrual is live; the rate is updated by hand when Yale
publishes a new estimate (`yale_household_cost_annual` and `yale_vintage`).

Cross-check from Treasury's Monthly Treasury Statement, Table 4: gross customs
duties, refunds, and net by month. The pre-2025 run rate is the mean of
September 2024 through January 2025 ($7.66B a month). Duties collected above
that run rate in 2026 are shown per household, alongside refunds paid to
importers since the Supreme Court's February 2026 IEEPA ruling. Receipts
measure what Treasury collected, not what households paid, so they are a
cross-check rather than the headline.

Both the Yale estimate and the customs baseline are relative to tariff policy
as of January 2025, which still includes the Section 301 and 232 tariffs
carried over from the first Trump term. Neither is a zero-tariff
counterfactual.

## Mortgage rates (flow-based, pre-war forecast counterfactual)

Only households that take out a mortgage in 2026 pay the higher rate, so this
leg is built from actual origination flows rather than an average household.

For each Freddie Mac PMMS week from March 5, 2026:

- gap = actual 30-year fixed rate − the pre-war forecast for that quarter
- flow = that quarter's mortgage originations (New York Fed Household Debt and
  Credit Report: $530B in Q1, $505B in Q2; later quarters nowcast at the last
  reported pace) ÷ 13 weeks × 90% fixed-rate share (MBA weekly survey ARM
  share has run 8–10%)
- extra monthly payment = flow × (level payment per dollar at the actual rate −
  at the forecast rate), 30-year amortization

"Committed" sums the extra monthly payment across all weeks (what the 2026
cohort now pays every month, annualized). "Paid so far" accrues each week's
extra payment from the week the loans closed. Negative weeks (actual below
forecast) are allowed; they net against positive weeks.

Counterfactual paths, both pre-war:

- Primary: MBA Mortgage Finance Forecast, 6.4% in every quarter of 2026
  (December 2025 / February 2026 vintage). The higher forecast, so the smaller
  cost. Rates ran below it from March into May and above it since June.
- Alternate: Fannie Mae Housing Forecast, February 2026: 6.1% in H1, 6.0% in
  H2.

The payment-difference measure is the cash-flow cost; it is smaller than
balance × rate gap because a higher-rate loan also amortizes more slowly.

Credit cards and other revolving debt are excluded: their rates follow the
prime rate, which follows the federal funds rate, flat at 3.63% all year.

## Real earnings

Real average hourly earnings (BLS CES total private ÷ CPI-U) are shown as
context and not added to the ledger. The CPI already contains the gasoline
and tariff price increases; adding a real-wage loss to the gas and tariff
lines would count the same dollars twice.

## Freshness and failure behavior

`fetch_data.py` runs daily in GitHub Actions. Each pull is best-effort: if a
source is unreachable the previous cached observations are kept, and the page
shows the latest date for every series. Hand-updated inputs (IRS season
totals, Yale's per-household estimate, New York Fed origination volumes,
Brown's cross-check figures) live in `PARAMS` with their release dates.
