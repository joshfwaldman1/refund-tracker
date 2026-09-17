# Methodology

The ledger answers one question: **did the bigger 2026 tax refund cover what
households have paid extra, in total since January 20, 2025, for fuel,
tariffs, and debt service?**

Every number on the page is computed by `build.py` from `data/cache.json` plus
the `PARAMS` block at the top of that file. Each parameter carries a tag:

| Tag | Meaning |
|---|---|
| published | Taken directly from an official release or a named study |
| derived | Computed from published figures; the formula is in the code |
| judgment | An analyst choice; the sensitivity table on the page shows what it moves |

Each cost line is built from real, published data (Treasury, EIA, the Federal
Reserve, BEA) and cross-checked against a named outside estimate (Brown
University, the Yale Budget Lab). Nothing is modeled from scratch.

## Unit, denominator, and period

All headline figures are per U.S. household, with aggregate dollars alongside.
The denominator is 132 million households (Census ACS 2024; Brown's tracker
implies the same). The CPS ASEC 2025 figure of about 135 million lowers every
per-household number by roughly 2%.

Totals run from Inauguration Day, January 20, 2025. Fuel starts on February
28, 2026, when the war began, because that is the shock it measures. Tariffs
start in February 2025, the first month new tariffs were in force. Debt
service is measured against Q4 2024, the last full quarter before the term.

Costs and the refund boost are both spread over all households, including
non-filers and non-drivers, so the lines are comparable.

## Refund boost (IRS)

Extra refund dollars = total refunds issued in the 2026 filing season minus
the same week of the 2025 season, from the IRS Filing Season Statistics
release for the week ending May 8, 2026 ($324.8B vs. $275.0B). The 2025
season carried no tax-law change, so this is the whole refund side. The IRS
stops weekly cumulative reporting in May, so this line is fixed until 2027.

This is a year-over-year comparison, not a comparison to a no-tax-law
counterfactual. CBO's January 2025 baseline assumed the 2017 tax cuts expired,
so against that baseline the refund boost would be larger.

## Fuel: gasoline and diesel (Brown University method)

Brown's Climate Solutions Lab Iran War Energy Cost Tracker describes its
method as: actual retail prices (AAA, EIA) compared each day with a no-war
counterfactual "estimated based on the pre-war price and historical daily
price changes," multiplied by EIA consumption, divided by Census households.
Brown counts both gasoline and diesel, treating diesel as passed through to
households in freight and goods prices.

This ledger replicates that with EIA's weekly regular-gasoline and on-highway
diesel series:

1. Anchor: the last weekly price before February 28, 2026 (gasoline $2.937,
   diesel $3.809, week of Feb 23).
2. Seasonal path: for each of eight normal years (2015–2019, 2023–2025), the
   price in each week after the last February week divided by that February
   price. The counterfactual for week *k* is the anchor times the average of
   those ratios. 2020–2022 are excluded (pandemic collapse, Ukraine spike);
   Brown does not publish its base years, so this is tagged judgment.
3. Gap × gallons. Gasoline: BLS Consumer Expenditure Survey 2024 spending on
   gasoline, other fuels, and motor oil ($2,645) divided by the 2024 average
   pump price, about 800 gallons a year per household. Diesel: EIA
   transportation-sector distillate consumption, about 46.5 billion gallons a
   year, divided by households, about 350 gallons a year per household, all
   of it charged to households as Brown does.

Brown uses total EIA gasoline consumption (household plus commercial); this
ledger counts only household gasoline gallons, so it runs lower on gasoline.
Brown's published numbers are stored as a cross-check with their date.

## Tariffs (Treasury receipts; Yale Budget Lab cross-check)

Treasury's Monthly Treasury Statement, Table 4, reports gross customs duties,
refunds, and net by month. The pre-2025 run rate is the mean of September
2024 through January 2025 gross duties ($7.66B a month). The tariff line is
the sum of gross duties above that run rate from February 2025 through the
last reported month, plus the days of the current month not yet reported at
the last month's daily pace (flagged as a nowcast on the page).

Gross collections, not net, because households paid tariff-inflated prices
while the duties were in force and the refunds ordered after the Supreme
Court's February 2026 IEEPA ruling go to importers, not to households. The
refunds are shown alongside.

Collections are a border tax; who bears it is an incidence question.
Cavallo, Llamas and Vazquez (2025) find near-complete pass-through to U.S.
import prices and partial, lagged pass-through at retail. The sensitivity
table shows the line at 75%. Collections also omit two household costs that
never reach Treasury: markups on domestic goods that compete with tariffed
imports, and the deadweight loss from forgone trade. On net the headline is
a reasonable central estimate, not an upper or lower bound.

The Yale Budget Lab's State of U.S. Tariffs (August 24, 2026 vintage) puts
the cost of tariffs now in force at about $1,100 per household a year under
current law. That is shown as the cross-check on the current pace; it is
lower than the collection pace because the IEEPA tariffs are gone.

Both measures are relative to tariff policy as of January 2025, which still
includes the Section 301 and 232 tariffs carried over from the first Trump
term. Neither is a zero-tariff counterfactual.

## Debt service (Federal Reserve ratio × BEA income)

The Federal Reserve's household debt service ratio (DSR) is required mortgage
and consumer-debt payments as a share of disposable personal income,
quarterly, with mortgage (MDSP) and consumer (CDSP) components. Multiplying
the ratio by BEA disposable personal income (quarterly average of the monthly
SAAR series) gives debt service in dollars at an annual rate.

- Base: Q4 2024.
- Each quarter's extra = (that quarter's annual dollar debt service − Q4 2024's)
  ÷ 4. Quarters after the last published ratio use the last ratio against the
  latest monthly income; the current quarter is prorated by days elapsed.
- **Headline (ratio-only):** each quarter's extra = (that quarter's ratio −
  Q4 2024's ratio) × Q4 2024 income ÷ 4. Holding income at its Q4 2024 level
  removes the part of the dollar increase that comes from incomes and
  balances growing in proportion, and isolates the rate-and-mix effect.
  Mortgage and consumer pieces use MDSP and CDSP the same way. The mortgage
  ratio has risen as the stock of low-rate mortgages rolls into loans at 6%
  to 7%; the consumer-credit ratio has eased since the Fed's late-2025 cuts,
  so it enters with a negative sign.
- **Nominal (sensitivity):** each quarter's extra = (that quarter's annual
  dollar debt service − Q4 2024's) ÷ 4. This is the real increase in dollars
  households send lenders, but most of it tracks income growth at a roughly
  constant ratio, so it is shown, not headlined.

The ratio-only measure is still not a pure interest-rate effect: the DSR
also moves with the share of income going to amortization and with the mix
of borrowers. A cleaner decomposition (effective rate on outstanding balances
× balances) is possible from the Financial Accounts and NIPA interest tables
and is the natural next refinement.

BEA's monthly personal interest payments (non-mortgage interest paid by
households) are shown as the fresher monthly read on the consumer-credit
part: latest month versus December 2024, at an annual rate.

For new borrowers, the panel also shows the extra monthly payment on an
illustrative $330K mortgage at the current Freddie Mac rate versus the
pre-war MBA (6.4%) and Fannie Mae (6.0 to 6.1%) forecasts. That flow-based
calculation (forecast gap × New York Fed origination volumes) is computed in
`build.py` but is not a ledger line, because it overlaps with the debt
service line.

## What the ledger is not

- Not a causal estimate of one policy. Each line has its own stated
  counterfactual (no war; pre-2025 tariff policy; Q4 2024 debt service).
- Gross of second-round effects: no substitution, no deadweight loss, no
  general-equilibrium effects on wages, employment, or the exchange rate.
- The lines overlap at the margin: fuel and tariffs both enter the CPI, and
  the debt-service line is measured on nominal income and not deflated.
- The average household is not a typical one. Fuel and tariff burdens are
  regressive as a share of income (Yale publishes deciles); the debt-service
  line falls on households that borrowed or refinanced since 2022 and on
  revolving borrowers.
- The refund line excludes withholding changes and is measured against 2025,
  not against a counterfactual in which the 2017 cuts expired.

## Real earnings

Real average hourly earnings (BLS CES total private ÷ CPI-U) are shown as
context and not added to the ledger. The CPI already contains the fuel and
tariff price increases; adding a real-wage loss to those lines would count
the same dollars twice.

## Freshness and failure behavior

`fetch_data.py` runs daily in GitHub Actions. FRED is tried first (keyed);
gasoline, mortgage rates, CPI, and earnings have keyless fallbacks to EIA,
Freddie Mac, and the BLS API. If a source is unreachable the previous cached
observations are kept, and the page shows the latest date for every series.
Hand-updated inputs (IRS season totals, Yale's per-household estimate, New
York Fed origination volumes, Brown's cross-check figures) live in `PARAMS`
with their release dates.
