import csv
import io
import json
import time
from pathlib import Path

import requests

import config
from data.errors import DataSourceError


def get_sp500_constituents() -> list[dict]:
    """Current S&P 500 constituents as [{"symbol": ..., "sector": ...}, ...],
    cached locally (refreshed monthly - reconstitution is infrequent)."""
    cache_path = Path(config.SP500_CACHE_PATH)
    if cache_path.exists():
        age_days = (time.time() - cache_path.stat().st_mtime) / 86400
        if age_days < config.SP500_CACHE_MAX_AGE_DAYS:
            return json.loads(cache_path.read_text(encoding="utf-8"))

    try:
        resp = requests.get(config.SP500_CONSTITUENTS_URL, timeout=config.DEFAULT_REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise DataSourceError("sp500", None, str(exc)) from exc

    reader = csv.DictReader(io.StringIO(resp.text))
    constituents = [
        {"symbol": row["Symbol"].strip(), "sector": row["GICS Sector"].strip()}
        for row in reader
        if row.get("Symbol") and row.get("GICS Sector")
    ]
    if not constituents:
        raise DataSourceError("sp500", None, "constituent CSV parsed to zero rows")

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(constituents), encoding="utf-8")
    return constituents
