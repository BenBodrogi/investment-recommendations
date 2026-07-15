#!/usr/bin/env python
"""Entry point: fetch -> score -> deep-dive -> write dashboard-web/data/dashboard_data.json.

Always writes to the same fixed path and exits 0 on partial-data runs
(degrades gracefully). Exits non-zero only if the watchlist fails to load
or zero symbols score at all. Prints RESULT_PATH=<path> as a final,
parseable confirmation line. Run on a schedule by
.github/workflows/refresh-dashboard.yml, which commits the result so Vercel
redeploys with fresh data.
"""
import argparse
import logging
import sys
import time

from dotenv import load_dotenv

import config
from data import coingecko_client, edgar_client, finnhub_client, marketaux_client, sp500_client
from data.errors import DataSourceError
from data.watchlist import WatchlistEntry, load_watchlist
from dashboard import payload_builder
from intelligence import best_choice, composite_scorer, deep_dive, macro_context, selector

logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--watchlist", default=None,
        help="Path to watchlist YAML. If given, discovery is skipped entirely and only this "
             "file's manual entries are used (fast path for local iteration). If omitted, the "
             "default watchlist.yaml is merged with auto-discovered S&P 500 stocks and top-N "
             "crypto by market cap.",
    )
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--skip-deep-dive", action="store_true", help="Skip deep-dive enrichment (faster iteration)")
    parser.add_argument(
        "--print-universe-only", action="store_true",
        help="Build the universe (manual + discovered) and print counts, then exit - no API "
             "calls beyond discovery itself, no scoring.",
    )
    return parser.parse_args()


def build_universe(explicit_watchlist_path: str | None) -> list[WatchlistEntry]:
    """Manual watchlist.yaml entries, merged with auto-discovered S&P 500
    stocks and top-N crypto by market cap - unless a watchlist path was
    explicitly passed, in which case discovery is skipped and only that
    file's entries are used (the fast path for local iteration)."""
    manual_entries = load_watchlist(explicit_watchlist_path)
    if explicit_watchlist_path is not None:
        return manual_entries

    entries = list(manual_entries)
    seen_stock_symbols = {e.symbol for e in entries if e.asset_class == "stock"}
    seen_crypto_ids = {e.coingecko_id for e in entries if e.asset_class == "crypto"}

    try:
        for row in sp500_client.get_sp500_constituents():
            if row["symbol"] not in seen_stock_symbols:
                entries.append(WatchlistEntry(symbol=row["symbol"], asset_class="stock", group=row["sector"]))
                seen_stock_symbols.add(row["symbol"])
    except DataSourceError as exc:
        logger.warning("S&P 500 discovery unavailable this run, falling back to manual stocks only: %s", exc)

    try:
        for cg_id, symbol in coingecko_client.get_top_market_ids(config.CRYPTO_DISCOVERY_TOP_N):
            if cg_id not in seen_crypto_ids:
                entries.append(WatchlistEntry(symbol=symbol, asset_class="crypto", group="Discovered", coingecko_id=cg_id))
                seen_crypto_ids.add(cg_id)
    except DataSourceError as exc:
        logger.warning("Crypto discovery unavailable this run, falling back to manual crypto only: %s", exc)

    return entries


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
        entries = build_universe(args.watchlist)
    except (OSError, ValueError) as exc:
        logger.error("Fatal: could not load watchlist: %s", exc)
        return 1

    if args.print_universe_only:
        by_class = {"stock": 0, "etf": 0, "crypto": 0}
        for e in entries:
            by_class[e.asset_class] += 1
        logger.info(
            "Universe: %d stocks, %d etfs, %d crypto (%d total)",
            by_class["stock"], by_class["etf"], by_class["crypto"], len(entries),
        )
        return 0

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

    best_choice_symbol, best_choice_confirmed = best_choice.determine_best_choice(
        scored_symbols, len(symbols_skipped)
    )
    payload = payload_builder.build_payload(
        scored_symbols, deep_dives, macro, data_quality, best_choice_symbol, best_choice_confirmed
    )
    result_path = payload_builder.write_payload(payload)

    logger.info(
        "Wrote %s (%d symbols scored, %d skipped, %.1fs)",
        result_path, len(scored_symbols), len(symbols_skipped), data_quality["run_duration_seconds"],
    )
    print(f"RESULT_PATH={result_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
