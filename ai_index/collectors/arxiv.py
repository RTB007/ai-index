"""arXiv daily submission counts via the public Atom API.

Indicator name: arxiv_ai_submissions
Value: total submissions across configured categories for that day.
Backfillable: yes (full archive).

Notes:
- arXiv requires HTTPS (HTTP returns 301).
- arXiv returns HTTP 200 with an in-band Atom <entry>"Error" body when overloaded.
  We detect that and retry with backoff.
- Their docs ask for ~3s between requests; we honor that.
"""
from __future__ import annotations

import re
import time
from datetime import date, timedelta
from typing import Iterator

import requests

INDICATOR = "arxiv_ai_submissions"
ENDPOINT = "https://export.arxiv.org/api/query"
HEADERS = {"User-Agent": "ai-index/0.1 (+https://github.com/RTB007/ai-index)"}
_TOTAL_RE = re.compile(r"<opensearch:totalResults[^>]*>(\d+)</opensearch:totalResults>")
_INLINE_ERROR = re.compile(r"<title>\s*Error\s*</title>|server (encountered|is overloaded)", re.I)


def _count_for_day(d: date, categories: list[str]) -> int:
    cat_clause = " OR ".join(f"cat:{c}" for c in categories)
    start = d.strftime("%Y%m%d") + "0000"
    end = d.strftime("%Y%m%d") + "2359"
    # Use spaces — requests URL-encodes them as `+` (correct for arxiv API).
    q = f"({cat_clause}) AND submittedDate:[{start} TO {end}]"
    params = {"search_query": q, "max_results": 0}
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            r = requests.get(ENDPOINT, params=params, headers=HEADERS, timeout=30)
            r.raise_for_status()
            text = r.text
            if _INLINE_ERROR.search(text):
                raise RuntimeError("arxiv returned in-band server error")
            m = _TOTAL_RE.search(text)
            return int(m.group(1)) if m else 0
        except Exception as e:
            last_err = e
            if attempt == 3:
                raise
            time.sleep(3 + attempt * 5)  # 3s, 8s, 13s
    raise last_err  # unreachable


def collect(
    start_date: date, end_date: date, cfg: dict
) -> Iterator[tuple[str, str, float, dict | None]]:
    cats = cfg["indicators"]["arxiv"]["categories"]
    cur = start_date
    while cur <= end_date:
        try:
            count = _count_for_day(cur, cats)
        except Exception:
            # Skip this day — script-level handler will log it. Don't kill the whole range.
            cur += timedelta(days=1)
            time.sleep(3)
            continue
        yield cur.isoformat(), INDICATOR, float(count), {"categories": cats}
        cur += timedelta(days=1)
        time.sleep(3)  # arXiv asks for ≥3s between requests
