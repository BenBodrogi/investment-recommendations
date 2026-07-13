# Handoff — investment-recommendations

Personal research tool: a Python pipeline pulls free financial APIs into a
balanced-risk investment recommendation dataset (stocks/ETFs/crypto), and a
Next.js app displays it with a one-click refresh. Written 2026-07-13.

## Status

**Working end-to-end, one open item to verify.**

- **Python pipeline** (`run_pipeline.py` + `data/`, `intelligence/`, `dashboard/`) —
  done, verified with real API keys across multiple runs. Screens a 40-symbol
  watchlist, deep-dives the top 5 stocks / 3 ETFs / 2 crypto, writes
  `output/dashboard_data.json`. See [README.md](README.md) for the full
  architecture, scoring methodology, and data sources.
- **Next.js dashboard** (`dashboard-web/`) — App Router + TypeScript + Tailwind +
  Recharts, matches the conventions in your `sentinel-dashboard` project. Reads
  the JSON, shows watchlist table + deep-dive cards + macro stat row, and a
  "Refresh now" button that spawns the Python pipeline via an SSE-streaming API
  route and reloads with fresh data.
- **⚠️ Open item**: the score-breakdown / return-estimate charts were
  overflowing their grid column (hardcoded Recharts `width={280}` wider than
  the actual container), causing overlapping text between the two columns of a
  deep-dive card. Fixed by switching both `ScoreBreakdownChart.tsx` and
  `ReturnRangeChart.tsx` to Recharts' `ResponsiveContainer`. The build compiles
  clean and the fix is the standard pattern for this exact problem, but I
  couldn't get a working screenshot tool to visually re-confirm it before this
  handoff (tooling issue, not app-related) — **check this first** on the new
  machine: run the dev server, open a deep-dive card, confirm the score
  breakdown and return estimate no longer overlap.
- **Not started** (deliberately deferred, see README "Status" table): a
  recurring scheduled refresh + publishing this as a Claude Artifact. That was
  the original plan before you asked for the Next.js app instead; "Both" is
  still the stated goal (Next.js for on-demand local use, Artifact/schedule for
  passive updates) but no work has been done on the schedule/Artifact side.

## Moving to a new machine

**Git state**: both `investment-recommendations/` and `dashboard-web/` have a
local `.git` (dashboard-web has one commit — the create-next-app scaffold —
everything since is uncommitted; the root repo has zero commits). If you want
to move via git, you'll need to commit first — ask me and I will, but I won't
do it unprompted. If you're moving via a direct copy/cloud-sync instead, read
on.

**Do not copy** (regenerate instead, both are machine-specific):
- `investment-recommendations/.venv/`
- `investment-recommendations/dashboard-web/node_modules/` and `.next/`

**Do copy despite being gitignored** (these hold your actual config/secrets,
git would silently leave them behind on a git-based move, and a naive
gitignore-respecting sync tool would too):
- `investment-recommendations/.env` — your real Finnhub/FRED/MarketAux keys
  and SEC User-Agent
- `investment-recommendations/dashboard-web/.env.local` — **has your OLD
  machine's absolute paths baked in** (`PIPELINE_DIR`, `PIPELINE_PYTHON`).
  These will be wrong on a new machine/username/drive letter — update them
  after copying, or just recreate from `.env.local.example` with the new
  paths.

**Setup on the new machine**, from `investment-recommendations/`:
```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```
Copy over `.env` (or recreate from `.env.example` + your existing keys).

Then from `investment-recommendations/dashboard-web/`:
```
npm install
```
Copy over `.env.local` and fix the two absolute paths, or recreate from
`.env.local.example`.

**Running it**:
- Manual pipeline run: `.venv\Scripts\python.exe run_pipeline.py` from the
  root (~90-150s, writes `output/dashboard_data.json`).
- Dashboard: `npm run dev` from `dashboard-web/`, open `localhost:3000`. The
  "Refresh now" button does the pipeline run for you and streams its log
  output live.
- A `.claude/launch.json` config named `investment-dashboard` already runs the
  dev server via `npm --prefix <path> run dev` if you're using the Browser
  preview tool - update the hardcoded path in that file too after moving.

## Bugs fixed this session (context if anything looks off)

- **Secret redaction**: Finnhub/FRED/MarketAux all authenticate via query-string
  params; a raw request exception embedded the key in its message. Fixed
  centrally in `data/errors.py`'s `DataSourceError`.
- **Stale/mismatched EDGAR fundamentals**: companies that migrated XBRL revenue
  concepts (e.g. NEE) could return years-stale data under a legacy tag. Fixed
  with a staleness cutoff and a same-fiscal-period check before computing
  margin, in `data/edgar_client.py`.
- **SSE refresh button showed a false "connection failed" error** even on a
  successful run — two compounding bugs in
  `dashboard-web/app/api/refresh/route.ts`: (1) `closed = true` was set
  *before* calling `send()`, which gates on `closed`, so the terminal
  "done"/"error" message was silently swallowed; (2) an aborted request (e.g.
  navigating away mid-refresh) could leave an orphaned Python process running
  in the background — `proc.kill()` doesn't reliably kill a process tree on
  Windows — and when it finished later, closing the already-closed stream
  controller threw an uncaught exception that could crash the dev server.
  Fixed with a centralized `safeClose()` guard and `taskkill /T /F` on
  Windows for abort cleanup.

## Reference

- Data sources, scoring formula, watchlist composition: [README.md](README.md)
- API signup links: `.env.example` (Finnhub, FRED, MarketAux all free)
- The approved build plan (useful for the "why" behind architectural choices
  like the JSON-contract split between Python and Next.js):
  `C:\Users\bodro\.claude\plans\replicated-imagining-bubble.md` — machine-local,
  won't travel with the project itself, but worth copying if you want it.
