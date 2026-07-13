import dataclasses
import json
import os
from datetime import datetime, timezone

import config


def _asdict(obj):
    return dataclasses.asdict(obj) if dataclasses.is_dataclass(obj) else obj


def build_payload(scored_symbols: list, deep_dives: dict, macro, data_quality: dict) -> dict:
    return {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "disclaimer": config.STANDING_DISCLAIMER,
        "macro_backdrop": {
            "fed_funds_rate": macro.fed_funds_rate,
            "cpi_yoy": macro.cpi_yoy,
            "unemployment_rate": macro.unemployment_rate,
            "treasury_10y": macro.treasury_10y,
            "narrative": macro.narrative,
        },
        "watchlist_summary": [_asdict(s) for s in scored_symbols],
        "deep_dives": {
            asset_class: [_asdict(d) for d in dives]
            for asset_class, dives in deep_dives.items()
        },
        "data_quality": data_quality,
    }


def write_payload(payload: dict, path: str = None) -> str:
    path = path or os.path.join(config.OUTPUT_DIR, config.OUTPUT_FILENAME)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path
