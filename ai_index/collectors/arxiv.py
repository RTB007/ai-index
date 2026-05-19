"""arXiv daily submission counts via the public Atom API.

Indicator name: arxiv_ai_submissions
Value: total submissions across configured categories for that day.
Backfillable: yes (full archive).
"""
from __future__ import annotations

import re
import time
from datetime import date, timedelta
from typing import Iterator

import requests

INDICATOR = "arxiv_ai_submissions"
ENDPOINT = "http://export.arxiv.org/api/query"
_TOTAL_RE = re.compile(r"<opensearch:totalResults[^>]*>(\d+)</opensearch:totalResults>")


def _count_for_day(d: date, categories: list[str]) -> int:
    cat_clause = "+OR+".join(f"cat:{c}" for c in categories)
    start = d.strftime("%Y%m%d") + "0000"
    end = d.strftime("%Y%m%d") + "2359"
    q = f"({cat_clause})+AND+submittedDate:[{start}+TO+{end}]"
    params = {"search_query": q, "max_results": 0}
    for attempt in range(3):
        try:
            r = requests.get(ENDPOINT, params=params, timeout=30)
            r.raise_for_status()
            m = _TOTAL_RE.search(r.text)
            return int(m.group(1)) if m else 0
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2**attempt)
    return 0


def collect(
    start_date: date, end_date: date, cfg: dict
) -> Iterator[tuple[str, str, float, dict | None]]:
    cats = cfg["indicators"]["arxiv"]["categories"]
    cur = start_date
    while cur <= end_date:
        count = _count_for_day(cur, cats)
        yield cur.isoformat(), INDICATOR, float(count), {"categories": cats}
        cur += timedelta(days=1)
        time.sleep(3)  # arXiv asks for 3s between requests
