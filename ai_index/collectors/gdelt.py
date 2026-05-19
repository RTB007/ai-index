"""GDELT DOC 2.0 daily article volume.

Indicator name: gdelt_ai_volume
Value: daily article volume percentage from GDELT TimelineVol output.
Backfillable: yes (GDELT 2.0 starts 2015).

DOC 2.0 docs: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
"""
from __future__ import annotations

import time
from datetime import date, datetime, time as dtime, timedelta
from typing import Iterator

import requests

INDICATOR = "gdelt_ai_volume"
ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"


def collect(
    start_date: date, end_date: date, cfg: dict
) -> Iterator[tuple[str, str, float, dict | None]]:
    query = cfg["indicators"]["gdelt"]["query"]
    # GDELT TimelineVol returns the whole range in one request; chunk by 6 months to stay safe.
    chunk = timedelta(days=180)
    cur = start_date
    while cur <= end_date:
        chunk_end = min(cur + chunk, end_date)
        params = {
            "query": query,
            "mode": "timelinevol",
            "format": "json",
            "startdatetime": datetime.combine(cur, dtime.min).strftime("%Y%m%d%H%M%S"),
            "enddatetime": datetime.combine(chunk_end, dtime.max).strftime("%Y%m%d%H%M%S"),
            "timelinesmooth": 0,
        }
        for attempt in range(3):
            try:
                r = requests.get(ENDPOINT, params=params, timeout=60)
                r.raise_for_status()
                data = r.json()
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2**attempt)

        # Response: {"timeline": [{"data": [{"date": "20240115T000000Z", "value": 0.123}, ...]}]}
        # Aggregate to daily (GDELT may return 15-min bins; sum per day).
        daily: dict[str, float] = {}
        for series in data.get("timeline", []):
            for pt in series.get("data", []):
                raw = pt.get("date", "")
                # Format: YYYYMMDDTHHMMSSZ
                if len(raw) >= 8:
                    d_iso = f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
                    daily[d_iso] = daily.get(d_iso, 0.0) + float(pt.get("value", 0.0))

        for d_iso in sorted(daily):
            yield d_iso, INDICATOR, daily[d_iso], {"query": query}

        cur = chunk_end + timedelta(days=1)
        time.sleep(1)
