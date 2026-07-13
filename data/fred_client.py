import os

import requests

import config
from data.errors import DataSourceError


def get_series_latest(series_key: str) -> float:
    """Fetch the most recent observation for one of config.FRED_SERIES.
    Raises DataSourceError if the key is unconfigured, the request fails,
    or FRED returns a missing-data sentinel ('.')."""
    series_cfg = config.FRED_SERIES.get(series_key)
    if not series_cfg:
        raise DataSourceError("fred", None, f"unknown series key: {series_key!r}")

    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        raise DataSourceError("fred", None, "FRED_API_KEY is not set")

    params = {
        "series_id": series_cfg["series_id"],
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 1,
    }
    if series_cfg.get("units"):
        params["units"] = series_cfg["units"]

    try:
        resp = requests.get(
            f"{config.FRED_BASE_URL}/series/observations",
            params=params,
            timeout=config.DEFAULT_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        observations = resp.json().get("observations") or []
    except requests.RequestException as exc:
        raise DataSourceError("fred", None, str(exc)) from exc

    if not observations or observations[0]["value"] == ".":
        raise DataSourceError("fred", None, f"no data for series {series_cfg['series_id']!r}")

    return float(observations[0]["value"])
