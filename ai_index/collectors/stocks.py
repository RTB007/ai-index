"""Daily stock closes via yfinance.

Stored in `stock_prices` (separate from indicators).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterator

import yfinance as yf


def collect(
    start_date: date, end_date: date, tickers: list[str]
) -> Iterator[tuple[str, str, float, int | None]]:
    """Yield (date_iso, ticker, close, volume) tuples."""
    # yfinance end is exclusive, so +1 day.
    df = yf.download(
        tickers,
        start=start_date.isoformat(),
        end=(end_date + timedelta(days=1)).isoformat(),
        progress=False,
        auto_adjust=False,
        group_by="ticker",
        threads=True,
    )
    if df.empty:
        return

    if len(tickers) == 1:
        t = tickers[0]
        for ts, row in df.iterrows():
            close = row.get("Close")
            vol = row.get("Volume")
            if close is None or close != close:  # NaN guard
                continue
            yield ts.date().isoformat(), t, float(close), int(vol) if vol == vol else None
        return

    for t in tickers:
        if t not in df.columns.get_level_values(0):
            continue
        sub = df[t]
        for ts, row in sub.iterrows():
            close = row.get("Close")
            vol = row.get("Volume")
            if close is None or close != close:
                continue
            yield ts.date().isoformat(), t, float(close), int(vol) if vol == vol else None
