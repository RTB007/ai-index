# ai-index

A daily-updated "AI fantasy/heat" index for the AI market, scored 0–100 by Claude based on early indicators, plotted against a basket of AI stocks.

Lives at `ai-index.lowlandcapital.com`.

## How it works

1. **Daily job** collects raw early-indicator data (Google Trends, HackerNews, arXiv, GDELT, stock closes).
2. **Claude** is invoked locally via `claude -p` (uses the Max subscription, no API key) with a 30-day window of indicators and a fixed rubric, returning a JSON score + rationale + sub-scores.
3. **SQLite** stores raw indicators, the score, and stock prices.
4. **Static dashboard** plots the index against the AI stock basket.

The raw indicators are stored alongside Claude's score so a purely-mechanical baseline can be derived later for cross-check.

## Local dev

```bash
uv sync
uv run python -m scripts.backfill --days 365   # one-time
uv run python -m scripts.daily                  # what the timer runs
uv run python -m scripts.export_json
```

## Deploy (Hetzner CAX11)

See [`deploy/`](deploy/) — systemd timer + nginx vhost.
