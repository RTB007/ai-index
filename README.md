# ai-index

A daily-updated **AI fantasy/heat index** — a 0–100 score for how hot the AI market is right now, scored by Claude against a rubric and plotted against baskets of AI-exposed stocks.

**Live dashboard:** <https://ai-index.lowlandcapital.com>

The interesting part isn't the indicators themselves — anyone can pull Google Trends and HN counts. It's that the index is composed daily by Claude reasoning over both **demand-side attention** (what people are saying) and **supply-side substrate** (what people are spending real money on), and weighting the *alignment* between them. Loud retail without GPU price moves is froth; quiet weeks where power utilities and GPU-cloud equities keep grinding higher are real build-out.

## The signal

| Side | Indicator | Source | Backfillable |
|---|---|---|---|
| Demand | `trends_ai_composite` | Google Trends (`pytrends`) | partial (Google rate-limits aggressive backfills) |
| Demand | `hn_ai_stories` | HN Algolia search API, OR-union via `optionalWords` | full |
| Demand | `gdelt_ai_volume` | GDELT DOC 2.0, AI-theme article volume | full (when their API cooperates) |
| Demand | `arxiv_ai_submissions` | arXiv API, cs.AI / cs.LG / cs.CL submissions | full (research-supply, treated as background) |
| Supply | `gpu_spot_h100_usd_per_hour` | Azure Retail Prices API, `Standard_ND96isr_H100_v5` spot | **forward-only** |
| Supply | `gpu_spot_a100_usd_per_hour` | Azure Retail Prices API, `Standard_ND96amsr_A100_v4` spot | **forward-only** |
| Supply | `power_vs_spy_30d` | yfinance basket (VST, CEG, TLN, GEV, NRG) 30d return − SPY 30d return | full |
| Supply | `gpu_basket_vs_spy_30d` | yfinance basket (CRWV, NBIS, IREN, APLD) 30d return − SPY 30d return | full |

Plus three stock baskets for the chart overlay (main AI, power utilities, GPU-cloud), all rebased to 100, with SPY as a dashed benchmark.

Raw indicators *and* Claude's score are both stored, so a purely mechanical baseline can be derived later for cross-check.

## How a day plays out

1. **Collect** — `scripts/daily.py` runs each enabled collector in turn. Failed sources (rate-limit / 5xx / network flake) are logged and skipped; the rest still produce a score.
2. **Compute basket signals** — basket-vs-SPY 30d relative returns are derived from `stock_prices` in the same transaction.
3. **Score** — `claude -p --output-format json` is called with the rubric, the 30-day window of every available indicator, and instructions to return strict JSON. Uses the **Max-subscription** auth on the host (no API key).
4. **Store** — `fantasy_score(date, score, rationale, components, prompt_version)`.
5. **Export** — single `web/data.json` for the static dashboard to consume.

A systemd `--user` timer fires it daily at ~03:30 UTC. Lives in [`deploy/`](deploy/).

## Why Claude in the loop?

A pure-mechanical index would weight indicators with fixed coefficients and miss context. Claude can reason: *"GPU basket is up 39% vs SPY but momentum is rolling over, and power utilities just collapsed — coherent FOMO without supply-side confirmation, cap below 70."* The rubric is versioned (`PROMPT_VERSION` in [`ai_index/scoring.py`](ai_index/scoring.py)), so historical scores can be regenerated when the rubric changes.

## Local development

```bash
uv sync
uv run python -m scripts.backfill --days 365            # one-time history
uv run python -m scripts.daily                          # today's score + export
```

Config lives in [`config.toml`](config.toml) — tickers per basket, enabled indicators, scoring window, Claude binary path. No code changes needed to extend.

## Deploy

Designed for a single-node Linux host (Hetzner ARM in my case). See [`deploy/README.md`](deploy/README.md) for systemd timer + Caddy vhost setup.

## License

MIT — see [LICENSE](LICENSE).
