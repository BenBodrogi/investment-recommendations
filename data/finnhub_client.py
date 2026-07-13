import os
import time
from dataclasses import dataclass

import requests

import config
from data.errors import DataSourceError

_last_request_time = 0.0


@dataclass
class Quote:
    symbol: str
    price: float
    day_change_pct: float
    previous_close: float


@dataclass
class Metrics:
    symbol: str
    pe_ttm: float | None
    beta: float | None
    dividend_yield_pct: float | None
    return_13wk_pct: float | None
    return_26wk_pct: float | None


def _throttle():
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    wait = config.FINNHUB_MIN_REQUEST_INTERVAL - elapsed
    if wait > 0:
        time.sleep(wait)
    _last_request_time = time.monotonic()


def _get(path: str, params: dict, symbol: str | None = None) -> dict:
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        raise DataSourceError("finnhub", symbol, "FINNHUB_API_KEY is not set")

    _throttle()
    try:
        resp = requests.get(
            f"{config.FINNHUB_BASE_URL}{path}",
            params={**params, "token": api_key},
            timeout=config.DEFAULT_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise DataSourceError("finnhub", symbol, str(exc)) from exc


def get_quote(symbol: str) -> Quote:
    data = _get("/quote", {"symbol": symbol}, symbol=symbol)
    price = data.get("c")
    previous_close = data.get("pc")
    if not price or not previous_close:
        raise DataSourceError("finnhub", symbol, f"empty/zero quote payload: {data!r}")
    return Quote(
        symbol=symbol,
        price=price,
        day_change_pct=data.get("dp", 0.0),
        previous_close=previous_close,
    )


def get_metrics(symbol: str) -> Metrics:
    data = _get("/stock/metric", {"symbol": symbol, "metric": "all"}, symbol=symbol)
    m = data.get("metric") or {}
    return Metrics(
        symbol=symbol,
        pe_ttm=m.get("peTTM"),
        beta=m.get("beta"),
        dividend_yield_pct=m.get("dividendYieldIndicatedAnnual"),
        return_13wk_pct=m.get("13WeekPriceReturnDaily"),
        return_26wk_pct=m.get("26WeekPriceReturnDaily"),
    )


def get_next_earnings_date(symbol: str) -> str | None:
    """Returns the nearest upcoming earnings date (YYYY-MM-DD) for symbol, or None."""
    today = time.strftime("%Y-%m-%d")
    in_90_days = time.strftime("%Y-%m-%d", time.localtime(time.time() + 90 * 86400))
    data = _get(
        "/calendar/earnings",
        {"from": today, "to": in_90_days, "symbol": symbol},
        symbol=symbol,
    )
    upcoming = data.get("earningsCalendar") or []
    return upcoming[0]["date"] if upcoming else None
