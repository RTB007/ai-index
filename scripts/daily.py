"""Daily job: collect last few days of indicators + stocks, score yesterday, export JSON.

Designed to be idempotent — safe to re-run any day. Run via systemd timer once daily.
"""
from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta

from ai_index import config, db, scoring

from ._common import run_indicator_collectors, run_stocks, setup_logging

log = logging.getLogger("ai_index.daily")


def main() -> int:
    parser = argparse.ArgumentParser(description="ai-index daily job")
    parser.add_argument(
        "--target",
        type=date.fromisoformat,
        default=date.today() - timedelta(days=1),
        help="Date to score (default: yesterday). Most sources lag ~1 day.",
    )
    parser.add_argument(
        "--collect-window",
        type=int,
        default=3,
        help="Days back from target to (re)collect indicators (default 3, catches late-arriving data).",
    )
    parser.add_argument(
        "--no-score",
        action="store_true",
        help="Skip Claude scoring (collection + stocks only).",
    )
    args = parser.parse_args()

    setup_logging()
    cfg = config.load()
    db_p = config.db_path(cfg)
    db.init(db_p)

    collect_start = args.target - timedelta(days=args.collect_window)
    collect_end = args.target

    n_ind = n_stk = 0
    with db.connect(db_p) as conn:
        for row in run_indicator_collectors(cfg, collect_start, collect_end):
            db.upsert_indicator(conn, *row)
            n_ind += 1
        for d_iso, ticker, close, vol in run_stocks(cfg, collect_start, collect_end):
            db.upsert_stock(conn, d_iso, ticker, close, vol)
            n_stk += 1
    log.info("upserted indicators=%d stocks=%d", n_ind, n_stk)

    if args.no_score:
        return 0

    with db.connect(db_p) as conn:
        window = db.indicators_window(
            conn, args.target.isoformat(), cfg["scoring"]["window_days"]
        )

    if not window:
        log.warning("no indicators in window — cannot score %s", args.target)
        return 1

    log.info("scoring %s with %d indicators", args.target, len(window))
    result = scoring.score(
        args.target.isoformat(), window, claude_bin=cfg["scoring"]["claude_bin"]
    )
    log.info("score=%d rationale=%s", result["score"], result["rationale"])

    with db.connect(db_p) as conn:
        db.upsert_score(
            conn,
            args.target.isoformat(),
            result["score"],
            result["rationale"],
            result["components"],
            cfg["scoring"]["prompt_version"],
        )

    # Export JSON for the frontend.
    from . import export_json
    export_json.export(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
