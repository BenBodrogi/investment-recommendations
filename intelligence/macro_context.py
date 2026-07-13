import logging
from dataclasses import dataclass, field

from data.errors import DataSourceError
from data.fred_client import get_series_latest

logger = logging.getLogger(__name__)


@dataclass
class MacroSnapshot:
    fed_funds_rate: float | None = None
    cpi_yoy: float | None = None
    unemployment_rate: float | None = None
    treasury_10y: float | None = None
    narrative: str = ""
    unavailable_series: list = field(default_factory=list)


def get_macro_snapshot() -> MacroSnapshot:
    snapshot = MacroSnapshot()
    values = {}
    for key in ("fed_funds_rate", "cpi_yoy", "unemployment_rate", "treasury_10y"):
        try:
            values[key] = get_series_latest(key)
        except DataSourceError as exc:
            logger.warning("FRED series %s unavailable: %s", key, exc)
            snapshot.unavailable_series.append(key)
            values[key] = None

    snapshot.fed_funds_rate = values["fed_funds_rate"]
    snapshot.cpi_yoy = values["cpi_yoy"]
    snapshot.unemployment_rate = values["unemployment_rate"]
    snapshot.treasury_10y = values["treasury_10y"]
    snapshot.narrative = _build_narrative(snapshot)
    return snapshot


def _build_narrative(s: MacroSnapshot) -> str:
    parts = []
    if s.fed_funds_rate is not None:
        parts.append(f"the Fed funds rate is {s.fed_funds_rate:.2f}%")
    if s.cpi_yoy is not None:
        parts.append(f"CPI inflation is running at {s.cpi_yoy:.1f}% year-over-year")
    if s.unemployment_rate is not None:
        parts.append(f"unemployment sits at {s.unemployment_rate:.1f}%")
    if s.treasury_10y is not None:
        parts.append(f"the 10-year Treasury yield is {s.treasury_10y:.2f}%")
    if not parts:
        return "Macro backdrop unavailable this run — all FRED series failed to load."
    return "As of this run, " + "; ".join(parts) + "."
