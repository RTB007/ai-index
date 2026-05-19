"""Export DB contents to a single JSON file the frontend reads."""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone

from ai_index import config, db

from ._common import setup_logging

log = logging.getLogger("ai_index.export")


def export(cfg: dict) -> None:
    db_p = config.db_path(cfg)
    out_p = config.export_path(cfg)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    with db.connect(db_p) as conn:
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "prompt_version": cfg["scoring"]["prompt_version"],
            "scores": db.scores_all(conn),
            "indicators": db.indicators_all(conn),
            "stocks": db.stocks_all(conn),
            "tickers": cfg["stocks"]["tickers"],
            "baskets": {
                "main": cfg["stocks"].get("tickers", []),
                "power": cfg["stocks"].get("power_basket", []),
                "gpu": cfg["stocks"].get("gpu_basket", []),
            },
            "benchmark": cfg["stocks"].get("benchmark"),
        }
    with out_p.open("w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))
    log.info(
        "wrote %s (%d scores, %d indicator series, %d tickers)",
        out_p,
        len(payload["scores"]),
        len(payload["indicators"]),
        len(payload["stocks"]),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    setup_logging()
    export(config.load())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
