# investment-recommendations

A periodically-refreshed dashboard of balanced-risk investment recommendations
across stocks, ETFs, and crypto, built from free financial APIs. A GitHub
Actions cron job refreshes the data daily and a Next.js app
([dashboard-web/](dashboard-web/README.md)) deployed on Vercel serves it —
see [Deployment](#deployment).

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
│   ├── best_choice.py            # single featured pick, hysteresis-stabilized
│   ├── macro_context.py          # FRED snapshot -> backdrop narrative
│   ├── return_estimator.py       # heuristic return estimate + range
│   └── deep_dive.py              # situation/strengths/weaknesses assembly
├── dashboard/
│   └── payload_builder.py        # assembles the final JSON — never touches HTML
├── .github/workflows/
│   └── refresh-dashboard.yml     # daily cron: run pipeline, commit output, Vercel redeploys
├── dashboard-web/data/
│   └── dashboard_data.json       # stable contract, committed — Vercel serves this directly
└── output/                    # gitignored, created at runtime
    └── cik_lookup_cache.json       # SEC ticker->CIK cache (~7 day refresh), internal only
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
Writes `dashboard-web/data/dashboard_data.json`, which `dashboard-web` reads
directly. Locally, `dashboard-web`'s "Refresh now" button runs this same
command for you. In production, `.github/workflows/refresh-dashboard.yml`
runs it daily and commits the result, which Vercel picks up as a normal
push and redeploys — see [Deployment](#deployment) below.

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

**Best choice**: the single highest composite score across the *entire*
watchlist (any asset class). Re-evaluated on every run, but stabilized by
hysteresis (`config.BEST_CHOICE_SWITCH_MARGIN`, default 5 points) — the
featured pick only changes when a new leader clearly beats the incumbent's
current score, not on ordinary day-to-day noise. Not a calendar lock: there's
no expiry, just a switching threshold. See `intelligence/best_choice.py`.

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

## Deployment

Vercel's serverless functions can't run this pipeline directly — free-tier
functions cap at ~10s, Pro at 60-300s, and a real run takes ~90-150s. Instead:

1. `.github/workflows/refresh-dashboard.yml` runs daily (cron, plus a manual
   `workflow_dispatch` trigger) on a GitHub-hosted runner: checks out the
   repo, installs `requirements.txt`, runs `run_pipeline.py` with the 5 API
   keys from GitHub Actions secrets, and commits
   `dashboard-web/data/dashboard_data.json` if it changed.
2. That push is an ordinary commit to `main`, so Vercel's normal git
   integration redeploys automatically — no webhook or extra config.
3. `dashboard-web` reads the committed JSON directly (`lib/data.ts`,
   `process.cwd()`-relative), so Vercel never talks to the financial APIs
   and needs no environment variables of its own.

**One-time setup** (not automatable — both require your own account access):
- Add `FINNHUB_API_KEY`, `FRED_API_KEY`, `MARKETAUX_API_KEY`,
  `SEC_EDGAR_USER_AGENT`, `COINGECKO_API_KEY` as GitHub Actions secrets
  (repo Settings → Secrets and variables → Actions).
- Import this repo into Vercel as a new project with **Root Directory set
  to `dashboard-web`**; everything else can stay at Vercel's defaults.

The local "Refresh now" button only appears when `PIPELINE_PYTHON` is set
(i.e. in local dev via `dashboard-web/.env.local`) — the deployed site
shows "Data refreshes automatically" instead, since there's no local Python
process for it to spawn there.

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
| 2 | Built, not yet live | GitHub Actions + Vercel auto-deploy (see [Deployment](#deployment)) — code is in place; still needs your GitHub secrets added and the repo imported into Vercel before it's actually running on a schedule |
