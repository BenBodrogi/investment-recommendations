"""Selects the single top-scoring symbol across the whole watchlist, with
hysteresis against the previous run's pick so the featured choice doesn't
flip on ordinary day-to-day score movement - but only once that pick has
been confirmed by a run with reasonably complete data. A pick crowned
during a degraded run (most of the watchlist failed to score) never gets
hysteresis protection; the next run re-evaluates it freely regardless of
margin, since it was never actually compared against the full field."""
import json
import os

import config
from intelligence.composite_scorer import ScoredSymbol


def _load_previous_pick(path: str) -> tuple[str | None, bool]:
    """Returns (symbol, confirmed). confirmed defaults to False when the
    field is missing (a file written before this logic existed), so the
    first run after this ships always re-evaluates freely once."""
    if not os.path.exists(path):
        return None, False
    try:
        with open(path, "r", encoding="utf-8") as f:
            previous = json.load(f)
    except (OSError, ValueError):
        return None, False
    symbol = previous.get("best_choice", {}).get("symbol")
    confirmed = bool(previous.get("best_choice_confirmed", False))
    return symbol, confirmed


def determine_best_choice(
    scored_symbols: list[ScoredSymbol], skipped_count: int, previous_path: str = None
) -> tuple[ScoredSymbol, bool]:
    """Returns (pick, confirmed). confirmed reflects whether *this* run's
    coverage was complete enough for the pick to earn hysteresis protection
    next time - independent of whether hysteresis applied this time."""
    ranked = sorted(scored_symbols, key=lambda s: s.composite_score, reverse=True)
    current_leader = ranked[0]

    total_attempted = len(scored_symbols) + skipped_count
    coverage_pct = (len(scored_symbols) / total_attempted * 100) if total_attempted else 0
    this_run_confirmed = coverage_pct >= config.BEST_CHOICE_MIN_COVERAGE_PCT

    path = previous_path or os.path.join(config.OUTPUT_DIR, config.OUTPUT_FILENAME)
    previous_symbol, previous_confirmed = _load_previous_pick(path)

    if previous_symbol is None or not previous_confirmed:
        return current_leader, this_run_confirmed

    incumbent = next((s for s in ranked if s.symbol == previous_symbol), None)
    if incumbent is None:
        return current_leader, this_run_confirmed  # previous pick is no longer in this run's data

    if current_leader.composite_score - incumbent.composite_score > config.BEST_CHOICE_SWITCH_MARGIN:
        return current_leader, this_run_confirmed
    return incumbent, this_run_confirmed
