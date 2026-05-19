"""Shared helpers for scripts: collector dispatch + logging."""
from __future__ import annotations

import logging
import sys
from datetime import date
from typing import Iterator

from ai_index.collectors import arxiv, gdelt, hackernews, stocks, trends

log = logging.getLogger("ai_index")


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )


# Map config flag -> collector module. Order = run order.
COLLECTORS = {
    "trends": trends,
    "hackernews": hackernews,
    "arxiv": arxiv,
    "gdelt": gdelt,
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


def run_stocks(
    cfg: dict, start: date, end: date
) -> Iterator[tuple[str, str, float, int | None]]:
    tickers = cfg["stocks"]["tickers"]
    log.info("collecting stocks %s %s..%s", tickers, start, end)
    try:
        yield from stocks.collect(start, end, tickers)
    except Exception as e:
        log.exception("stocks collector failed: %s", e)
