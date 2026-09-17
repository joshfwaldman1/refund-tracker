"""
fetch_data.py — Pull the raw series the ledger needs and refresh data/cache.json.

Sources (all public, all keyless except FRED which prefers an API key):
  * GASREGW          EIA weekly U.S. regular gasoline price, via FRED
  * CPIAUCSL         BLS CPI-U all items, SA, via FRED
  * CES0500000003    BLS average hourly earnings, total private, via FRED
  * CES0500000011    BLS average weekly earnings, total private, via FRED
  * MORTGAGE30US     Freddie Mac PMMS 30-year fixed rate, weekly, via FRED
  * MTS Table 4      Treasury Monthly Treasury Statement — customs duties
                     gross receipts, refunds, net (Fiscal Data API)

Design: every pull is best-effort. If a source is unreachable the previous
cached observations are kept, so a flaky API never blanks the site. The build
step (build.py) reports how stale each series is.

Run:  FRED_API_KEY=... python3 fetch_data.py
"""

from __future__ import annotations

import csv
import io
import json
import os
import socket
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

CACHE_PATH = Path(__file__).parent / "data" / "cache.json"
FRED_SERIES = ["GASREGW", "CPIAUCSL", "CES0500000003", "CES0500000011", "MORTGAGE30US"]
HEADERS = {"User-Agent": "refund-ledger/1.0 (public data tracker)"}

socket.setdefaulttimeout(20)


def http_get(url: str) -> str:
    """GET a URL and return the body as text."""
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request) as response:
        return response.read().decode("utf-8")


def fetch_fred(series_id: str, start: str = "2015-01-01") -> list[dict]:
    """
    Fetch one FRED series as [{date, value}], oldest first.

    Uses the JSON API when FRED_API_KEY is set, otherwise falls back to the
    keyless fredgraph CSV endpoint. Missing observations ('.') are dropped.
    """
    api_key = os.environ.get("FRED_API_KEY")
    if api_key:
        url = (
            "https://api.stlouisfed.org/fred/series/observations"
            f"?series_id={series_id}&api_key={api_key}&file_type=json"
            f"&observation_start={start}"
        )
        payload = json.loads(http_get(url))
        rows = [(o["date"], o["value"]) for o in payload["observations"]]
    else:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        reader = csv.reader(io.StringIO(http_get(url)))
        next(reader)  # header
        rows = [(r[0], r[1]) for r in reader if r[0] >= start]
    return [{"date": d, "value": float(v)} for d, v in rows if v not in (".", "")]


def fetch_freddie_pmms() -> list[dict]:
    """Keyless fallback for MORTGAGE30US: Freddie Mac's own PMMS history CSV."""
    text = http_get("https://www.freddiemac.com/pmms/docs/PMMS_history.csv")
    reader = csv.DictReader(io.StringIO(text))
    out = []
    for row in reader:
        raw_date = (row.get("date") or row.get("Date") or "").strip()
        rate = (row.get("pmms30") or row.get("PMMS30") or "").strip()
        if not raw_date or not rate:
            continue
        try:
            d = datetime.strptime(raw_date, "%m/%d/%Y").date() if "/" in raw_date else datetime.strptime(raw_date, "%Y-%m-%d").date()
            out.append({"date": d.isoformat(), "value": float(rate)})
        except ValueError:
            continue
    return [r for r in sorted(out, key=lambda r: r["date"]) if r["date"] >= "2015-01-01"]


def fetch_bls(series_id: str) -> list[dict]:
    """Keyless fallback for BLS monthly series (CPI, earnings) via the BLS API v2."""
    year = datetime.now().year
    body = json.dumps({"seriesid": [series_id], "startyear": str(year - 3), "endyear": str(year)}).encode()
    request = urllib.request.Request(
        "https://api.bls.gov/publicAPI/v2/timeseries/data/", data=body,
        headers={**HEADERS, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        payload = json.loads(response.read().decode())
    rows = payload["Results"]["series"][0]["data"]
    out = [{"date": f"{r['year']}-{r['period'][1:]}-01", "value": float(r["value"])}
           for r in rows if r["period"].startswith("M") and r["period"] != "M13"]
    return sorted(out, key=lambda r: r["date"])


def fetch_eia_gas_history() -> list[dict]:
    """Keyless fallback for GASREGW: EIA's weekly regular-gasoline history page (HTML table)."""
    import re
    html = http_get("https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=EMM_EPMR_PTE_NUS_DPG&f=W")
    out = []
    # Each row: a "YYYY Mon-DD" label then up to five "MM/DD" dates each followed by a value.
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        year_match = re.search(r"(\d{4})\s*[A-Z][a-z]{2}", re.sub(r"<[^>]+>", " ", row))
        if not year_match:
            continue
        year = int(year_match.group(1))
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        for i in range(1, len(cells) - 1, 2):
            date_cell, value_cell = cells[i], cells[i + 1]
            if re.fullmatch(r"\d{2}/\d{2}", date_cell) and re.fullmatch(r"[\d.]+", value_cell):
                month, day = date_cell.split("/")
                out.append({"date": f"{year}-{month}-{day}", "value": float(value_cell)})
    return [r for r in sorted(out, key=lambda r: r["date"]) if r["date"] >= "2015-01-01"]


# BLS ids for the FRED monthly series (CPI-U all items SA; AHE and AWE, total private).
FALLBACKS = {
    "MORTGAGE30US": fetch_freddie_pmms,
    "GASREGW": fetch_eia_gas_history,
    "CPIAUCSL": lambda: fetch_bls("CUSR0000SA0"),
    "CES0500000003": lambda: fetch_bls("CES0500000003"),
    "CES0500000011": lambda: fetch_bls("CES0500000011"),
}


def fetch_mts_customs(start: str = "2023-10-01") -> list[dict]:
    """
    Fetch monthly customs duties from the Monthly Treasury Statement, Table 4.

    Returns [{date, gross, refunds, net}] oldest first, dollars.
    """
    url = (
        "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/"
        "accounting/mts/mts_table_4"
        f"?filter=classification_desc:eq:Customs%20Duties,record_date:gte:{start}"
        "&sort=record_date&page[size]=500"
        "&fields=record_date,current_month_gross_rcpt_amt,"
        "current_month_refund_amt,current_month_net_rcpt_amt"
    )
    payload = json.loads(http_get(url))
    out = []
    for row in payload["data"]:
        gross = float(row["current_month_gross_rcpt_amt"])
        refunds = float(row["current_month_refund_amt"])
        out.append(
            {
                "date": row["record_date"],
                "gross": gross,
                "refunds": refunds,
                "net": round(gross - refunds, 2),
            }
        )
    return out


def main() -> int:
    cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}
    failures = []

    for series_id in FRED_SERIES:
        observations, used = None, "FRED"
        try:
            observations = fetch_fred(series_id)
        except Exception as error:  # noqa: BLE001 — best-effort by design
            print(f"  {series_id:<14} FRED failed ({error}); trying source fallback")
            try:
                observations, used = FALLBACKS[series_id](), "source"
            except Exception as fallback_error:  # noqa: BLE001
                print(f"  {series_id:<14} fallback failed ({fallback_error})")
        if observations and len(observations) >= 10:
            # Never let a fallback shorten history: merge into what we already hold.
            merged = {r["date"]: r for r in cache.get(series_id, [])}
            merged.update({r["date"]: r for r in observations})
            cache[series_id] = [merged[k] for k in sorted(merged)]
            print(f"  {series_id:<14} ok via {used}; latest {cache[series_id][-1]['date']}")
        else:
            failures.append(series_id)
            print(f"  {series_id:<14} FAILED; keeping cached copy")

    try:
        customs = fetch_mts_customs()
        if len(customs) < 12:
            raise ValueError(f"only {len(customs)} months returned")
        cache["MTS_CUSTOMS"] = customs
        print(f"  MTS_CUSTOMS    ok  latest {customs[-1]['date']}")
    except Exception as error:  # noqa: BLE001
        failures.append("MTS_CUSTOMS")
        print(f"  MTS_CUSTOMS    FAILED ({error}); keeping cached copy")

    cache["_note"] = (
        "Raw observations refreshed by fetch_data.py. Failed pulls keep the "
        "previous cached values; build.py reports staleness."
    )
    CACHE_PATH.write_text(json.dumps(cache, indent=1))
    print(f"wrote {CACHE_PATH} ({len(failures)} source(s) failed: {failures})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
