"""Selects the single top-scoring symbol across the whole watchlist, with
hysteresis against the previous run's pick so the featured choice doesn't
flip on ordinary day-to-day score movement."""
import json
import os

import config
from intelligence.composite_scorer import ScoredSymbol


def _load_previous_pick_symbol(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            previous = json.load(f)
        return previous.get("best_choice", {}).get("symbol")
    except (OSError, ValueError):
        return None


def determine_best_choice(scored_symbols: list[ScoredSymbol], previous_path: str = None) -> ScoredSymbol:
    """Keeps showing the previous pick unless it's dropped out of this run's
    watchlist, or a new leader beats its current score by more than
    config.BEST_CHOICE_SWITCH_MARGIN."""
    ranked = sorted(scored_symbols, key=lambda s: s.composite_score, reverse=True)
    current_leader = ranked[0]

    path = previous_path or os.path.join(config.OUTPUT_DIR, config.OUTPUT_FILENAME)
    previous_symbol = _load_previous_pick_symbol(path)
    if previous_symbol is None:
        return current_leader

    incumbent = next((s for s in ranked if s.symbol == previous_symbol), None)
    if incumbent is None:
        return current_leader  # previous pick is no longer in this run's data

    if current_leader.composite_score - incumbent.composite_score > config.BEST_CHOICE_SWITCH_MARGIN:
        return current_leader
    return incumbent
