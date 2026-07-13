import logging
from dataclasses import dataclass

import yaml

import config

logger = logging.getLogger(__name__)


@dataclass
class WatchlistEntry:
    symbol: str
    asset_class: str          # "stock" | "etf" | "crypto"
    group: str                # sector (stocks) or category (etfs/crypto)
    coingecko_id: str | None = None  # crypto only — CoinGecko keys on id, not ticker


_REQUIRED_FIELDS = {
    "stock": ("symbol", "sector"),
    "etf": ("symbol", "category"),
    "crypto": ("symbol", "coingecko_id", "category"),
}
_GROUP_FIELD = {"stock": "sector", "etf": "category", "crypto": "category"}
_YAML_SECTION = {"stock": "stocks", "etf": "etfs", "crypto": "crypto"}


def load_watchlist(path: str = None) -> list[WatchlistEntry]:
    path = path or config.WATCHLIST_PATH
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    entries: list[WatchlistEntry] = []
    for asset_class, section_key in _YAML_SECTION.items():
        for row in raw.get(section_key, []) or []:
            required = _REQUIRED_FIELDS[asset_class]
            missing = [field for field in required if not row.get(field)]
            if missing:
                logger.warning(
                    "Skipping malformed %s entry %r — missing field(s): %s",
                    asset_class, row, ", ".join(missing),
                )
                continue
            entries.append(WatchlistEntry(
                symbol=row["symbol"],
                asset_class=asset_class,
                group=row[_GROUP_FIELD[asset_class]],
                coingecko_id=row.get("coingecko_id"),
            ))

    if not entries:
        raise ValueError(f"Watchlist at {path!r} loaded but contains zero valid entries")

    return entries
