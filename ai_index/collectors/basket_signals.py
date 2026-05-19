"""Basket-vs-benchmark relative-return indicators.

Different from the API-based collectors: this one reads from `stock_prices`
in the local DB and writes indicator rows directly. Must run AFTER the
stocks collector upserts prices.

For each basket configured in `[stocks]`, computes the equal-weighted basket's
30-day return, subtracts the benchmark's 30-day return over the same window,
and stores that delta (in percentage points) as a daily indicator.

Why this matters: a basket of GPU-cloud companies outperforming SPY by +15pp
over 30d is a clean supply-tightness signal even when retail attention is flat.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Iterator

from .. import db

WINDOW_DAYS = 30


def _series_for(conn: sqlite3.Connection, ticker: str) -> dict[str, float]:
    cur = conn.execute(
        "SELECT date, close FROM stock_prices WHERE ticker=? ORDER BY date", (ticker,)
    )
    return {row["date"]: float(row["close"]) for row in cur}


def _trading_day_n_back(prices: dict[str, float], target: str, n: int) -> str | None:
    """Return the date string for the n-th trading day on/before `target` in this series.
    Trading days come from the series itself — non-trading days are simply absent."""
    days = [d for d in prices if d <= target]
    if len(days) < n + 1:
        return None
    return days[-(n + 1)]


def _basket_return(
    conn: sqlite3.Connection, tickers: list[str], target: str
) -> float | None:
    """Equal-weighted basket return over the last ~WINDOW_DAYS trading days, ending at `target`.
    Returns None if too few tickers have valid prices."""
    returns: list[float] = []
    for t in tickers:
        prices = _series_for(conn, t)
        if target not in prices:
            continue
        ref_date = _trading_day_n_back(prices, target, WINDOW_DAYS)
        if not ref_date:
            continue
        try:
            r = prices[target] / prices[ref_date] - 1.0
            returns.append(r)
        except (KeyError, ZeroDivisionError):
            continue
    if len(returns) < 2:
        return None
    return sum(returns) / len(returns)


def compute_and_upsert(
    conn: sqlite3.Connection,
    cfg: dict,
    start_date: date,
    end_date: date,
) -> int:
    """Compute basket-vs-SPY indicators for every available date in the range. Returns rowcount."""
    benchmark = cfg["stocks"].get("benchmark", "SPY")
    baskets: dict[str, list[str]] = {}
    if cfg["stocks"].get("power_basket"):
        baskets["power_vs_spy_30d"] = cfg["stocks"]["power_basket"]
    if cfg["stocks"].get("gpu_basket"):
        baskets["gpu_basket_vs_spy_30d"] = cfg["stocks"]["gpu_basket"]
    if not baskets:
        return 0

    # Find trading days in the range that have benchmark data.
    bench_prices = _series_for(conn, benchmark)
    target_days = sorted(
        d for d in bench_prices if start_date.isoformat() <= d <= end_date.isoformat()
    )

    n = 0
    for target in target_days:
        bench_ref = _trading_day_n_back(bench_prices, target, WINDOW_DAYS)
        if not bench_ref:
            continue
        bench_return = bench_prices[target] / bench_prices[bench_ref] - 1.0

        for indicator_name, tickers in baskets.items():
            br = _basket_return(conn, tickers, target)
            if br is None:
                continue
            delta_pp = (br - bench_return) * 100  # percentage points
            db.upsert_indicator(
                conn, target, indicator_name, delta_pp,
                {"basket": tickers, "benchmark": benchmark, "window_days": WINDOW_DAYS},
            )
            n += 1
    return n


def collect(
    start_date: date, end_date: date, cfg: dict
) -> Iterator[tuple[str, str, float, dict | None]]:
    """No-op: this collector writes directly via compute_and_upsert. Provided to match
    the collector interface so it can be referenced in COLLECTORS, but the framework
    calls compute_and_upsert separately."""
    return iter(())
