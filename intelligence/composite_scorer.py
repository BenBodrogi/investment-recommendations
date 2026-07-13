from dataclasses import dataclass, field

import config
from data.coingecko_client import CryptoMarket
from data.finnhub_client import Metrics, Quote


@dataclass
class ScoredSymbol:
    symbol: str
    asset_class: str   # "stock" | "etf" | "crypto"
    group: str          # sector (stocks) or category (etfs/crypto)
    composite_score: float
    score_breakdown: dict
    price: float
    day_change_pct: float | None
    data_quality_notes: list = field(default_factory=list)


def _interp(x: float, points: list[tuple[float, float]]) -> float:
    """Piecewise-linear interpolation; clamps to the first/last point outside range."""
    points = sorted(points)
    if x <= points[0][0]:
        return points[0][1]
    if x >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return points[-1][1]  # unreachable, satisfies type checkers


def blended_equity_return_pct(metrics: Metrics | None) -> float | None:
    """Average of trailing 13wk/26wk returns — the shared 'recent trend'
    figure used by both the momentum sub-score and the return estimator."""
    if metrics is None:
        return None
    r13, r26 = metrics.return_13wk_pct, metrics.return_26wk_pct
    if r13 is None and r26 is None:
        return None
    return 0.5 * (r13 if r13 is not None else r26) + 0.5 * (r26 if r26 is not None else r13)


def blended_crypto_return_pct(market: CryptoMarket) -> float | None:
    """Average of trailing 7d/30d changes — the shared 'recent trend' figure
    used by both the momentum sub-score and the return estimator."""
    d7, d30 = market.change_7d_pct, market.change_30d_pct
    if d7 is None and d30 is None:
        return None
    return 0.5 * (d7 if d7 is not None else d30) + 0.5 * (d30 if d30 is not None else d7)


def _score_pe(pe: float | None) -> float:
    if pe is None:
        return config.NEUTRAL_SCORE
    if pe <= 0:
        return 20.0  # unprofitable — treated like a very expensive multiple
    return _interp(pe, [
        (0, 60),
        (config.PE_SWEET_SPOT_LOW, 100),
        (config.PE_SWEET_SPOT_HIGH, 100),
        (config.PE_EXPENSIVE_CUTOFF, 20),
    ])


def _score_momentum_equity(blended_return_pct: float | None) -> float:
    if blended_return_pct is None:
        return config.NEUTRAL_SCORE
    return _interp(blended_return_pct, [
        (-50, 0),
        (0, 50),
        (config.MOMENTUM_CAP_PCT, 100),
        (config.MOMENTUM_OVEREXTENDED_PCT, 100),
        (100, 30),  # overextension decay past MOMENTUM_OVEREXTENDED_PCT
    ])


def _score_beta(beta: float | None) -> float:
    if beta is None:
        return config.NEUTRAL_SCORE
    return _interp(beta, [
        (0, 60),
        (config.BETA_SWEET_SPOT_LOW, 100),
        (config.BETA_SWEET_SPOT_HIGH, 100),
        (2.0, 20),
    ])


def _score_yield(dividend_yield_pct: float | None) -> float:
    if dividend_yield_pct is None:
        return config.NEUTRAL_SCORE
    if dividend_yield_pct <= 0:
        return 40.0
    return _interp(dividend_yield_pct, [
        (0, 40),
        (config.YIELD_SWEET_SPOT_PCT, 100),
        (config.YIELD_DISTRESS_CUTOFF_PCT, 50),
        (20, 50),
    ])


def score_equity(
    symbol: str,
    asset_class: str,
    group: str,
    quote: Quote,
    metrics: Metrics | None,
) -> ScoredSymbol:
    notes = []
    if metrics is None:
        notes.append("fundamentals unavailable — all sub-scores defaulted to neutral")
        pe = beta = dividend_yield = None
    else:
        pe, beta, dividend_yield = metrics.pe_ttm, metrics.beta, metrics.dividend_yield_pct
        for field_name, value in [("P/E", pe), ("beta", beta), ("dividend yield", dividend_yield)]:
            if value is None:
                notes.append(f"{field_name} unavailable — sub-score defaulted to neutral")
    blended_momentum = blended_equity_return_pct(metrics)

    breakdown = {
        "valuation": _score_pe(pe),
        "momentum": _score_momentum_equity(blended_momentum),
        "volatility": _score_beta(beta),
        "yield": _score_yield(dividend_yield),
    }
    composite = sum(breakdown[k] * w for k, w in config.SCORING_WEIGHTS_EQUITY.items())

    return ScoredSymbol(
        symbol=symbol,
        asset_class=asset_class,
        group=group,
        composite_score=round(composite, 1),
        score_breakdown={k: round(v, 1) for k, v in breakdown.items()},
        price=quote.price,
        day_change_pct=quote.day_change_pct,
        data_quality_notes=notes,
    )


def _score_crypto_valuation(ath_change_pct: float) -> float:
    return _interp(ath_change_pct, [
        (-100, 25),
        (-80, 40),
        (config.CRYPTO_ATH_SWEET_SPOT_LOW_PCT, 100),
        (config.CRYPTO_ATH_SWEET_SPOT_HIGH_PCT, 100),
        (0, 50),
    ])


def _score_crypto_momentum(blended_change_pct: float | None) -> float:
    if blended_change_pct is None:
        return config.NEUTRAL_SCORE
    return _interp(blended_change_pct, [
        (-50, 0),
        (0, 50),
        (config.CRYPTO_MOMENTUM_CAP_PCT, 100),
        (60, 100),
        (150, 30),
    ])


def _score_crypto_volatility(change_30d: float | None) -> float:
    if change_30d is None:
        return config.NEUTRAL_SCORE
    return _interp(abs(change_30d), [(0, 100), (30, 50), (60, 20)])


def score_crypto(symbol: str, group: str, market: CryptoMarket) -> ScoredSymbol:
    notes = []
    if market.change_7d_pct is None and market.change_30d_pct is None:
        notes.append("7d/30d price change unavailable — momentum/volatility defaulted to neutral")

    breakdown = {
        "valuation": _score_crypto_valuation(market.ath_change_percentage),
        "momentum": _score_crypto_momentum(blended_crypto_return_pct(market)),
        "volatility": _score_crypto_volatility(market.change_30d_pct),
    }
    composite = sum(breakdown[k] * w for k, w in config.SCORING_WEIGHTS_CRYPTO.items())

    return ScoredSymbol(
        symbol=symbol,
        asset_class="crypto",
        group=group,
        composite_score=round(composite, 1),
        score_breakdown={k: round(v, 1) for k, v in breakdown.items()},
        price=market.price,
        day_change_pct=market.change_7d_pct,
        data_quality_notes=notes,
    )
