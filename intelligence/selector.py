import config
from intelligence.composite_scorer import ScoredSymbol


def select_top_n(scored_symbols: list[ScoredSymbol]) -> dict:
    """Top N per asset class (config.DEEP_DIVE_TOP_N) become deep-dive candidates."""
    result = {}
    for asset_class, n in config.DEEP_DIVE_TOP_N.items():
        candidates = [s for s in scored_symbols if s.asset_class == asset_class]
        candidates.sort(key=lambda s: s.composite_score, reverse=True)
        result[asset_class] = candidates[:n]
    return result
