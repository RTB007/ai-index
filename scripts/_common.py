"""Shared helpers for scripts: collector dispatch + logging."""
from __future__ import annotations

import logging
import sys
from datetime import date
from typing import Iterator

from ai_index.collectors import arxiv, gdelt, gpu_spot, hackernews, stocks, trends

log = logging.getLogger("ai_index")


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )


# Map config key -> collector module. Order = run order.
# basket_signals is intentionally excluded — it has a different interface
# (reads from DB) and is driven from daily.py / backfill.py directly.
COLLECTORS = {
    "trends": trends,
    "hackernews": hackernews,
    "arxiv": arxiv,
    "gdelt": gdelt,
    "gpu_spot": gpu_spot,
}


def run_indicator_collectors(
    cfg: dict, start: date, end: date
) -> Iterator[tuple[str, str, float, dict | None]]:
    """Run each enabled indicator collector, yield all rows. Failures are logged & skipped."""
    for key, mod in COLLECTORS.items():
        sub = cfg["indicators"].get(key, {})
        if not sub.get("enabled", False):
            continue
        log.info("collecting %s %s..%s", key, start, end)
        try:
            yield from mod.collect(start, end, cfg)
        except Exception as e:
            log.exception("collector %s failed: %s", key, e)


def all_tickers(cfg: dict) -> list[str]:
    """Union of all configured baskets + benchmark, deduped, preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    keys = ("tickers", "power_basket", "gpu_basket")
    for key in keys:
        for t in cfg["stocks"].get(key, []) or []:
            if t not in seen:
                seen.add(t)
                out.append(t)
    bench = cfg["stocks"].get("benchmark")
    if bench and bench not in seen:
        out.append(bench)
    return out


def run_stocks(
    cfg: dict, start: date, end: date
) -> Iterator[tuple[str, str, float, int | None]]:
    tickers = all_tickers(cfg)
    log.info("collecting stocks (%d tickers) %s..%s", len(tickers), start, end)
    try:
        yield from stocks.collect(start, end, tickers)
    except Exception as e:
        log.exception("stocks collector failed: %s", e)
