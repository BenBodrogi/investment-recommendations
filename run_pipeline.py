#!/usr/bin/env python
"""Entry point: fetch -> score -> deep-dive -> write output/dashboard_data.json.

Always writes to the same fixed path and exits 0 on partial-data runs
(degrades gracefully). Exits non-zero only if the watchlist fails to load
or zero symbols score at all. Prints RESULT_PATH=<path> as a final,
parseable confirmation line - this is the contract a future scheduled
Claude session will rely on to find the output.
"""
import argparse
import logging
import sys
import time

from dotenv import load_dotenv

from data import coingecko_client, edgar_client, finnhub_client, marketaux_client
from data.errors import DataSourceError
from data.watchlist import load_watchlist
from dashboard import payload_builder
from intelligence import composite_scorer, deep_dive, macro_context, selector

logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watchlist", default=None, help="Path to watchlist YAML (default: config.WATCHLIST_PATH)")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--skip-deep-dive", action="store_true", help="Skip deep-dive enrichment (faster iteration)")
    return parser.parse_args()


def broad_screen(entries):
    """Lightweight quote+fundamentals pass across the whole watchlist."""
    scored = []
    symbols_skipped = []
    raw_data = {}  # symbol -> Metrics (equities) or CryptoMarket (crypto), reused during deep-dive

    crypto_entries = [e for e in entries if e.asset_class == "crypto"]
    equity_entries = [e for e in entries if e.asset_class != "crypto"]

    if crypto_entries:
        try:
            markets = coingecko_client.get_markets([e.coingecko_id for e in crypto_entries])
        except DataSourceError as exc:
            logger.warning("CoinGecko unavailable this run, skipping all crypto: %s", exc)
            markets = {}
        for e in crypto_entries:
            market = markets.get(e.coingecko_id)
            if market is None:
                symbols_skipped.append({"symbol": e.symbol, "reason": "CoinGecko had no data for this id"})
                continue
            scored.append(composite_scorer.score_crypto(e.symbol, e.group, market))
            raw_data[e.symbol] = market

    for e in equity_entries:
        try:
            quote = finnhub_client.get_quote(e.symbol)
        except DataSourceError as exc:
            symbols_skipped.append({"symbol": e.symbol, "reason": str(exc)})
            continue
        try:
            metrics = finnhub_client.get_metrics(e.symbol)
        except DataSourceError as exc:
            logger.info("Metrics unavailable for %s, scoring with neutral defaults: %s", e.symbol, exc)
            metrics = None
        scored.append(composite_scorer.score_equity(e.symbol, e.asset_class, e.group, quote, metrics))
        raw_data[e.symbol] = metrics

    return scored, symbols_skipped, raw_data


def build_deep_dives(top_candidates: dict, raw_data: dict, macro):
    """Richer, targeted enrichment for the top-N-per-asset-class only."""
    deep_dives = {}
    deep_dive_sections_omitted = []

    for asset_class, symbols in top_candidates.items():
        results = []
        for scored in symbols:
            news = None
            try:
                news = marketaux_client.get_news_sentiment(scored.symbol)
            except DataSourceError as exc:
                logger.info("MarketAux unavailable for %s: %s", scored.symbol, exc)

            if asset_class == "crypto":
                market = raw_data.get(scored.symbol)
                dive = deep_dive.build_crypto_deep_dive(scored, market, news, macro)
            else:
                metrics = raw_data.get(scored.symbol)
                earnings_date = None
                company_facts = None
                if asset_class == "stock":
                    try:
                        earnings_date = finnhub_client.get_next_earnings_date(scored.symbol)
                    except DataSourceError as exc:
                        logger.info("Earnings calendar unavailable for %s: %s", scored.symbol, exc)
                    try:
                        company_facts = edgar_client.get_company_facts(scored.symbol)
                    except DataSourceError as exc:
                        logger.info("EDGAR unavailable for %s: %s", scored.symbol, exc)
                dive = deep_dive.build_equity_deep_dive(scored, metrics, company_facts, news, macro, earnings_date)

            for section in dive.sections_omitted:
                deep_dive_sections_omitted.append({"symbol": scored.symbol, "section": section})
            results.append(dive)
        deep_dives[asset_class] = results

    return deep_dives, deep_dive_sections_omitted


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    load_dotenv()

    start = time.monotonic()

    try:
        entries = load_watchlist(args.watchlist)
    except (OSError, ValueError) as exc:
        logger.error("Fatal: could not load watchlist: %s", exc)
        return 1

    scored_symbols, symbols_skipped, raw_data = broad_screen(entries)
    if not scored_symbols:
        logger.error("Fatal: zero symbols scored this run - check Finnhub/CoinGecko connectivity and API keys.")
        return 1

    macro = macro_context.get_macro_snapshot()

    deep_dives = {}
    deep_dive_sections_omitted = []
    if not args.skip_deep_dive:
        top_candidates = selector.select_top_n(scored_symbols)
        deep_dives, deep_dive_sections_omitted = build_deep_dives(top_candidates, raw_data, macro)

    data_quality = {
        "sources_attempted": ["finnhub", "coingecko", "fred", "edgar", "marketaux"],
        "sources_fully_unavailable": list(macro.unavailable_series),
        "symbols_skipped": symbols_skipped,
        "deep_dive_sections_omitted": deep_dive_sections_omitted,
        "run_duration_seconds": round(time.monotonic() - start, 1),
    }

    payload = payload_builder.build_payload(scored_symbols, deep_dives, macro, data_quality)
    result_path = payload_builder.write_payload(payload)

    logger.info(
        "Wrote %s (%d symbols scored, %d skipped, %.1fs)",
        result_path, len(scored_symbols), len(symbols_skipped), data_quality["run_duration_seconds"],
    )
    print(f"RESULT_PATH={result_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
