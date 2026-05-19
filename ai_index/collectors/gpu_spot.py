"""Azure GPU spot prices via the public Azure Retail Prices API.

Indicators:
  gpu_spot_h100_usd_per_hour  — min spot $/hr for Standard_ND_H100_v5 (8x H100)
  gpu_spot_a100_usd_per_hour  — min spot $/hr for Standard_ND96amsr_A100_v4 (8x A100 80GB)

The API only exposes CURRENT prices — no historical endpoint. So this is a
forward-only collector: every call yields rows for `today`, regardless of the
range passed in. Over time daily writes build the time series we need.

Public, no auth, no documented rate limit beyond "be reasonable". We hit it once
per SKU per region per day (≤6 calls/day total).
"""
from __future__ import annotations

import time
from datetime import date
from typing import Iterator

import requests

ENDPOINT = "https://prices.azure.com/api/retail/prices"
HEADERS = {"User-Agent": "ai-index/0.1 (+https://github.com/RTB007/ai-index)"}


def _indicator_name_for(sku: str) -> str:
    if "H100" in sku:
        return "gpu_spot_h100_usd_per_hour"
    if "A100" in sku:
        return "gpu_spot_a100_usd_per_hour"
    return f"gpu_spot_{sku.lower().replace('standard_', '').replace('_', '')}_usd_per_hour"


def _fetch_spot_price(sku: str, region: str) -> float | None:
    """Return min spot $/hr for the (sku, region) combination, or None if not found."""
    flt = (
        f"armSkuName eq '{sku}' "
        f"and armRegionName eq '{region}' "
        f"and priceType eq 'Consumption' "
        f"and contains(meterName, 'Spot')"
    )
    best: float | None = None
    next_url: str | None = ENDPOINT
    params: dict[str, str] | None = {"$filter": flt}
    for _ in range(5):  # paginate at most a few times
        for attempt in range(3):
            try:
                r = requests.get(next_url, params=params, headers=HEADERS, timeout=30)
                r.raise_for_status()
                data = r.json()
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        for item in data.get("Items", []):
            price = item.get("retailPrice")
            if price is not None and price > 0:
                if best is None or price < best:
                    best = float(price)
        next_url = data.get("NextPageLink")
        if not next_url:
            break
        params = None  # next-page URL is fully qualified
    return best


def collect(
    start_date: date, end_date: date, cfg: dict
) -> Iterator[tuple[str, str, float, dict | None]]:
    """Azure has no historical endpoint; ignore the range and emit one row per SKU for today."""
    today = date.today().isoformat()
    skus = cfg["indicators"]["gpu_spot"]["skus"]
    regions = cfg["indicators"]["gpu_spot"]["regions"]

    for sku in skus:
        region_prices: dict[str, float] = {}
        for region in regions:
            try:
                p = _fetch_spot_price(sku, region)
            except Exception:
                p = None
            if p is not None:
                region_prices[region] = p
            time.sleep(0.5)
        if not region_prices:
            continue
        min_price = min(region_prices.values())
        yield (
            today,
            _indicator_name_for(sku),
            min_price,
            {"sku": sku, "regions": region_prices},
        )
