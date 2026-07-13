from dataclasses import dataclass, field

from data.coingecko_client import CryptoMarket
from data.edgar_client import CompanyFacts
from data.finnhub_client import Metrics, Quote
from data.marketaux_client import NewsSentiment
from intelligence.composite_scorer import (
    ScoredSymbol,
    blended_crypto_return_pct,
    blended_equity_return_pct,
)
from intelligence.macro_context import MacroSnapshot
from intelligence.return_estimator import ReturnEstimate, estimate_return

_SENTIMENT_POSITIVE = 0.15
_SENTIMENT_NEGATIVE = -0.15
_SCORE_STRONG = 70
_SCORE_WEAK = 30


@dataclass
class DeepDive:
    symbol: str
    asset_class: str
    group: str
    composite_score: float
    score_breakdown: dict
    price: float
    current_situation: str
    strengths: list
    weaknesses: list
    return_estimate: ReturnEstimate
    sections_omitted: list = field(default_factory=list)


def _news_line(news: NewsSentiment | None, sections_omitted: list) -> str | None:
    if news is None:
        sections_omitted.append("news_sentiment")
        return None
    if not news.headlines:
        return "No recent news coverage found in the lookback window."
    if news.average_sentiment is None:
        return f"Recent headline: “{news.headlines[0]}” (sentiment unscored)."
    tone = "positive" if news.average_sentiment > _SENTIMENT_POSITIVE else (
        "negative" if news.average_sentiment < _SENTIMENT_NEGATIVE else "mixed/neutral"
    )
    return f"Recent news sentiment skews {tone} (headline: “{news.headlines[0]}”)."


def build_equity_deep_dive(
    scored: ScoredSymbol,
    metrics: Metrics | None,
    company_facts: CompanyFacts | None,
    news: NewsSentiment | None,
    macro: MacroSnapshot,
    earnings_date: str | None,
) -> DeepDive:
    sections_omitted = list(scored.data_quality_notes)
    b = scored.score_breakdown
    pe = metrics.pe_ttm if metrics else None
    beta = metrics.beta if metrics else None
    dividend_yield = metrics.dividend_yield_pct if metrics else None

    situation_parts = [
        f"{scored.symbol} trades at ${scored.price:,.2f} "
        f"({scored.day_change_pct:+.1f}% today), {scored.group} sector."
    ]
    if earnings_date:
        situation_parts.append(f"Next earnings expected around {earnings_date}.")
    if company_facts and company_facts.revenue:
        margin_str = (
            f", net margin {company_facts.net_margin_pct:.1f}%"
            if company_facts.net_margin_pct is not None else ""
        )
        situation_parts.append(
            f"Latest 10-K revenue was ${company_facts.revenue / 1e9:,.1f}B "
            f"(period ending {company_facts.revenue_period_end}){margin_str}."
        )
    elif scored.asset_class == "stock":
        # Covers both company_facts is None (fetch failed) and company_facts
        # existing but revenue being None (stale/mistagged concept filtered
        # out by edgar_client). Not flagged for ETFs — company-facts isn't
        # fetched for them in the first place (funds don't file 10-Ks).
        sections_omitted.append("sec_edgar_fundamentals")
    news_line = _news_line(news, sections_omitted)
    if news_line:
        situation_parts.append(news_line)
    situation_parts.append(macro.narrative)

    strengths, weaknesses = [], []
    if b["valuation"] >= _SCORE_STRONG and pe is not None:
        strengths.append(f"Valuation looks reasonable — P/E of {pe:.1f}, near the historically comfortable 10–20x range.")
    elif b["valuation"] <= _SCORE_WEAK:
        if pe is not None and pe <= 0:
            weaknesses.append("Currently unprofitable on a trailing basis, so P/E isn't meaningful — valuation can't be grounded in current earnings.")
        elif pe is not None:
            weaknesses.append(f"Rich valuation — P/E of {pe:.1f} is well above the comfortable range, raising the bar for continued growth.")

    if b["momentum"] >= _SCORE_STRONG:
        strengths.append("Positive recent price trend over the trailing 13/26-week window.")
    elif b["momentum"] <= _SCORE_WEAK:
        weaknesses.append("Negative or weak recent price trend over the trailing 13/26-week window.")

    if b["volatility"] >= _SCORE_STRONG and beta is not None:
        strengths.append(f"Beta of {beta:.2f} — volatility close to the broad market, not prone to outsized swings.")
    elif b["volatility"] <= _SCORE_WEAK and beta is not None:
        descriptor = "notably higher" if beta > 1.1 else "unusually low"
        weaknesses.append(f"Beta of {beta:.2f} is {descriptor} than the broad-market sweet spot, adding volatility risk to the picture.")

    if b["yield"] >= _SCORE_STRONG and dividend_yield:
        strengths.append(f"Dividend yield of {dividend_yield:.1f}% sits in an attractive, sustainable-looking range.")
    elif dividend_yield and dividend_yield > 0 and b["yield"] <= _SCORE_WEAK:
        weaknesses.append(f"Dividend yield of {dividend_yield:.1f}% is high enough to raise a yield-trap question — worth checking payout sustainability.")
    elif not dividend_yield:
        weaknesses.append("Pays no meaningful dividend — total return here depends entirely on price appreciation.")

    if company_facts and company_facts.net_margin_pct is not None:
        if company_facts.net_margin_pct >= 15:
            strengths.append(f"Healthy net margin of {company_facts.net_margin_pct:.1f}% per its latest annual filing.")
        elif company_facts.net_margin_pct < 5:
            weaknesses.append(f"Thin net margin of {company_facts.net_margin_pct:.1f}% per its latest annual filing — limited buffer if costs rise.")

    if news and news.average_sentiment is not None:
        if news.average_sentiment > _SENTIMENT_POSITIVE:
            strengths.append("Recent news coverage skews positive.")
        elif news.average_sentiment < _SENTIMENT_NEGATIVE:
            weaknesses.append("Recent news coverage skews negative.")

    if not strengths:
        strengths.append("No standout strengths from current data — a middling profile across every factor measured.")
    if not weaknesses:
        weaknesses.append("No major red flags from current data, though a lack of weaknesses is itself worth double-checking against your own research.")

    etf_category = scored.group if scored.asset_class == "etf" else None
    return_estimate = estimate_return(
        asset_class=scored.asset_class,
        trend_annualized_pct=(
            ((1 + blended_equity_return_pct(metrics) / 100) ** 2 - 1) * 100
            if blended_equity_return_pct(metrics) is not None else 0.0
        ),
        dividend_yield_pct=dividend_yield,
        normalized_volatility=(100 - b["volatility"]) / 100,
        etf_category=etf_category,
    )

    return DeepDive(
        symbol=scored.symbol,
        asset_class=scored.asset_class,
        group=scored.group,
        composite_score=scored.composite_score,
        score_breakdown=scored.score_breakdown,
        price=scored.price,
        current_situation=" ".join(situation_parts),
        strengths=strengths,
        weaknesses=weaknesses,
        return_estimate=return_estimate,
        sections_omitted=sections_omitted,
    )


def build_crypto_deep_dive(
    scored: ScoredSymbol,
    market: CryptoMarket,
    news: NewsSentiment | None,
    macro: MacroSnapshot,
) -> DeepDive:
    sections_omitted = list(scored.data_quality_notes)
    b = scored.score_breakdown

    situation_parts = [
        f"{scored.symbol} trades at ${market.price:,.2f}, "
        f"{market.ath_change_percentage:+.1f}% off its all-time high."
    ]
    news_line = _news_line(news, sections_omitted)
    if news_line:
        situation_parts.append(news_line)
    situation_parts.append(macro.narrative)

    strengths, weaknesses = [], []
    if b["valuation"] >= _SCORE_STRONG:
        strengths.append(f"Trading {abs(market.ath_change_percentage):.0f}% below its all-time high — a real discount without looking structurally broken.")
    elif b["valuation"] <= _SCORE_WEAK:
        if market.ath_change_percentage > -20:
            weaknesses.append("Trading close to its all-time high, leaving little margin of safety if sentiment turns.")
        else:
            weaknesses.append(f"Trading {abs(market.ath_change_percentage):.0f}% below its all-time high — deep enough that it may reflect a structural setback, not just a discount.")

    if b["momentum"] >= _SCORE_STRONG:
        strengths.append("Positive recent momentum over the trailing 7/30-day window.")
    elif b["momentum"] <= _SCORE_WEAK:
        weaknesses.append("Negative or weak recent momentum over the trailing 7/30-day window.")

    if b["volatility"] >= _SCORE_STRONG:
        strengths.append("30-day price swings have been comparatively contained for a crypto asset.")
    elif b["volatility"] <= _SCORE_WEAK:
        weaknesses.append("Large 30-day price swings — elevated volatility even by crypto standards.")

    if news and news.average_sentiment is not None:
        if news.average_sentiment > _SENTIMENT_POSITIVE:
            strengths.append("Recent news coverage skews positive.")
        elif news.average_sentiment < _SENTIMENT_NEGATIVE:
            weaknesses.append("Recent news coverage skews negative.")

    if not strengths:
        strengths.append("No standout strengths from current data — a middling profile across every factor measured.")
    if not weaknesses:
        weaknesses.append("No major red flags from current data, though a lack of weaknesses is itself worth double-checking against your own research.")

    blended = blended_crypto_return_pct(market)
    return_estimate = estimate_return(
        asset_class="crypto",
        trend_annualized_pct=((1 + blended / 100) ** 12 - 1) * 100 if blended is not None else 0.0,
        dividend_yield_pct=None,
        normalized_volatility=(100 - b["volatility"]) / 100,
    )

    return DeepDive(
        symbol=scored.symbol,
        asset_class="crypto",
        group=scored.group,
        composite_score=scored.composite_score,
        score_breakdown=scored.score_breakdown,
        price=market.price,
        current_situation=" ".join(situation_parts),
        strengths=strengths,
        weaknesses=weaknesses,
        return_estimate=return_estimate,
        sections_omitted=sections_omitted,
    )
