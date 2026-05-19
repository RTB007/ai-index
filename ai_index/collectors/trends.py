"""Google Trends daily interest via pytrends.

Indicator name: trends_ai_composite
Value: mean of the daily 0-100 interest scores across configured keywords.
Backfillable: yes, up to 5 years (Google returns daily granularity for windows up to ~9 months;
longer windows return weekly, so we chunk).
"""
from __future__ import annotations

import time
from datetime import date, timedelta
from typing import Iterator

from pytrends.request import TrendReq

INDICATOR = "trends_ai_composite"
CHUNK_DAYS = 240  # safely under Google's 9-month daily-granularity cutoff


def _fetch_chunk(
    keywords: list[str], geo: str, start: date, end: date
) -> dict[str, float]:
    pytrends = TrendReq(hl="en-US", tz=0, timeout=(10, 30))
    timeframe = f"{start.isoformat()} {end.isoformat()}"
    pytrends.build_payload(keywords, timeframe=timeframe, geo=geo)
    df = pytrends.interest_over_time()
    if df.empty:
        return {}
    if "isPartial" in df.columns:
        df = df[~df["isPartial"]]
    # Mean across keywords -> single composite series.
    composite = df[keywords].mean(axis=1)
    return {idx.date().isoformat(): float(val) for idx, val in composite.items()}


def collect(
    start_date: date, end_date: date, cfg: dict
) -> Iterator[tuple[str, str, float, dict | None]]:
    kw = cfg["indicators"]["trends"]["keywords"]
    geo = cfg["indicators"]["trends"].get("geo", "")
    cur = start_date
    while cur <= end_date:
        chunk_end = min(cur + timedelta(days=CHUNK_DAYS), end_date)
        for attempt in range(3):
            try:
                series = _fetch_chunk(kw, geo, cur, chunk_end)
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(5 * (2**attempt))
        for d_iso in sorted(series):
            yield d_iso, INDICATOR, series[d_iso], {"keywords": kw, "geo": geo}
        cur = chunk_end + timedelta(days=1)
        time.sleep(2)
