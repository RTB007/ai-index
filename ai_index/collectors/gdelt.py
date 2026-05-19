"""GDELT DOC 2.0 daily article volume.

Indicator name: gdelt_ai_volume
Value: aggregated daily article volume value from GDELT TimelineVol output.
Backfillable: yes (GDELT 2.0 starts 2015).

GDELT's API is intermittently flaky — TLS handshakes hang silently from some IPs.
We retry with bigger backoffs and a shorter connect timeout so a stuck attempt
doesn't burn the whole window.
"""
from __future__ import annotations

import time
from datetime import date, datetime, time as dtime, timedelta
from typing import Iterator

import requests

INDICATOR = "gdelt_ai_volume"
ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
HEADERS = {"User-Agent": "ai-index/0.1 (+https://github.com/RTB007/ai-index)"}
# (connect_timeout, read_timeout) — connect short so a hung TLS gets retried fast.
TIMEOUT = (10, 90)


def _fetch_chunk(query: str, start: date, end: date) -> dict | None:
    params = {
        "query": query,
        "mode": "timelinevol",
        "format": "json",
        "startdatetime": datetime.combine(start, dtime.min).strftime("%Y%m%d%H%M%S"),
        "enddatetime": datetime.combine(end, dtime.max).strftime("%Y%m%d%H%M%S"),
        "timelinesmooth": 0,
    }
    for attempt in range(5):
        try:
            r = requests.get(ENDPOINT, params=params, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            text = r.text.strip()
            if not text:
                raise RuntimeError("gdelt returned empty body")
            return r.json()
        except Exception:
            if attempt == 4:
                raise
            time.sleep(5 + attempt * 10)  # 5, 15, 25, 35s
    return None


def collect(
    start_date: date, end_date: date, cfg: dict
) -> Iterator[tuple[str, str, float, dict | None]]:
    query = cfg["indicators"]["gdelt"]["query"]
    # Chunk by 60 days — keeps response size manageable and recovers faster on flake.
    chunk = timedelta(days=60)
    cur = start_date
    while cur <= end_date:
        chunk_end = min(cur + chunk, end_date)
        try:
            data = _fetch_chunk(query, cur, chunk_end)
        except Exception:
            cur = chunk_end + timedelta(days=1)
            time.sleep(2)
            continue
        if data is None:
            cur = chunk_end + timedelta(days=1)
            continue

        # Response: {"timeline":[{"data":[{"date":"YYYYMMDDTHHMMSSZ","value":N},...]}]}
        # GDELT returns 15-min bins; sum to daily.
        daily: dict[str, float] = {}
        for series in data.get("timeline", []):
            for pt in series.get("data", []):
                raw = pt.get("date", "")
                if len(raw) >= 8:
                    d_iso = f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
                    daily[d_iso] = daily.get(d_iso, 0.0) + float(pt.get("value", 0.0))

        for d_iso in sorted(daily):
            yield d_iso, INDICATOR, daily[d_iso], {"query": query}

        cur = chunk_end + timedelta(days=1)
        time.sleep(1)
