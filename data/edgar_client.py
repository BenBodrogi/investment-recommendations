import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

import config
from data.errors import DataSourceError

_last_request_time = 0.0

# A well-followed public company's latest 10-K should never be much more
# than ~15 months old. If the best match we can find under our known
# concept names is older than this, it almost always means the filer has
# migrated to a different XBRL tag we're not checking (see NEE, which tags
# revenue outside _REVENUE_CONCEPTS and left only a stale 2012 match) -
# better to report it as unavailable than as current.
_MAX_FILING_AGE_DAYS = 730

# Different filers tag the same concept differently; try each in order and
# use the first that has annual (10-K) data.
_REVENUE_CONCEPTS = [
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
]
_NET_INCOME_CONCEPTS = ["NetIncomeLoss"]


@dataclass
class CompanyFacts:
    symbol: str
    revenue: float | None
    revenue_period_end: str | None
    net_income: float | None
    net_margin_pct: float | None


def _throttle():
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    wait = config.SEC_EDGAR_MIN_REQUEST_INTERVAL - elapsed
    if wait > 0:
        time.sleep(wait)
    _last_request_time = time.monotonic()


def _headers(symbol: str | None) -> dict:
    user_agent = os.getenv("SEC_EDGAR_USER_AGENT")
    if not user_agent:
        raise DataSourceError("edgar", symbol, "SEC_EDGAR_USER_AGENT is not set")
    return {"User-Agent": user_agent}


def _get_json(url: str, symbol: str | None = None) -> dict:
    _throttle()
    try:
        resp = requests.get(url, headers=_headers(symbol), timeout=config.DEFAULT_REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise DataSourceError("edgar", symbol, str(exc)) from exc


def _load_cik_map() -> dict[str, str]:
    """ticker -> 10-digit zero-padded CIK, cached locally (refreshed weekly)."""
    cache_path = Path(config.CIK_CACHE_PATH)
    if cache_path.exists():
        age_days = (time.time() - cache_path.stat().st_mtime) / 86400
        if age_days < config.CIK_CACHE_MAX_AGE_DAYS:
            return json.loads(cache_path.read_text(encoding="utf-8"))

    raw = _get_json(config.EDGAR_TICKER_MAP_URL)
    ticker_to_cik = {
        row["ticker"].upper(): str(row["cik_str"]).zfill(10)
        for row in raw.values()
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(ticker_to_cik), encoding="utf-8")
    return ticker_to_cik


def _latest_annual_value(facts: dict, concept_names: list[str]) -> tuple[float, str] | None:
    """Companies sometimes migrate which XBRL concept they tag a figure
    under (e.g. Apple moved revenue from `Revenues` to
    `RevenueFromContractWithCustomerExcludingAssessedTax` around 2018).
    Collect the best candidate from every concept name and take the
    most recent overall, rather than stopping at the first concept that
    has any data at all — otherwise a stale, no-longer-used concept can
    shadow years of more recent data filed under its replacement."""
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    candidates = []
    for concept in concept_names:
        entries = us_gaap.get(concept, {}).get("units", {}).get("USD", [])
        annual = [e for e in entries if e.get("form") == "10-K" and e.get("val") is not None]
        if annual:
            candidates.append(max(annual, key=lambda e: e["end"]))
    if not candidates:
        return None
    best = max(candidates, key=lambda e: e["end"])
    return best["val"], best["end"]


def get_company_facts(symbol: str) -> CompanyFacts:
    cik_map = _load_cik_map()
    cik = cik_map.get(symbol.upper())
    if not cik:
        raise DataSourceError("edgar", symbol, "no CIK found for this ticker")

    facts = _get_json(f"{config.EDGAR_BASE_URL}/companyfacts/CIK{cik}.json", symbol=symbol)

    revenue, revenue_period = _latest_annual_value(facts, _REVENUE_CONCEPTS) or (None, None)
    net_income, net_income_period = _latest_annual_value(facts, _NET_INCOME_CONCEPTS) or (None, None)

    cutoff = (datetime.now(timezone.utc) - timedelta(days=_MAX_FILING_AGE_DAYS)).strftime("%Y-%m-%d")
    if revenue_period and revenue_period < cutoff:
        revenue, revenue_period = None, None
    if net_income_period and net_income_period < cutoff:
        net_income, net_income_period = None, None

    # Margin is only meaningful when both figures come from the same
    # fiscal period. Each figure is independently useful on its own even
    # when they don't match (or one is missing) - only the derived ratio
    # needs this guard.
    margin = None
    if revenue and net_income is not None and revenue_period == net_income_period:
        margin = net_income / revenue * 100

    return CompanyFacts(
        symbol=symbol,
        revenue=revenue,
        revenue_period_end=revenue_period,
        net_income=net_income,
        net_margin_pct=margin,
    )
