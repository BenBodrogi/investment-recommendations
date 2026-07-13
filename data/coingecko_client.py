import os
from dataclasses import dataclass

import requests

import config
from data.errors import DataSourceError


@dataclass
class CryptoMarket:
    coingecko_id: str
    price: float
    ath_change_percentage: float
    change_7d_pct: float | None
    change_30d_pct: float | None


def get_markets(coingecko_ids: list[str]) -> dict[str, CryptoMarket]:
    """Single batched call covering every crypto in the watchlist."""
    headers = {}
    api_key = os.getenv("COINGECKO_API_KEY")
    if api_key:
        headers["x-cg-demo-api-key"] = api_key

    try:
        resp = requests.get(
            f"{config.COINGECKO_BASE_URL}/coins/markets",
            params={
                "vs_currency": "usd",
                "ids": ",".join(coingecko_ids),
                "price_change_percentage": "7d,30d",
            },
            headers=headers,
            timeout=config.DEFAULT_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        rows = resp.json()
    except requests.RequestException as exc:
        raise DataSourceError("coingecko", None, str(exc)) from exc

    results: dict[str, CryptoMarket] = {}
    for row in rows:
        cg_id = row.get("id")
        price = row.get("current_price")
        if not cg_id or not price:
            continue
        results[cg_id] = CryptoMarket(
            coingecko_id=cg_id,
            price=price,
            ath_change_percentage=row.get("ath_change_percentage") or 0.0,
            change_7d_pct=row.get("price_change_percentage_7d_in_currency"),
            change_30d_pct=row.get("price_change_percentage_30d_in_currency"),
        )
    return results
