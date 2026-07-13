from dataclasses import dataclass

import config


@dataclass
class ReturnEstimate:
    central_pct: float
    low_pct: float
    high_pct: float
    horizon_months: int
    caveat: str


def estimate_return(
    asset_class: str,               # "stock" | "etf" | "crypto"
    trend_annualized_pct: float,     # already annualized by the caller
    dividend_yield_pct: float | None,
    normalized_volatility: float,    # 0..1 (0 = low vol, 1 = high vol)
    etf_category: str | None = None,
) -> ReturnEstimate:
    """Simple, transparent heuristic blend — NOT a model. Deliberately
    dampens the trailing trend toward a long-run base rate rather than
    naively extrapolating it, and clamps the trend input so one wild
    short-term move (especially crypto) can't dominate the estimate."""
    clamped_trend = max(-60.0, min(60.0, trend_annualized_pct)) / 100

    base_rate = config.ASSET_CLASS_BASE_RATE.get(asset_class, 0.08)
    if asset_class == "etf" and etf_category in config.ETF_CATEGORY_BASE_RATE_OVERRIDES:
        base_rate = config.ETF_CATEGORY_BASE_RATE_OVERRIDES[etf_category]

    dividend_component = (dividend_yield_pct or 0.0) / 100

    central = 0.4 * clamped_trend + 0.4 * base_rate + 0.2 * dividend_component
    central_pct = central * 100

    base_spread = config.BASE_SPREAD_PCT.get(asset_class, 12)
    spread = base_spread * (1 + max(0.0, min(1.0, normalized_volatility)))

    return ReturnEstimate(
        central_pct=round(central_pct, 1),
        low_pct=round(central_pct - spread, 1),
        high_pct=round(central_pct + spread, 1),
        horizon_months=config.RETURN_ESTIMATE_HORIZON_MONTHS,
        caveat=config.RETURN_ESTIMATE_CAVEAT,
    )
