# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

**Fully implemented.** All `src/` modules are live. The app scrapes U.S. House STOCK Act disclosures, stores trades and prices in SQLite, computes portfolio metrics and benchmark comparisons, and serves a Chart.js dashboard via FastAPI.

Read `PHASES.md` for the 6-phase roadmap and remaining work.

## Commands

```bash
# Install
pip install -e .            # runtime deps
pip install -e ".[dev]"     # + test/lint deps

# Run
python main.py              # FastAPI on port 8000 + APScheduler background jobs

# Seed with historical data (House PTRs, 2024-present)
python seed_database.py

# Test
pytest tests/               # all tests
pytest tests/unit/          # unit only
pytest tests/integration/   # integration only (hits real SQLite)
pytest -v tests/unit/test_models.py   # single file
pytest --cov=src            # coverage
```

Environment: copy `.env.example` → `.env` and fill in `FINNHUB_API_KEY`, `FMP_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

## Architecture

```
Browser (HTML + Chart.js)  ←→  static/
  └─ FastAPI  (see API Endpoints below)
       └─ Services  (portfolio_calc, index_compare, metrics, alert_service, trade_service)
            └─ Repositories  (PoliticianRepository, TradeRepository, PriceRepository,
                              SubscriptionRepository — all in src/db/repositories.py)
                 └─ SQLite  (WAL mode — concurrent FastAPI reads + APScheduler writes)

Background jobs (APScheduler):
  Every  1h  → HouseScraper    → disclosures-clerk.house.gov (free, no API key)
  Every 30m  → PriceFetcher    → yfinance (traded tickers + 6 benchmark indices)

Enrichment (on-demand):
  fmp_enrichment.py → unitedstates/congress-legislators GitHub dataset (party/chamber lookup)

Alerts (on new trades):
  TelegramBot → send-only, mock-mode when TELEGRAM_BOT_TOKEN is unset
```

**Finnhub** (`src/scraper/finnhub_client.py`) — client exists but not wired into the scheduler; congressional trading endpoint is premium-only on the free tier.

## API Endpoints

All routes live under the `/api` prefix except `/health` and `/`.

| Method | Path | Description |
|---|---|---|
| GET | `/api/politicians` | List all politicians with trade counts |
| GET | `/api/politicians/{id}/trades` | All trades for a politician |
| GET | `/api/politicians/{id}/portfolio` | Current portfolio snapshot |
| GET | `/api/politicians/{id}/metrics` | Risk metrics (CAGR, Sharpe, beta, alpha, drawdown) |
| GET | `/api/leaderboard` | Politicians ranked by return vs benchmark |
| GET | `/api/comparison` | Side-by-side politician vs benchmark series |
| GET | `/api/benchmarks` | Available benchmark tickers |
| GET | `/api/trades/recent` | Recent trades across all politicians |
| POST | `/api/admin/update-prices` | Trigger manual price refresh |
| POST | `/api/admin/enrich-parties` | Re-run party/chamber enrichment |
| GET | `/api/admin/debug-enrichment` | Inspect enrichment data |
| POST | `/api/admin/set-parties` | Manually set party for a politician |
| POST | `/api/subscriptions` | Create Telegram alert subscription |
| GET | `/api/subscriptions` | List subscriptions |
| DELETE | `/api/subscriptions/{id}` | Delete subscription |
| GET | `/health` | Health check |

## Key Technical Decisions

| Topic | Decision |
|---|---|
| Primary trade source | House PTR XML/PDF from `disclosures-clerk.house.gov` — free, official, no API key |
| Party/chamber lookup | `unitedstates/congress-legislators` JSON — free, no API key, updated each Congress |
| Trade amount | Midpoint of STOCK Act disclosure range (industry standard) |
| Deduplication | Composite unique key: `politician_id + ticker + trade_date + amount_from + amount_to + trade_type` |
| Returns | Configurable window: 1D / 5D / 1M / 6M / YTD / 1Y / 5Y / MAX |
| Share count | Fixed at **reference-date price** (trade_date or filing_date), never current price — required for arithmetically correct return-over-range |
| Risk metrics | CAGR, volatility, Sharpe, max drawdown, CAPM beta & alpha — computed in `src/services/metrics.py` against aligned daily price series |
| Risk-free rate | `RISK_FREE_RATE` env var (default 0.04 = 4%); used by Sharpe & alpha |
| Price adjustment | yfinance `auto_adjust=True` — `daily_prices.close` is already split/dividend-adjusted. Do not change without updating `metrics.py`. |
| Price history | 2 years fetched per price-update run; `INSERT OR IGNORE` makes repeats cheap |
| Comparison mode | `trade` (politician's actual performance) vs `filing` (replicable post-disclosure) — toggle via `?mode=` query param |
| Telegram | Gracefully falls back to mock/log mode when token is unset or invalid |
| DB concurrency | SQLite WAL satisfies FastAPI (reads) + APScheduler (writes) without extra infra |

## Module Responsibilities

- `src/models/` — Pydantic models: `Politician`, `Trade`, `Price`, `Portfolio`, `Holding`, `ProfitRecord`, `TelegramSubscription`; `Party`/`Chamber`/`TradeType` enums
- `src/scraper/`
  - `house_scraper.py` — scrapes House PTR XML index + parses PDFs via `pdfplumber`
  - `price_fetcher.py` — yfinance batch fetching with in-memory cache
  - `fmp_enrichment.py` — party/chamber lookup from congress-legislators dataset
  - `finnhub_client.py` — Finnhub congressional trading client (not active in scheduler)
- `src/services/`
  - `portfolio_calc.py` — portfolio reconstruction, P&L, daily series
  - `index_compare.py` — benchmark series, date-range helpers, normalised return series
  - `metrics.py` — pure numerical: CAGR, Sharpe, beta, alpha, drawdown (no DB, no async)
  - `alert_service.py` — formats and dispatches Telegram alerts on new trades
  - `trade_service.py` — orchestrates House scraper → deduplication → DB storage
- `src/db/`
  - `database.py` — WAL setup, schema DDL (`politicians`, `trades`, `daily_prices`, `subscriptions`), async connection lifecycle
  - `repositories.py` — all repository classes: `PoliticianRepository`, `TradeRepository`, `PriceRepository`, `SubscriptionRepository`
- `src/api/` — FastAPI routers (`routes_politicians`, `routes_portfolio`, `routes_subscriptions`, `routes_misc`); `app.py` wires them together and mounts `static/`
- `src/telegram/bot.py` — send-only Telegram bot with mock fallback
- `scheduler.py` — APScheduler wrapper: hourly trade scrape + 30-min price update
- `tests/conftest.py` — shared fixtures (sample politician / trade / price data)

## Database Schema

```sql
politicians   (id, name, party, chamber)
trades        (id, politician_id, politician_name, ticker, asset_name,
               trade_type, amount_from, amount_to, trade_date, filing_date)
daily_prices  (id, ticker, date, close)      -- stocks + benchmark indices
subscriptions (id, politician_id, telegram_chat_id, active, created_at)
```

`daily_prices` stores both individual tickers and benchmark indices (SPY, QQQ, etc.) so all return calculations use the same data path.

## Utility Scripts

| Script | Purpose |
|---|---|
| `seed_database.py` | Bulk-import House PTRs from 2024-01-01 to today |
| `probe_data_sources.py` | Quiverquant API probe (research — not used in app) |
| `scripts/probe_finnhub_depth.py` | Finnhub data-depth probe (premium wall confirmed) |
| `scripts/probe_house_depth.py` | House PTR depth/coverage probe |
| `scripts/import_trendlyne_mccaul.py` | One-off import from `mccaul_trades_raw.json` |
