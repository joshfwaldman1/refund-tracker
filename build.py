"""
build.py — Turn raw observations into the household ledger and write docs/data.js.

The ledger answers one question:

    Did the bigger 2026 tax refund cover what households have paid extra, in
    total since January 2025, for fuel, tariffs, and debt service?

Each leg copies its method from a published analysis rather than inventing one:

    Fuel      Brown University Climate Solutions Lab, Iran War Energy Cost
              Tracker: actual gasoline and diesel prices vs. a no-war
              counterfactual built from the pre-war price and historical
              seasonal price changes, times consumption, per Census household.
    Tariffs   Treasury customs duties collected above the pre-2025 run rate,
              total since February 2025 (Yale Budget Lab rate as cross-check).
    Debt      Federal Reserve household debt service ratio times BEA disposable
              income: the rise in annual debt service since Q4 2024, accrued
              quarter by quarter (BEA personal interest payments as the monthly
              read on the consumer-credit part; pre-war mortgage forecasts vs.
              NY Fed origination flows for new borrowers).
    Refunds   IRS Filing Season Statistics, 2026 vs. 2025 same week.

Every parameter is tagged:
    published  — a figure taken directly from an official release
    derived    — computed from published figures (formula shown)
    judgment   — an analyst choice; the sensitivity block shows what it moves

See METHODOLOGY.md for the reasoning behind each choice.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
CACHE_PATH = ROOT / "data" / "cache.json"
OUTPUT_JS = ROOT / "docs" / "data.js"
OUTPUT_JSON = ROOT / "docs" / "data.json"

# --------------------------------------------------------------------------- #
# Parameters
# --------------------------------------------------------------------------- #
PARAMS = {
    # ---- Denominator -------------------------------------------------------
    "households_millions": {
        "value": 132.0,
        "tag": "judgment",
        "source": "Census Bureau ACS 2024 (about 132M households). Brown's tracker implies "
                  "the same denominator ($100.9B / $770 per household = 131M). CPS ASEC "
                  "2025 implies ~135M; using it lowers every per-household figure ~2%.",
        "url": "https://www.census.gov/programs-surveys/acs",
    },
    # ---- Tax refunds --------------------------------------------------------
    "refund_total_2026_billion": {
        "value": 324.757, "tag": "published",
        "source": "IRS Filing Season Statistics, week ending May 8, 2026: total refunds issued.",
        "url": "https://www.irs.gov/newsroom/filing-season-statistics-for-week-ending-may-8-2026",
    },
    "refund_total_2025_billion": {
        "value": 274.979, "tag": "published",
        "source": "IRS Filing Season Statistics, same week 2025 (comparison column).",
        "url": "https://www.irs.gov/newsroom/filing-season-statistics-for-week-ending-may-8-2026",
    },
    "refund_avg_2026": {"value": 3276, "tag": "published", "source": "IRS, May 8 2026 release."},
    "refund_avg_2025": {"value": 2939, "tag": "published", "source": "IRS, May 8 2026 release."},
    "refund_count_2026_millions": {"value": 99.138, "tag": "published", "source": "IRS, May 8 2026 release."},
    "refund_as_of": {"value": "2026-05-08", "tag": "published", "source": "IRS weekly cumulative statistics end in May."},
    # ---- Gasoline (method: Brown Climate Solutions Lab) ---------------------
    "war_start": {"value": "2026-02-28", "tag": "published", "source": "Brown tracker start date."},
    "gas_anchor_week": {
        "value": "2026-02-23", "tag": "derived",
        "source": "Last EIA weekly observation before the war (pre-war price the counterfactual grows from).",
    },
    "gas_seasonal_base_years": {
        "value": [2015, 2016, 2017, 2018, 2019, 2023, 2024, 2025],
        "tag": "judgment",
        "source": "Years used for 'historical price changes' in the no-war counterfactual. "
                  "2020-2022 excluded (pandemic collapse, Ukraine spike). Brown does not "
                  "publish its base years; this is the closest transparent replication.",
        "url": "https://climate.watson.brown.edu/news/2026-09-08/us-energy-costs-iran-war",
    },
    "cex_gasoline_spend_2024": {
        "value": 2645.0, "tag": "published",
        "source": "BLS Consumer Expenditure Survey 2024: average annual spending per consumer "
                  "unit on gasoline, other fuels, and motor oil.",
        "url": "https://www.bls.gov/news.release/cesan.nr0.htm",
    },
    "avg_gas_price_2024": {
        "value": 3.30, "tag": "published",
        "source": "EIA, U.S. regular retail gasoline, 2024 annual average. Overridden by the "
                  "computed average when the cache holds a full year of 2024 weekly data.",
        "url": "https://www.eia.gov/petroleum/gasdiesel/",
    },
    "diesel_transport_gallons_billion": {
        "value": 46.5, "tag": "published",
        "source": "EIA: about 46.5 billion gallons of distillate fuel consumed by the U.S. "
                  "transportation sector per year (on-highway diesel). Brown passes all of it "
                  "through to households via freight and goods prices; so does this ledger.",
        "url": "https://www.eia.gov/tools/faqs/faq.php?id=24&t=10",
    },
    "brown_crosscheck": {
        "value": {"date": "2026-09-07", "gasoline_per_household": 422, "gasoline_billion": 55,
                  "gas_plus_diesel_per_household": 770, "gas_plus_diesel_billion": 100.9},
        "tag": "published",
        "source": "Brown Iran War Energy Cost Tracker headline figures, as reported Sept 7-8, 2026. "
                  "Shown as a cross-check; Brown's gasoline figure uses EIA total consumption "
                  "(household and commercial), this ledger uses CEX household gallons only.",
        "url": "https://iranwarcost.watson.brown.edu/",
    },
    # ---- Tariffs (Treasury receipts; Yale Budget Lab cross-check) ------------
    "tariff_start_month": {
        "value": "2025-02-28", "tag": "published",
        "source": "First month with new-term tariffs in force (China 10% on Feb 4, 2025).",
    },
    "tariff_passthrough_sensitivity": {
        "value": 0.75, "tag": "judgment",
        "source": "Share of duties borne by U.S. buyers in the sensitivity row. Cavallo, Llamas & "
                  "Vazquez (2025) find near-complete pass-through to import prices with partial, "
                  "lagged pass-through at retail; the headline uses gross collections (100%).",
        "url": "https://www.hbs.edu/faculty/Pages/item.aspx?num=67208",
    },
    "yale_household_cost_annual": {
        "value": 1100.0, "tag": "published",
        "source": "Yale Budget Lab, State of U.S. Tariffs, Aug 24 2026: estimated household cost "
                  "of all 2025-26 tariffs under current law, about $1,100 per year (average "
                  "household, price-level effect 0.7%, effective rate 11.0%).",
        "url": "https://budgetlab.yale.edu/research/state-us-tariffs",
    },
    "yale_vintage": {"value": "2026-08-24", "tag": "published", "source": "Date of the Yale estimate in use."},
    "customs_baseline_months": {
        "value": ["2024-09-30", "2024-10-31", "2024-11-30", "2024-12-31", "2025-01-31"],
        "tag": "judgment",
        "source": "Pre-2025-tariff run rate of gross customs duties (cross-check only).",
    },
    "ledger_start": {"value": "2025-01-20", "tag": "published", "source": "Inauguration Day. Totals run from here."},
    # ---- Debt service -------------------------------------------------------
    "debt_service_base_quarter": {
        "value": "2024-10-01", "tag": "judgment",
        "source": "Q4 2024, the last full quarter before the term. Debt service above this "
                  "quarter's annual dollar level counts as the increase.",
        "url": "https://www.federalreserve.gov/releases/housedebt/",
    },
    # ---- Mortgages ----------------------------------------------------------
    "originations_quarterly_billion": {
        "value": {"2026Q1": 530.0, "2026Q2": 505.0},
        "tag": "published",
        "source": "New York Fed Household Debt and Credit Report: mortgage originations, "
                  "Q1 2026 (May 12 release) and Q2 2026 (Aug 11 release). Later quarters "
                  "are nowcast at the last reported quarter's pace until published.",
        "url": "https://www.newyorkfed.org/microeconomics/hhdc",
    },
    "fixed_rate_share": {
        "value": 0.90, "tag": "judgment",
        "source": "Share of originations that are fixed-rate. MBA Weekly Applications Survey "
                  "ARM share has run 8-10% in 2026. Adjustable loans are excluded because "
                  "their rate is not locked at origination.",
        "url": "https://www.mba.org/news-and-research/research-and-economics/single-family-research/weekly-applications-survey",
    },
    "mortgage_forecast_primary": {
        "value": {"name": "MBA Mortgage Finance Forecast (pre-war, Dec 2025 / Feb 2026 vintage)",
                  "path": {"2026Q1": 6.4, "2026Q2": 6.4, "2026Q3": 6.4, "2026Q4": 6.4}},
        "tag": "published",
        "source": "MBA projected a 6.4% 30-year fixed rate in every quarter of 2026. The higher "
                  "of the two pre-war forecasts, so it produces the smaller cost (safe side).",
        "url": "https://nationalmortgageprofessional.com/news/mba-solidifies-2026-forecast",
    },
    "mortgage_forecast_alt": {
        "value": {"name": "Fannie Mae Housing Forecast (February 2026 vintage)",
                  "path": {"2026Q1": 6.1, "2026Q2": 6.1, "2026Q3": 6.0, "2026Q4": 6.0}},
        "tag": "published",
        "source": "Fannie Mae's February 2026 forecast: 6.1% in H1 2026, 6.0% through 2027.",
        "url": "https://www.fanniemae.com/media/56656/display",
    },
    "mortgage_window_start": {
        "value": "2026-03-05", "tag": "judgment",
        "source": "First Freddie Mac PMMS week after the war began. Loans originated before the "
                  "shock are not charged to it.",
    },
    "example_loan": {
        "value": 330000, "tag": "judgment",
        "source": "Illustrative loan: 80% of a roughly $410K median existing-home price (NAR).",
    },
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def parse(d: str) -> date:
    """Parse an ISO date string."""
    return datetime.strptime(d, "%Y-%m-%d").date()


def series_map(rows: list[dict]) -> dict[str, float]:
    """[{date, value}] -> {date: value}."""
    return {r["date"]: r["value"] for r in rows}


def p(name: str):
    """Shortcut for a parameter value."""
    return PARAMS[name]["value"]


def quarter_of(d: date) -> str:
    """'2026Q3' for a date."""
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def yoy_pct(rows: dict[str, float], month: str) -> float | None:
    """Year-over-year % change for a monthly {date: value} map at `month`."""
    prior = parse(month).replace(year=parse(month).year - 1).isoformat()
    if prior in rows and month in rows:
        return (rows[month] / rows[prior] - 1.0) * 100.0
    return None


def monthly_payment_per_dollar(annual_rate_pct: float, years: int = 30) -> float:
    """Level monthly payment on $1 of principal, fully amortizing."""
    r = annual_rate_pct / 100.0 / 12.0
    n = years * 12
    return r / (1.0 - (1.0 + r) ** (-n))


# --------------------------------------------------------------------------- #
# Ledger legs
# --------------------------------------------------------------------------- #
def refund_leg(households: float) -> dict:
    """The tax-refund boost: 2026 refund dollars minus 2025 refund dollars, same week."""
    total_boost_b = p("refund_total_2026_billion") - p("refund_total_2025_billion")
    return {
        "aggregate_billion": round(total_boost_b, 2),
        "per_household": round(total_boost_b * 1e9 / (households * 1e6)),
        "avg_refund_2026": p("refund_avg_2026"),
        "avg_refund_2025": p("refund_avg_2025"),
        "avg_refund_change": p("refund_avg_2026") - p("refund_avg_2025"),
        "refund_count_millions": p("refund_count_2026_millions"),
        "as_of": p("refund_as_of"),
    }


def seasonal_factors(prices: dict[str, float]) -> list[float]:
    """
    Brown-style 'historical price changes': for each base year, the price in
    each week after the last February week divided by that February price.
    Returns the mean ratio by weeks-since-anchor (index 0 = anchor week = 1.0).
    """
    ratios_by_k: dict[int, list[float]] = {}
    for year in p("gas_seasonal_base_years"):
        year_weeks = sorted(d for d in prices if d.startswith(str(year)))
        anchors = [d for d in year_weeks if d <= f"{year}-02-28"]
        if not anchors:
            continue
        anchor = anchors[-1]
        anchor_price = prices[anchor]
        after = [d for d in year_weeks if d >= anchor]
        for k, d in enumerate(after):
            ratios_by_k.setdefault(k, []).append(prices[d] / anchor_price)
    max_k = max(ratios_by_k)
    return [sum(ratios_by_k[k]) / len(ratios_by_k[k]) for k in range(max_k + 1)]


def fuel_leg(series: list[dict], households: float, gallons_per_year: float, gallons_source: str) -> dict:
    """
    Extra spending on one fuel since the war, Brown method:
    weekly gap = actual price - (pre-war price x seasonal factor);
    cost = gap x household gallons per week.
    """
    prices = series_map(series)
    gallons_per_week = gallons_per_year / 52.0

    factors = seasonal_factors(prices)
    anchor = p("gas_anchor_week")
    anchor_price = prices[anchor]
    flat_baseline = sum(prices[d] for d in prices if "2026-02-01" <= d <= anchor) / len(
        [d for d in prices if "2026-02-01" <= d <= anchor]
    )

    weeks = [d for d in sorted(prices) if d > anchor]
    cum = cum_flat = cum_yoy = 0.0
    path = []
    for k, week in enumerate(weeks, start=1):
        price = prices[week]
        counterfactual = anchor_price * factors[min(k, len(factors) - 1)]
        cum += (price - counterfactual) * gallons_per_week
        cum_flat += (price - flat_baseline) * gallons_per_week
        year_ago = parse(week).replace(year=parse(week).year - 1)
        match = [d for d in prices if abs((parse(d) - year_ago).days) <= 3]
        if match:
            cum_yoy += (price - prices[match[0]]) * gallons_per_week
        path.append({"date": week, "price": price, "counterfactual": round(counterfactual, 3),
                     "cumulative": round(cum, 2)})

    latest = path[-1]
    return {
        "per_household": round(cum),
        "aggregate_billion": round(cum * households * 1e6 / 1e9, 1),
        "per_household_flat_baseline": round(cum_flat),
        "per_household_yoy_baseline": round(cum_yoy),
        "latest_price": latest["price"],
        "latest_counterfactual": latest["counterfactual"],
        "latest_week": latest["date"],
        "premium_now": round(latest["price"] - latest["counterfactual"], 2),
        "weekly_extra_now": round((latest["price"] - latest["counterfactual"]) * gallons_per_week, 2),
        "anchor_price": anchor_price,
        "gallons_per_year": round(gallons_per_year),
        "gallons_source": gallons_source,
        "weeks_counted": len(weeks),
        "path": path,
    }


def household_gasoline_gallons(gas: list[dict]) -> tuple[float, str]:
    """CEX 2024 gasoline dollars / 2024 average pump price."""
    prices = series_map(gas)
    weeks_2024 = [v for d, v in prices.items() if d.startswith("2024")]
    if len(weeks_2024) >= 45:
        avg = sum(weeks_2024) / len(weeks_2024)
        return p("cex_gasoline_spend_2024") / avg, f"CEX $2,645 / ${avg:.2f} 2024 average price (EIA weekly)"
    avg = p("avg_gas_price_2024")
    return p("cex_gasoline_spend_2024") / avg, f"CEX $2,645 / ${avg:.2f} EIA 2024 annual average"


def fuels_leg(gas: list[dict], diesel: list[dict], households: float) -> dict:
    """Gasoline plus diesel, each by the Brown method, combined per household."""
    gas_gal, gas_src = household_gasoline_gallons(gas)
    diesel_gal = p("diesel_transport_gallons_billion") * 1e9 / (households * 1e6)
    g = fuel_leg(gas, households, gas_gal, gas_src)
    d = fuel_leg(diesel, households, diesel_gal, "EIA transportation distillate / households")
    combined_path = []
    d_by_week = {r["date"]: r["cumulative"] for r in d["path"]}
    for r in g["path"]:
        combined_path.append({"date": r["date"], "cumulative": round(r["cumulative"] + d_by_week.get(r["date"], 0.0), 2)})
    total = g["per_household"] + d["per_household"]
    return {
        "per_household": total,
        "aggregate_billion": round(g["aggregate_billion"] + d["aggregate_billion"], 1),
        "gasoline": {k: v for k, v in g.items() if k != "path"},
        "diesel": {k: v for k, v in d.items() if k != "path"},
        "per_household_flat_baseline": g["per_household_flat_baseline"] + d["per_household_flat_baseline"],
        "per_household_yoy_baseline": g["per_household_yoy_baseline"] + d["per_household_yoy_baseline"],
        "latest_week": g["latest_week"],
        "weeks_counted": g["weeks_counted"],
        "brown": p("brown_crosscheck"),
        "path": combined_path,
    }


def tariff_leg(customs: list[dict], households: float, as_of: date) -> dict:
    """
    Total tariffs collected above the pre-2025 run rate since February 2025
    (Treasury Monthly Treasury Statement), with the current month nowcast at
    the last reported month's daily pace. Yale Budget Lab's annual per-household
    estimate is the cross-check on the run rate.
    """
    by_month = {r["date"]: r for r in customs}
    baseline = sum(by_month[m]["gross"] for m in p("customs_baseline_months")) / len(p("customs_baseline_months"))
    refund_baseline = sum(by_month[m]["refunds"] for m in p("customs_baseline_months")) / len(p("customs_baseline_months"))
    months = [r for r in customs if r["date"] >= p("tariff_start_month")]
    incremental = sum(r["gross"] - baseline for r in months)
    refunds_to_importers = sum(max(r["refunds"] - refund_baseline, 0.0) for r in months)

    last = months[-1]
    last_end = parse(last["date"])
    daily_rate = (last["gross"] - baseline) / last_end.day
    days_uncovered = max((as_of - last_end).days, 0)
    nowcast = daily_rate * days_uncovered
    total = incremental + nowcast
    months_elapsed = (as_of - parse(p("tariff_start_month")).replace(day=1)).days / 30.4375

    return {
        "per_household": round(total / (households * 1e6)),
        "aggregate_billion": round(total / 1e9, 1),
        "reported_billion": round(incremental / 1e9, 1),
        "reported_through": last["date"],
        "nowcast_days": days_uncovered,
        "nowcast_billion": round(nowcast / 1e9, 1),
        "daily_rate_per_household": round(daily_rate / (households * 1e6), 2),
        "annualized_per_household": round(daily_rate * 365 / (households * 1e6)),
        "months_elapsed": round(months_elapsed, 1),
        "baseline_monthly_billion": round(baseline / 1e9, 2),
        "refunds_to_importers_billion": round(refunds_to_importers / 1e9, 1),
        "refunds_to_importers_per_household": round(refunds_to_importers / (households * 1e6)),
        "yale_annual": p("yale_household_cost_annual"),
        "yale_vintage": p("yale_vintage"),
        "yale_accrued_2026": round(p("yale_household_cost_annual") * ((as_of - date(2026, 1, 1)).days + 1) / 365),
        "monthly": [
            {"month": r["date"][:7], "gross_billion": round(r["gross"] / 1e9, 2),
             "refunds_billion": round(r["refunds"] / 1e9, 2),
             "incremental_billion": round((r["gross"] - baseline) / 1e9, 2)}
            for r in customs if r["date"] >= "2025-01-01"
        ],
    }


def debt_service_leg(cache: dict, households: float, as_of: date) -> dict:
    """
    Increase in household debt service since Q4 2024, in dollars.

    Annual debt service ($) for a quarter = Fed debt service ratio (% of DPI)
    x that quarter's average disposable personal income (BEA, SAAR). The rise
    above the Q4 2024 level, divided by four, is the extra paid in that
    quarter; quarters after the last published ratio use the last ratio with
    the latest DPI. Mortgage and consumer pieces come from MDSP and CDSP.
    BEA personal interest payments (monthly) give a fresher read on the
    consumer-credit part alone.
    """
    tdsp, mdsp, cdsp = series_map(cache["TDSP"]), series_map(cache["MDSP"]), series_map(cache["CDSP"])
    dpi = series_map(cache["DSPI"])

    def quarter_dpi(qstart: str) -> float:
        start = parse(qstart)
        vals = [v for d, v in dpi.items() if parse(d).year == start.year and (parse(d).month - 1) // 3 == (start.month - 1) // 3]
        return sum(vals) / len(vals) if vals else max(dpi.values())

    base_q = p("debt_service_base_quarter")
    base_total = tdsp[base_q] / 100 * quarter_dpi(base_q) * 1e9
    base_mort = mdsp[base_q] / 100 * quarter_dpi(base_q) * 1e9
    base_cons = cdsp[base_q] / 100 * quarter_dpi(base_q) * 1e9

    last_q = sorted(tdsp)[-1]
    quarters = []
    q = parse(base_q)
    q = date(q.year + (q.month + 3 > 12), (q.month + 3 - 1) % 12 + 1, 1)  # next quarter
    cumulative = cumulative_mort = cumulative_cons = cumulative_ratio_only = 0.0
    ratio_only_mort = ratio_only_cons = 0.0
    base_income = quarter_dpi(base_q)
    while q <= as_of:
        qs = q.isoformat()
        published = qs in tdsp
        ratio_t, ratio_m, ratio_c = (tdsp[qs], mdsp[qs], cdsp[qs]) if published else (tdsp[last_q], mdsp[last_q], cdsp[last_q])
        income = quarter_dpi(qs)
        annual_t, annual_m, annual_c = (ratio_t / 100 * income * 1e9, ratio_m / 100 * income * 1e9, ratio_c / 100 * income * 1e9)
        q_end = date(q.year + (q.month + 3 > 12), (q.month + 3 - 1) % 12 + 1, 1) - timedelta(days=1)
        share = 1.0 if q_end <= as_of else ((as_of - q).days + 1) / ((q_end - q).days + 1)
        cumulative += (annual_t - base_total) / 4 * share
        cumulative_mort += (annual_m - base_mort) / 4 * share
        cumulative_cons += (annual_c - base_cons) / 4 * share
        # Ratio change only: holds income at the Q4 2024 level, so income growth is not counted.
        cumulative_ratio_only += (ratio_t - tdsp[base_q]) / 100 * base_income * 1e9 / 4 * share
        ratio_only_mort += (ratio_m - mdsp[base_q]) / 100 * base_income * 1e9 / 4 * share
        ratio_only_cons += (ratio_c - cdsp[base_q]) / 100 * base_income * 1e9 / 4 * share
        quarters.append({"quarter": f"{q.year}Q{(q.month - 1) // 3 + 1}", "published": published,
                         "ratio": round(ratio_t, 2), "annual_billion": round(annual_t / 1e9, 1),
                         "increase_annual_billion": round((annual_t - base_total) / 1e9, 1),
                         "ratio_only_increase_annual_billion": round((ratio_t - tdsp[base_q]) / 100 * base_income, 1),
                         "share_elapsed": round(share, 2)})
        q = date(q.year + (q.month + 3 > 12), (q.month + 3 - 1) % 12 + 1, 1)

    latest_annual_increase = quarters[-1]["increase_annual_billion"]
    latest_pub = [r for r in quarters if r["published"]][-1]
    interest = series_map(cache["B069RC1"])
    int_base = interest[sorted(d for d in interest if d <= "2024-12-01")[-1]]
    int_latest_d = sorted(interest)[-1]

    return {
        "per_household": round(cumulative / (households * 1e6)),
        "aggregate_billion": round(cumulative / 1e9, 1),
        "ratio_only_per_household": round(cumulative_ratio_only / (households * 1e6)),
        "ratio_only_billion": round(cumulative_ratio_only / 1e9, 1),
        "mortgage_ratio_only_per_household": round(ratio_only_mort / (households * 1e6)),
        "consumer_ratio_only_per_household": round(ratio_only_cons / (households * 1e6)),
        "ratio_only_annual_billion": round((tdsp[last_q] - tdsp[base_q]) / 100 * base_income, 1),
        "mortgage_ratio_only_annual_billion": round((mdsp[last_q] - mdsp[base_q]) / 100 * base_income, 1),
        "mortgage_per_household": round(cumulative_mort / (households * 1e6)),
        "consumer_per_household": round(cumulative_cons / (households * 1e6)),
        "annual_increase_billion": latest_annual_increase,
        "annual_increase_per_household": round(latest_annual_increase * 1e9 / (households * 1e6)),
        "latest_published_quarter": latest_pub["quarter"],
        "latest_published_increase_billion": latest_pub["increase_annual_billion"],
        "ratio_base": round(tdsp[base_q], 2),
        "ratio_latest": round(tdsp[last_q], 2),
        "mortgage_ratio_base": round(mdsp[base_q], 2), "mortgage_ratio_latest": round(mdsp[last_q], 2),
        "consumer_ratio_base": round(cdsp[base_q], 2), "consumer_ratio_latest": round(cdsp[last_q], 2),
        "base_annual_billion": round(base_total / 1e9, 1),
        "interest_payments": {
            "base_month": "2024-12", "base_billion": int_base,
            "latest_month": int_latest_d[:7], "latest_billion": interest[int_latest_d],
            "increase_annual_billion": round(interest[int_latest_d] - int_base, 1),
            "increase_annual_per_household": round((interest[int_latest_d] - int_base) * 1e9 / (households * 1e6)),
        },
        "quarters": quarters,
    }


def mortgage_leg(rates: list[dict], households: float, as_of: date) -> dict:
    """
    Flow-based mortgage cost. For each Freddie Mac week since the war:
        gap        = actual 30-year rate - pre-war forecast for that quarter
        flow       = that quarter's originations / 13 x fixed-rate share
        extra/mo   = flow x (payment per $ at actual - payment per $ at forecast)
    'Committed' sums the extra monthly payment over all weeks (what the 2026
    cohort now pays every month); 'paid to date' accrues it since each loan closed.
    """
    rate_map = series_map(rates)
    originations = p("originations_quarterly_billion")
    last_reported_q = sorted(originations)[-1]
    fixed = p("fixed_rate_share")
    weeks = [d for d in sorted(rate_map) if d >= p("mortgage_window_start")]

    def run(path: dict[str, float]) -> dict:
        committed_monthly = paid = flow_total = 0.0
        rows = []
        for week in weeks:
            d = parse(week)
            q = quarter_of(d)
            q_volume = originations.get(q, originations[last_reported_q]) * 1e9
            flow = q_volume / 13.0 * fixed
            actual = rate_map[week]
            forecast = path.get(q, path[sorted(path)[-1]])
            extra_per_dollar = monthly_payment_per_dollar(actual) - monthly_payment_per_dollar(forecast)
            extra_monthly = flow * extra_per_dollar
            months_out = max((as_of - d).days, 0) / 30.4375
            committed_monthly += extra_monthly
            paid += extra_monthly * months_out
            flow_total += flow
            rows.append({"date": week, "rate": actual, "forecast": forecast, "gap": round(actual - forecast, 2),
                         "nowcast": q not in originations,
                         "committed_annual_billion": round(committed_monthly * 12 / 1e9, 2),
                         "paid_to_date_billion": round(paid / 1e9, 2)})
        return {
            "committed_annual_billion": round(committed_monthly * 12 / 1e9, 2),
            "paid_to_date_billion": round(paid / 1e9, 2),
            "per_household_annual": round(committed_monthly * 12 / (households * 1e6)),
            "per_household_paid": round(paid / (households * 1e6)),
            "originations_counted_billion": round(flow_total / 1e9, 1),
            "path": rows,
        }

    primary_cfg, alt_cfg = p("mortgage_forecast_primary"), p("mortgage_forecast_alt")
    primary, alt = run(primary_cfg["path"]), run(alt_cfg["path"])
    latest_week = weeks[-1]
    latest_rate = rate_map[latest_week]
    loan = p("example_loan")
    q_now = quarter_of(parse(latest_week))
    example = {
        name: {
            "forecast": cfg["path"].get(q_now, cfg["path"][sorted(cfg["path"])[-1]]),
            "extra_monthly": round(loan * (monthly_payment_per_dollar(latest_rate)
                                           - monthly_payment_per_dollar(cfg["path"].get(q_now, 6.4)))),
        }
        for name, cfg in (("primary", primary_cfg), ("alt", alt_cfg))
    }
    return {
        "per_household_annual": primary["per_household_annual"],
        "per_household_paid": primary["per_household_paid"],
        "committed_annual_billion": primary["committed_annual_billion"],
        "paid_to_date_billion": primary["paid_to_date_billion"],
        "originations_counted_billion": primary["originations_counted_billion"],
        "latest_rate": latest_rate,
        "latest_week": latest_week,
        "pre_war_low": min(v for d, v in rate_map.items() if "2026-01-01" <= d < p("mortgage_window_start")),
        "primary": {"name": primary_cfg["name"], **{k: v for k, v in primary.items() if k != "path"}},
        "alt": {"name": alt_cfg["name"], **{k: v for k, v in alt.items() if k != "path"}},
        "example_loan": loan,
        "example": example,
        "fixed_share": fixed,
        "originations": originations,
        "nowcast_quarters": sorted({quarter_of(parse(w)) for w in weeks} - set(originations)),
        "path": primary["path"],
    }


def wages_panel(ahe: list[dict], awe: list[dict], cpi: list[dict]) -> dict:
    """
    Real earnings context. NOT added to the ledger: the CPI already contains the
    gasoline and tariff price increases, so adding a real-wage loss on top of
    the gas and tariff legs would count the same dollars twice.
    """
    ahe_m, awe_m, cpi_m = series_map(ahe), series_map(awe), series_map(cpi)
    months = sorted(m for m in ahe_m if m in cpi_m and m >= "2025-01-01")
    path = []
    for m in months:
        nominal, prices = yoy_pct(ahe_m, m), yoy_pct(cpi_m, m)
        if nominal is None or prices is None:
            continue
        real = ((1 + nominal / 100) / (1 + prices / 100) - 1) * 100
        path.append({"month": m[:7], "nominal_yoy": round(nominal, 2), "cpi_yoy": round(prices, 2), "real_yoy": round(real, 2)})
    latest = path[-1]
    m = months[-1]
    weekly_now, weekly_yoy = awe_m.get(m), yoy_pct(awe_m, m)
    real_weekly = None
    if weekly_now and weekly_yoy is not None:
        real_weekly = ((1 + weekly_yoy / 100) / (1 + yoy_pct(cpi_m, m) / 100) - 1) * 100
    return {
        "latest_month": latest["month"],
        "real_hourly_yoy": latest["real_yoy"],
        "nominal_hourly_yoy": latest["nominal_yoy"],
        "cpi_yoy": latest["cpi_yoy"],
        "real_weekly_yoy": round(real_weekly, 2) if real_weekly is not None else None,
        "weekly_earnings_now": weekly_now,
        "worst_month": min(path, key=lambda r: r["real_yoy"]),
        "path": path,
    }


def weekly_ledger(fuel: dict, tariffs: dict, debt: dict, customs: list[dict], households: float, as_of: date) -> list[dict]:
    """Weekly cumulative per-household series for the chart, Mondays from Inauguration Day."""
    start = parse(p("ledger_start"))
    hh = households * 1e6

    # Tariffs: each reported month spread over its days; uncovered days at the nowcast pace.
    baseline = tariffs["baseline_monthly_billion"] * 1e9
    daily = {}
    for r in customs:
        if r["date"] < p("tariff_start_month"):
            continue
        end = parse(r["date"])
        per_day = (r["gross"] - baseline) / end.day / hh
        for n in range(1, end.day + 1):
            daily[end.replace(day=n)] = per_day
    d = parse(tariffs["reported_through"]) + timedelta(days=1)
    while d <= as_of:
        daily[d] = tariffs["daily_rate_per_household"]
        d += timedelta(days=1)

    # Debt service: each quarter's increase spread over its days.
    debt_daily = {}
    for r in debt["quarters"]:
        year, qn = int(r["quarter"][:4]), int(r["quarter"][-1])
        q0 = date(year, (qn - 1) * 3 + 1, 1)
        q1 = date(year + (qn == 4), (qn % 4) * 3 + 1, 1)
        ndays = (q1 - q0).days
        per_day = r["ratio_only_increase_annual_billion"] * 1e9 / 4 / ndays / hh
        for n in range(ndays):
            debt_daily[q0 + timedelta(days=n)] = per_day

    fuel_by_week = {r["date"]: r["cumulative"] for r in fuel["path"]}
    week = start + timedelta(days=(7 - start.weekday()) % 7)
    rows, last_fuel, tariff_cum, debt_cum, cursor = [], 0.0, 0.0, 0.0, start
    while week <= as_of:
        while cursor <= week:
            tariff_cum += daily.get(cursor, 0.0)
            debt_cum += debt_daily.get(cursor, 0.0)
            cursor += timedelta(days=1)
        match = [k for k in fuel_by_week if abs((parse(k) - week).days) <= 3]
        if match:
            last_fuel = fuel_by_week[match[0]]
        rows.append({"date": week.isoformat(), "fuel": round(last_fuel), "tariffs": round(tariff_cum), "debt": round(debt_cum)})
        week += timedelta(days=7)
    return rows


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    cache = json.loads(CACHE_PATH.read_text())
    households = p("households_millions")
    as_of = date.today()

    refunds = refund_leg(households)
    fuel = fuels_leg(cache["GASREGW"], cache["GASDESW"], households)
    tariffs = tariff_leg(cache["MTS_CUSTOMS"], households, as_of)
    debt = debt_service_leg(cache, households, as_of)
    mortgage = mortgage_leg(cache["MORTGAGE30US"], households, as_of)
    wages = wages_panel(cache["CES0500000003"], cache["CES0500000011"], cache["CPIAUCSL"])
    ledger = weekly_ledger(fuel, tariffs, debt, cache["MTS_CUSTOMS"], households, as_of)

    costs = fuel["per_household"] + tariffs["per_household"] + debt["ratio_only_per_household"]
    net = refunds["per_household"] - costs

    output = {
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "as_of": as_of.isoformat(),
        "ledger_start": p("ledger_start"),
        "households_millions": households,
        "headline": {
            "refund_boost": refunds["per_household"],
            "fuel_cost": fuel["per_household"],
            "tariff_cost": tariffs["per_household"],
            "debt_cost": debt["ratio_only_per_household"],
            "debt_cost_nominal": debt["per_household"],
            "total_cost": costs,
            "net": net,
            "cost_per_refund_dollar": round(costs / refunds["per_household"], 2),
            "aggregate": {
                "refund_boost_billion": refunds["aggregate_billion"],
                "fuel_billion": fuel["aggregate_billion"],
                "tariff_billion": tariffs["aggregate_billion"],
                "debt_billion": debt["ratio_only_billion"],
                "debt_nominal_billion": debt["aggregate_billion"],
            },
        },
        "refunds": refunds,
        "fuel": fuel,
        "tariffs": tariffs,
        "debt": debt,
        "mortgage": {k: v for k, v in mortgage.items() if k != "path"},
        "wages": wages,
        "ledger": ledger,
        "sensitivity": {
            "fuel_flat_prewar_baseline": fuel["per_household_flat_baseline"],
            "fuel_year_ago_baseline": fuel["per_household_yoy_baseline"],
            "fuel_gasoline_only": fuel["gasoline"]["per_household"],
            "fuel_brown_published": fuel["brown"]["gas_plus_diesel_per_household"],
            "tariffs_reported_months_only": round(tariffs["reported_billion"] * 1e9 / (households * 1e6)),
            "tariffs_75pct_passthrough": round(tariffs["per_household"] * p("tariff_passthrough_sensitivity")),
            "tariffs_yale_rate_2026_only": tariffs["yale_accrued_2026"],
            "debt_nominal_dollar_increase": debt["per_household"],
            "debt_mortgage_ratio_only": debt["mortgage_ratio_only_per_household"],
            "debt_consumer_ratio_only": debt["consumer_ratio_only_per_household"],
            "debt_consumer_only": debt["consumer_per_household"],
            "households_135m": {
                "refund_boost": round(refunds["aggregate_billion"] * 1e9 / 135e6),
                "tariff_cost": round(tariffs["aggregate_billion"] * 1e9 / 135e6),
            },
        },
        "freshness": {
            "fuel_latest_week": fuel["latest_week"],
            "mortgage_latest_week": mortgage["latest_week"],
            "customs_reported_through": tariffs["reported_through"],
            "debt_service_quarter": debt["latest_published_quarter"],
            "interest_payments_month": debt["interest_payments"]["latest_month"],
            "originations_reported_through": sorted(mortgage["originations"])[-1],
            "cpi_latest_month": cache["CPIAUCSL"][-1]["date"],
            "earnings_latest_month": cache["CES0500000003"][-1]["date"],
            "irs_as_of": refunds["as_of"],
            "yale_vintage": tariffs["yale_vintage"],
        },
        "params": {k: {"value": v["value"], "tag": v["tag"], "source": v["source"], "url": v.get("url")}
                   for k, v in PARAMS.items()},
    }

    OUTPUT_JSON.write_text(json.dumps(output, indent=1))
    OUTPUT_JS.write_text("window.LEDGER = " + json.dumps(output) + ";\n")

    print(f"as of {as_of}  (households: {households}M; totals since {p('ledger_start')})")
    print(f"  refund boost        +${refunds['per_household']:>6,}  (${refunds['aggregate_billion']}B)")
    print(f"  fuel since war      -${fuel['per_household']:>6,}  (${fuel['aggregate_billion']}B; gas ${fuel['gasoline']['per_household']} + diesel ${fuel['diesel']['per_household']}; Brown ${fuel['brown']['gas_plus_diesel_per_household']})")
    print(f"  tariffs since Feb25 -${tariffs['per_household']:>6,}  (${tariffs['aggregate_billion']}B incl ${tariffs['nowcast_billion']}B nowcast; run rate ${tariffs['annualized_per_household']}/yr vs Yale ${tariffs['yale_annual']})")
    print(f"  debt service        -${debt['ratio_only_per_household']:>6,}  (ratio-only ${debt['ratio_only_billion']}B; mortgage ${debt['mortgage_ratio_only_per_household']} consumer ${debt['consumer_ratio_only_per_household']}; nominal $ increase ${debt['per_household']}/hh = ${debt['aggregate_billion']}B; BEA interest +${debt['interest_payments']['increase_annual_billion']}B/yr)")
    print(f"  net                 {'-' if net < 0 else '+'}${abs(net):>6,}")
    print(f"wrote {OUTPUT_JS} and {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
