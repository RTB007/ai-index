"""HackerNews daily story count via Algolia search API.

Indicator name: hn_ai_stories
Value: number of AI-tagged stories submitted to HN that day matching the query.
Backfillable: yes, full archive (Algolia indexes all of HN).
"""
from __future__ import annotations

import time
from datetime import date, datetime, time as dtime, timezone
from typing import Iterator

import requests

INDICATOR = "hn_ai_stories"
ENDPOINT = "https://hn.algolia.com/api/v1/search"


def _day_bounds(d: date) -> tuple[int, int]:
    start = datetime.combine(d, dtime.min, tzinfo=timezone.utc)
    end = datetime.combine(d, dtime.max, tzinfo=timezone.utc)
    return int(start.timestamp()), int(end.timestamp())


def collect(
    start_date: date, end_date: date, cfg: dict
) -> Iterator[tuple[str, str, float, dict | None]]:
    query = cfg["indicators"]["hackernews"]["query"]
    cur = start_date
    while cur <= end_date:
        lo, hi = _day_bounds(cur)
        params = {
            "query": query,
            "tags": "story",
            "numericFilters": f"created_at_i>={lo},created_at_i<={hi}",
            "hitsPerPage": 0,
        }
        for attempt in range(3):
            try:
                r = requests.get(ENDPOINT, params=params, timeout=30)
                r.raise_for_status()
                count = r.json().get("nbHits", 0)
                yield cur.isoformat(), INDICATOR, float(count), {"query": query}
                break
            except Exception as e:
                if attempt == 2:
                    raise
                time.sleep(2**attempt)
        cur = date.fromordinal(cur.toordinal() + 1)
        time.sleep(0.1)  # polite
