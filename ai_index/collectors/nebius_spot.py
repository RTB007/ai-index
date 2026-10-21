"""Nebius AI Cloud spot (preemptible) GPU prices via the public Nebius billing API.

Indicators (USD per GPU-hour, median across regions of the daily average):
  nebius_spot_h200_usd       — Hopper H200 (platforms gpu-h200*)
  nebius_spot_blackwell_usd  — Blackwell B200 + B300 (platforms gpu-b200*, gpu-b300*)

Why this exists next to gpu_spot (Azure): Azure's "spot" retail prices are near-static list
prices per 8-GPU VM. Nebius spot prices are market-driven and move several times a day with
capacity tightness, so they are a much more sensitive supply-side signal: rising = GPUs
scarce, flat/falling = slack.

API: https://docs.nebius.com/signup-billing/spot-prices — public, no auth.
  GET /billing/v1alpha1/spot-price/list-series   hourly series, history limited to 30 days
Each series is one SKU (= platform x region). Per day we average the hourly points of a SKU,
then take the median over the SKUs of a group, so a region appearing or disappearing doesn't
make the series jump. Meta keeps the per-region daily averages.

Market pricing started 2026-10-08 11:00 UTC (see MARKT_VANAF); earlier days yield nothing.
Because history only reaches back 30 days, a backfill further back silently yields nothing
for older days; from launch on the daily job keeps the series going.
"""
from __future__ import annotations

import statistics
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Iterator

import requests

SERIES = "https://api.nebius.cloud/billing/v1alpha1/spot-price/list-series"
HEADERS = {"User-Agent": "ai-index/0.1 (+https://ai-index.lowlandcapital.com)"}
HISTORY_DAYS = 30
# Tot 2026-10-08 11:00 UTC had Nebius vaste preemptible-prijzen (H200 2.45, B300 4.30, ...);
# toen gingen alle SKU's tegelijk over op marktprijzen die honderden keren per maand bewegen.
# De vaste periode is geen marktsignaal - de overgang van lijstprijs naar marktprijs zou als
# "GPU's worden goedkoper" gelezen worden - dus pas vanaf de eerste volle marktdag.
MARKT_VANAF = date(2026, 10, 9)

# indicator name -> platform prefixes
GROUPS = {
    "nebius_spot_h200_usd": ("gpu-h200",),
    "nebius_spot_blackwell_usd": ("gpu-b200", "gpu-b300"),
}


def _get(params: dict) -> dict:
    for attempt in range(3):
        try:
            r = requests.get(SERIES, params=params, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    return {}


def _series(start: datetime) -> list[dict]:
    out, token = [], None
    for _ in range(20):  # paginate; 100 series per page
        params = {
            "filters.startTime": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "aggregation.granularity": "GRANULARITY_HOUR_1",
            "aggregation.method": "METHOD_AVG_PRICE",
            "pageSize": 100,
        }
        if token:
            params["pageToken"] = token
        data = _get(params)
        out.extend(data.get("items", []))
        token = data.get("nextPageToken")
        if not token:
            break
    return out


def _group_of(platform: str) -> str | None:
    for name, prefixes in GROUPS.items():
        if any(platform.startswith(p) for p in prefixes):
            return name
    return None


def collect(start_date: date, end_date: date, cfg: dict) -> Iterator[tuple[str, str, float, dict | None]]:
    now = datetime.now(timezone.utc)
    earliest = (now - timedelta(days=HISTORY_DAYS) + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    start_date = max(start_date, MARKT_VANAF)
    start = max(datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc), earliest)
    if start.date() > end_date:
        return

    # per (group, day): {sku-label: [hourly values]}
    per_dag: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for s in _series(start):
        group = _group_of((s.get("computeInstance") or {}).get("platform", ""))
        if not group or (s.get("currency") or "usd").lower() != "usd":
            continue
        label = "%s/%s" % ((s.get("computeInstance") or {}).get("platform", "?"), s.get("region", "?"))
        for p in s.get("points", []):
            try:
                d = p["timestamp"][:10]
                v = float(p["value"])
            except (KeyError, TypeError, ValueError):
                continue
            if v > 0 and start_date.isoformat() <= d <= end_date.isoformat():
                per_dag[(group, d)][label].append(v)

    for (group, d), skus in sorted(per_dag.items()):
        dagwaarden = {k: round(sum(v) / len(v), 4) for k, v in skus.items() if v}
        if not dagwaarden:
            continue
        yield (d, group, round(statistics.median(dagwaarden.values()), 4),
               {"per_region": dagwaarden, "skus": len(dagwaarden), "source": "nebius list-series hourly avg"})
