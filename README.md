# Capitol Trades Benchmark
<p align="center">
  <img src="image.png" alt="Capitol Trades Benchmark" width="300"/>
</p>

Track U.S. House of Representatives stock trades, reconstruct each member's portfolio, and benchmark their returns against major market indices (SPY, QQQ, etc.) — served through a FastAPI dashboard with Chart.js visualisations and optional Telegram alerts.

---

## Why you can trust the numbers

Most "politician trade tracker" sites are black boxes: you see a leaderboard, but not where the data came from or how the return was computed. This project is deliberately the opposite.

### 1. The data comes straight from the source

- **Trades** are scraped from [disclosures-clerk.house.gov](https://disclosures-clerk.house.gov/) — the official U.S. House Periodic Transaction Report (PTR) system mandated by the STOCK Act. No third-party aggregator sits between the filing and the database. The scraper pulls the XML index and parses the original PDFs with `pdfplumber`.
- **Party and chamber** metadata comes from the [unitedstates/congress-legislators](https://github.com/unitedstates/congress-legislators) dataset — a community-maintained, version-controlled source of record used by many civic-tech projects.
- **Prices** come from Yahoo Finance via `yfinance`, with `auto_adjust=True` so closes are already split- and dividend-adjusted.

No premium APIs, no opaque scraping services, no "enriched" fields pulled from marketing databases. If a number is in the app, you can trace it back to a public, primary source.

### 2. The methodology is documented and auditable

Every non-trivial calculation is implemented as pure, testable code in [src/services/metrics.py](src/services/metrics.py) and [src/services/portfolio_calc.py](src/services/portfolio_calc.py):

| What | How it's computed |
|---|---|
| Trade amount | Midpoint of the STOCK Act disclosure range (industry standard — filings are bands, not exact dollars) |
| Share count | Fixed at the **reference-date price** (trade or filing date), never recomputed at current price — this is what makes a return-over-range arithmetically honest |
| Returns | Configurable window: 1D / 5D / 1M / 6M / YTD / 1Y / 5Y / MAX |
| Risk metrics | CAGR, volatility, Sharpe ratio, max drawdown, CAPM beta & alpha — all against aligned daily price series |
| Risk-free rate | Configurable via `RISK_FREE_RATE` env var (default 4%) |
| Comparison mode | `trade` (actual performance from trade date) vs `filing` (what a replicator could have done from the disclosure date) |

The `filing` mode matters: politicians have up to 45 days to disclose a trade, so returns measured from the trade date are not replicable by the public. The app exposes both so you can see the gap.

### 3. Deduplication is explicit

Trades are de-duplicated with a composite key: `politician_id + ticker + trade_date + amount_from + amount_to + trade_type`. Re-running the scraper cannot double-count.

### 4. It's open source

Every line that touches data ingestion, storage, and return math is in this repository. If you disagree with a methodological choice, you can read the code, open an issue, or fork it.

---

## What it does

- Scrapes House PTR filings every hour and stores them in SQLite (WAL mode)
- Fetches daily closing prices for every traded ticker and 6 benchmark indices every 30 minutes
- Reconstructs each politician's portfolio over time and computes realised/unrealised P&L
- Compares each politician's time-weighted return against user-selectable benchmarks
- Surfaces risk-adjusted metrics (Sharpe, beta, alpha, drawdown) per politician
- Ranks politicians on a leaderboard by excess return vs benchmark
- Sends Telegram alerts when a subscribed politician files a new trade (optional)

---

## Quick start

```bash
# 1. Clone and install
git clone <your-fork-url>
cd CapitolTradesBenchmark
pip install -e ".[dev]"

# 2. Configure
cp .env.example .env
# edit .env — only Telegram keys are strictly optional; the app runs without API keys
# because House PTR scraping and yfinance need none.

# 3. Seed historical data (House PTRs from 2024-01-01 to today)
python seed_database.py

# 4. Run
python main.py
# → FastAPI on http://localhost:8000
# → APScheduler starts hourly trade scrapes + 30-min price updates
```

Open `http://localhost:8000` for the dashboard.

---

## Stack

- **FastAPI** + **Uvicorn** — async web layer
- **SQLite** (WAL mode) — single-file DB, no external services needed
- **APScheduler** — background jobs for scraping and price updates
- **pdfplumber** — parses House PTR PDFs
- **yfinance** + **pandas** — prices and series math
- **Chart.js** — frontend visualisations (no heavy frontend framework)
- **python-telegram-bot** — optional alerts, gracefully falls back to mock mode when unconfigured

---

## API

All routes live under `/api` except `/health` and `/`.

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

---

## Project layout

```
src/
├── scraper/     # house_scraper, price_fetcher, fmp_enrichment, finnhub_client
├── services/    # portfolio_calc, index_compare, metrics, alert_service, trade_service
├── db/          # database (schema + WAL setup), repositories
├── api/         # FastAPI routers
├── models/      # Pydantic models
└── telegram/    # send-only bot
```

### Module responsibilities

| Module | Responsibility |
|---|---|
| `src/models/` | Pydantic models: `Politician`, `Trade`, `Price`, `Portfolio`, `Holding`, `ProfitRecord`, `TelegramSubscription`; `Party`/`Chamber`/`TradeType` enums |
| `src/scraper/house_scraper.py` | Scrapes House PTR XML index and parses PDFs via `pdfplumber` |
| `src/scraper/price_fetcher.py` | yfinance batch fetching with in-memory cache |
| `src/scraper/fmp_enrichment.py` | Party/chamber lookup from congress-legislators dataset |
| `src/services/portfolio_calc.py` | Portfolio reconstruction, P&L, daily series |
| `src/services/index_compare.py` | Benchmark series, date-range helpers, normalised return series |
| `src/services/metrics.py` | Pure numerical: CAGR, Sharpe, beta, alpha, drawdown (no DB, no async) |
| `src/services/alert_service.py` | Formats and dispatches Telegram alerts on new trades |
| `src/services/trade_service.py` | Orchestrates House scraper → deduplication → DB storage |
| `src/db/database.py` | WAL setup, schema DDL, async connection lifecycle |
| `src/db/repositories.py` | `PoliticianRepository`, `TradeRepository`, `PriceRepository`, `SubscriptionRepository` |
| `src/api/` | FastAPI routers wired together in `app.py`; mounts `static/` |
| `src/telegram/bot.py` | Send-only Telegram bot with mock fallback |
| `scheduler.py` | APScheduler: hourly trade scrape + 30-min price update |

---

## Testing

```bash
pytest tests/                  # all tests
pytest tests/unit/             # unit only
pytest tests/integration/      # integration (hits real SQLite)
pytest --cov=src               # coverage report
```

---

## Known limitations — stated up front

- **House only.** Senate disclosures use a different filing system and are not yet scraped.
- **Disclosure ranges are wide.** The STOCK Act reports trades in bands ($1k–$15k, $15k–$50k, etc.). Midpoint is the standard estimator but it has real error bars. Returns are accurate; *dollar* P&L figures are approximate by construction.
- **No insider-trading claim.** This tool shows outcomes, not intent. A politician beating SPY does not imply non-public information was used.
- **Finnhub client exists but is not wired in** — the congressional endpoint sits behind a premium tier. The House scraper covers the same ground for free.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Contributing

Issues and PRs welcome. If you spot a methodological bug in the return math, please open an issue with a concrete reproduction — the whole point of this project is that calculations stay auditable.
