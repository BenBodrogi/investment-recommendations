# investment-recommendations

A periodically-refreshed dashboard of balanced-risk investment recommendations
across stocks, ETFs, and crypto, built from free financial APIs and published
as a Claude Artifact.

---

## Project structure

```
investment-recommendations/
├── .env                     # gitignored — real secrets
├── .env.example             # every key documented with a signup link
├── config.py                 # all constants: URLs, weights, thresholds, disclaimers
├── watchlist.yaml            # curated, user-editable ~40-symbol universe
├── requirements.txt
├── run_pipeline.py           # CLI entry point — fetch -> score -> deep-dive -> JSON
├── data/                     # one API client wrapper per source
│   ├── errors.py               # DataSourceError — normalizes all 5 clients' failures
│   ├── watchlist.py             # loads/validates watchlist.yaml
│   ├── finnhub_client.py
│   ├── coingecko_client.py
│   ├── fred_client.py
│   ├── edgar_client.py
│   └── marketaux_client.py
├── intelligence/              # scoring & analysis
│   ├── composite_scorer.py      # balanced multi-factor score, whole watchlist
│   ├── selector.py               # top-N-per-asset-class
│   ├── macro_context.py          # FRED snapshot -> backdrop narrative
│   ├── return_estimator.py       # heuristic return estimate + range
│   └── deep_dive.py              # situation/strengths/weaknesses assembly
├── dashboard/
│   └── payload_builder.py        # assembles the final JSON — never touches HTML
└── output/                    # gitignored, created at runtime
    ├── dashboard_data.json         # stable contract, overwritten every run
    └── cik_lookup_cache.json       # SEC ticker->CIK cache (~7 day refresh)
```

---

## Setup

### 1. Create and activate a virtual environment
```
python -m venv .venv
.venv\Scripts\activate
```

### 2. Install dependencies
```
pip install -r requirements.txt
```

### 3. Configure environment variables
Copy `.env.example` to `.env` and fill in each key (see [Data sources](#data-sources)
below for signup links). `SEC_EDGAR_USER_AGENT` needs no signup, just a
descriptive string in `"app-name your-email"` format.

### 4. Run the pipeline
```
python run_pipeline.py
```
Writes `output/dashboard_data.json`. Publishing that data as a Claude Artifact
and scheduling recurring runs are separate steps, done outside this codebase
(see Status below) — Python has no way to call Claude's Artifact tool, so a
Claude session has to be the one to read this file and publish/refresh the
dashboard.

Useful flags for manual iteration:
- `--skip-deep-dive` — broad screen only, skips the slower per-candidate enrichment
- `--watchlist path/to/file.yaml` — use an alternate watchlist
- `--log-level DEBUG` — verbose logging

---

## Watchlist

Edit `watchlist.yaml` freely — it's re-read on every run. Starter composition:
26 stocks across 6 sectors (Technology, Healthcare, Financials, Consumer,
Energy/Industrials, Defensive/Income), 9 ETFs (broad market, sector, dividend,
international, bond, commodity), 5 major crypto (BTC, ETH, SOL, ADA, LINK).

---

## Scoring methodology

Balanced-risk framing: every factor is weighted equally by design, so no
single lens (growth, safety, income) dominates the composite score.

**Stocks & ETFs** (25% each):

| Factor | Signal | Sweet spot |
|---|---|---|
| Valuation | Trailing P/E | 10–20x |
| Momentum | Blended 13wk/26wk return | Up to +25%, decays past +45% |
| Volatility | Beta | 0.7–1.1 |
| Yield | Dividend yield | ~3.5%, decays as a yield-trap signal past 7% |

**Crypto** (no yield concept — weight redistributed):

| Factor | Weight | Signal |
|---|---|---|
| Valuation proxy | 30% | Distance from all-time high (sweet spot: -50% to -20%) |
| Momentum | 35% | Blended 7d/30d change |
| Volatility proxy | 35% | Magnitude of 30d swing (bigger swing -> lower score) |

Missing fundamentals (common for ETFs) default the affected sub-score to
neutral (50) rather than dropping the symbol — logged under `data_quality`
in the output JSON, never silently swallowed.

**Return estimate**: `0.4 × annualized trailing trend + 0.4 × asset-class
base rate + 0.2 × dividend yield`, ± a volatility-scaled spread. This is a
transparent heuristic blend, not a model — no Monte Carlo, no ML — and every
estimate carries an explicit "rough estimate, not a prediction" caveat.

---

## Data sources

| Source | Provides | Key required | Scope |
|---|---|---|---|
| [Finnhub](https://finnhub.io/register) | Quotes, fundamentals, earnings calendar | Yes (free) | Whole watchlist |
| [CoinGecko](https://www.coingecko.com/en/api) | Crypto market data | No | Whole crypto watchlist |
| [FRED](https://fred.stlouisfed.org/docs/api/api_key.html) | Macro backdrop | Yes (free) | Once per run |
| [SEC EDGAR](https://www.sec.gov/os/accessing-edgar-data) | Authoritative fundamentals | No (User-Agent required) | Deep-dive stocks only |
| [MarketAux](https://www.marketaux.com/account/dashboard) | News/sentiment | Yes (free, no card) | Deep-dive candidates only |

---

## Disclaimer

This dashboard is generated by an automated heuristic pipeline for research
and educational purposes only. It is not financial advice, and nothing here
comes from a licensed financial advisor. Always do your own research and
consult a licensed professional before making investment decisions.

---

## Status

| Phase | Status | Description |
|---|---|---|
| 1 | Done | Pipeline: fetch, score, deep-dive, write JSON — verified end-to-end |
| 2 | Next | Recurring Claude Code scheduled session republishes the dashboard Artifact |
