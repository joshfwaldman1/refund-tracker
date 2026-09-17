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
from pathlib import Path

CACHE_PATH = Path(__file__).parent / "data" / "cache.json"
FRED_SERIES = ["GASREGW", "CPIAUCSL", "CES0500000003", "CES0500000011", "MORTGAGE30US"]
HEADERS = {"User-Agent": "refund-ledger/1.0 (public data tracker)"}

socket.setdefaulttimeout(30)


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
        try:
            observations = fetch_fred(series_id)
            if len(observations) < 10:
                raise ValueError(f"only {len(observations)} observations returned")
            cache[series_id] = observations
            print(f"  {series_id:<14} ok  latest {observations[-1]['date']}")
        except Exception as error:  # noqa: BLE001 — best-effort by design
            failures.append(series_id)
            print(f"  {series_id:<14} FAILED ({error}); keeping cached copy")

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
