"""SQLite schema and helpers."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_indicators (
    date     TEXT NOT NULL,
    name     TEXT NOT NULL,
    value    REAL NOT NULL,
    meta     TEXT,
    PRIMARY KEY (date, name)
);
CREATE INDEX IF NOT EXISTS idx_raw_name_date ON raw_indicators(name, date);

CREATE TABLE IF NOT EXISTS fantasy_score (
    date            TEXT PRIMARY KEY,
    score           INTEGER NOT NULL,
    rationale       TEXT,
    components      TEXT,
    prompt_version  INTEGER NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS stock_prices (
    date    TEXT NOT NULL,
    ticker  TEXT NOT NULL,
    close   REAL NOT NULL,
    volume  INTEGER,
    PRIMARY KEY (date, ticker)
);
CREATE INDEX IF NOT EXISTS idx_stock_ticker_date ON stock_prices(ticker, date);
"""


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # 30s busy-timeout + WAL mode keeps the manual backfills and the systemd
    # timer from clobbering each other when their wall-clock windows overlap.
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init(db_path: Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def upsert_indicator(
    conn: sqlite3.Connection,
    date: str,
    name: str,
    value: float,
    meta: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        "INSERT INTO raw_indicators(date, name, value, meta) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(date, name) DO UPDATE SET value=excluded.value, meta=excluded.meta",
        (date, name, float(value), json.dumps(meta) if meta else None),
    )


def upsert_indicators(
    conn: sqlite3.Connection,
    rows: Iterable[tuple[str, str, float, dict[str, Any] | None]],
) -> int:
    n = 0
    for date, name, value, meta in rows:
        upsert_indicator(conn, date, name, value, meta)
        n += 1
    return n


def upsert_score(
    conn: sqlite3.Connection,
    date: str,
    score: int,
    rationale: str,
    components: dict[str, Any],
    prompt_version: int,
) -> None:
    conn.execute(
        "INSERT INTO fantasy_score(date, score, rationale, components, prompt_version) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(date) DO UPDATE SET score=excluded.score, rationale=excluded.rationale, "
        "components=excluded.components, prompt_version=excluded.prompt_version, "
        "created_at=datetime('now')",
        (date, int(score), rationale, json.dumps(components), prompt_version),
    )


def upsert_stock(
    conn: sqlite3.Connection,
    date: str,
    ticker: str,
    close: float,
    volume: int | None,
) -> None:
    conn.execute(
        "INSERT INTO stock_prices(date, ticker, close, volume) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(date, ticker) DO UPDATE SET close=excluded.close, volume=excluded.volume",
        (date, ticker, float(close), volume),
    )


def indicators_window(
    conn: sqlite3.Connection, end_date: str, days: int
) -> dict[str, list[dict[str, Any]]]:
    """Return {indicator_name: [{date, value, meta}, ...]} for the trailing window."""
    cur = conn.execute(
        "SELECT date, name, value, meta FROM raw_indicators "
        "WHERE date <= ? AND date >= date(?, ?) "
        "ORDER BY name, date",
        (end_date, end_date, f"-{days} days"),
    )
    out: dict[str, list[dict[str, Any]]] = {}
    for row in cur:
        out.setdefault(row["name"], []).append(
            {
                "date": row["date"],
                "value": row["value"],
                "meta": json.loads(row["meta"]) if row["meta"] else None,
            }
        )
    return out


def scores_all(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    cur = conn.execute(
        "SELECT date, score, rationale, components FROM fantasy_score ORDER BY date"
    )
    return [
        {
            "date": row["date"],
            "score": row["score"],
            "rationale": row["rationale"],
            "components": json.loads(row["components"]) if row["components"] else {},
        }
        for row in cur
    ]


def stocks_all(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    cur = conn.execute(
        "SELECT date, ticker, close, volume FROM stock_prices ORDER BY ticker, date"
    )
    out: dict[str, list[dict[str, Any]]] = {}
    for row in cur:
        out.setdefault(row["ticker"], []).append(
            {"date": row["date"], "close": row["close"], "volume": row["volume"]}
        )
    return out


def indicators_all(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    cur = conn.execute(
        "SELECT date, name, value FROM raw_indicators ORDER BY name, date"
    )
    out: dict[str, list[dict[str, Any]]] = {}
    for row in cur:
        out.setdefault(row["name"], []).append(
            {"date": row["date"], "value": row["value"]}
        )
    return out
