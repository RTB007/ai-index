"""One-time historical backfill of indicators and stock prices.

By default does NOT score — that's an optional --with-scores pass that calls Claude
once per day in the range. With 365 days that's ~365 Claude invocations, so it's gated.
"""
from __future__ import annotations

import argparse
import logging
import time
from datetime import date, timedelta

from ai_index import config, db, scoring

from ._common import run_indicator_collectors, run_stocks, setup_logging

log = logging.getLogger("ai_index.backfill")


def main() -> int:
    parser = argparse.ArgumentParser(description="ai-index historical backfill")
    parser.add_argument("--days", type=int, default=365, help="How many days back from end-date.")
    parser.add_argument("--end", type=date.fromisoformat, default=date.today() - timedelta(days=1))
    parser.add_argument(
        "--with-scores",
        action="store_true",
        help="Also run Claude scoring for each day in the range (slow + uses Max quota).",
    )
    parser.add_argument(
        "--score-step",
        type=int,
        default=1,
        help="With --with-scores, score every Nth day (default 1 = every day). "
        "Use 7 to get weekly scores for a quick first plot.",
    )
    parser.add_argument("--no-indicators", action="store_true", help="Skip indicator collection.")
    parser.add_argument("--no-stocks", action="store_true", help="Skip stock collection.")
    args = parser.parse_args()

    setup_logging()
    cfg = config.load()
    db_p = config.db_path(cfg)
    db.init(db_p)

    start = args.end - timedelta(days=args.days)
    log.info("backfill range: %s .. %s", start, args.end)

    if not args.no_indicators:
        with db.connect(db_p) as conn:
            n = 0
            for row in run_indicator_collectors(cfg, start, args.end):
                db.upsert_indicator(conn, *row)
                n += 1
            log.info("upserted %d indicator rows", n)

    if not args.no_stocks:
        with db.connect(db_p) as conn:
            n = 0
            for d_iso, ticker, close, vol in run_stocks(cfg, start, args.end):
                db.upsert_stock(conn, d_iso, ticker, close, vol)
                n += 1
            log.info("upserted %d stock rows", n)

    if args.with_scores:
        log.info("scoring %d days (step %d)", args.days // args.score_step, args.score_step)
        cur = start
        scored = 0
        while cur <= args.end:
            with db.connect(db_p) as conn:
                window = db.indicators_window(
                    conn, cur.isoformat(), cfg["scoring"]["window_days"]
                )
            if window:
                try:
                    result = scoring.score(
                        cur.isoformat(), window, claude_bin=cfg["scoring"]["claude_bin"]
                    )
                    with db.connect(db_p) as conn:
                        db.upsert_score(
                            conn,
                            cur.isoformat(),
                            result["score"],
                            result["rationale"],
                            result["components"],
                            cfg["scoring"]["prompt_version"],
                        )
                    scored += 1
                    log.info("scored %s = %d", cur, result["score"])
                except Exception as e:
                    log.exception("score failed for %s: %s", cur, e)
                # Be polite between Claude calls
                time.sleep(2)
            cur += timedelta(days=args.score_step)
        log.info("scored %d days", scored)

    # Always refresh export at the end.
    from . import export_json
    export_json.export(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
