# Capitol Trade Follower — Implementation Phases

Phased roadmap for building the app locally first, then Docker at the end.

---

## Phase 1: Foundation & Data Layer (Highest Risk First)

**Goal:** Validate that Finnhub API works and establish database schema.

**Critical tasks:**
1. Create `pyproject.toml` with dependencies:
   - `aiosqlite`, `fastapi`, `uvicorn`, `pydantic`
   - `yfinance`, `pandas`
   - `python-telegram-bot`
   - `apscheduler`
   - `requests` (for Finnhub API calls)

2. Create `.env.example` and `.env` (gitignored) with API keys:
   - `FINNHUB_API_KEY=d7hpb7pr01qirk40goe0d7hpb7pr01qirk40goeg`
   - `FMP_API_KEY=DT2ZvEUfmIMVpMbjWTOnQvUxasqO6clL` (enrichment only)
   - `TELEGRAM_BOT_TOKEN=MOCK_TOKEN_REPLACE_ME`
   - `TELEGRAM_CHAT_ID=` (user provides later)

3. Set up `src/models/`:
   - `politician.py` — `Politician`, `Party` (enum: D/R), `Chamber` (enum: Senate/House)
   - `trade.py` — `Trade`, `TradeType` (enum: BUY/SELL)
   - `portfolio.py` — `Portfolio`, `Holding`, `ProfitRecord`
   - `subscription.py` — `TelegramSubscription`

4. Implement `src/db/database.py`:
   - SQLite connection + **WAL mode**
   - Schema for: `politicians`, `trades`, `daily_prices`, `subscriptions`, `scrape_log`
   - Auto-migration on first run

5. Implement `src/db/repositories.py`:
   - CRUD operations using Pydantic models
   - Trade deduplication by `(politician_id, ticker, trade_date, tx_type)`
   - Batch price inserts

6. **Spike: Test Finnhub API**
   - Implement `src/scraper/finnhub_client.py`
   - Call Finnhub CongressionalTrading endpoint
   - Verify response structure + parse trades
   - Store 10 trades in DB
   - **DECISION GATE:** Does Finnhub work? If not, fall back to Capitol Trades wrappers before continuing.

7. Implement `src/scraper/price_fetcher.py`:
   - Fetch historical prices from yfinance for politician holdings + benchmarks
   - Cache in `daily_prices` table
   - Test with 5 tickers + S&P 500

**Deliverable:** App can fetch trades from Finnhub, store them, and fetch prices locally. Database populated with sample data.

**Time estimate:** 3-4 days

---

## Phase 2: Business Logic (Portfolio Calculations)

**Goal:** Calculate politician returns accurately over user-selected time ranges.

**Tasks:**
1. Implement `src/services/portfolio_calc.py`:
   - Reconstruct portfolio from trade history (sorted by trade_date)
   - **Midpoint estimation:** use midpoint of STOCK Act disclosure range
   - Calculate:
     - Current portfolio value (mark-to-market using latest prices)
     - Total P&L (realized + unrealized)
     - Return % over selected time range
     - Per-holding breakdown
   - **Unit tests:** given trades + prices → expected P&L

2. Implement `src/services/index_compare.py`:
   - Fetch benchmark historical prices (yfinance only)
   - Normalize politician returns to same period as benchmark
   - Support time ranges: `1D`, `5D`, `1M`, `6M`, `YTD`, `1Y`, `5Y`, `MAX`
   - **Leaderboard:** Return % over selected time range (not lifetime)
   - **Unit tests:** given portfolio + benchmark → expected comparison

3. Implement `src/services/trade_service.py`:
   - Fetch latest trades from Finnhub
   - Deduplicate against DB
   - Store new trades
   - **Unit tests:** deduplication logic

4. Implement `src/services/alert_service.py`:
   - Compare latest scrapes against DB
   - Detect new trades
   - Prepare alert payloads for Telegram (no sending yet)
   - **Unit tests:** new trade detection

**Deliverable:** Core logic working; can calculate P&L for any politician over any time range.

**Time estimate:** 2-3 days

---

## Phase 3: API Layer

**Goal:** Expose all business logic via FastAPI endpoints.

**Tasks:**
1. Implement `src/api/app.py` — FastAPI application factory

2. Implement `src/api/routes_politicians.py`:
   - `GET /api/politicians` — list all with trade counts
   - `GET /api/politicians/{id}/trades` — trade history
   - `GET /api/politicians/{id}/portfolio` — current portfolio + P&L

3. Implement `src/api/routes_portfolio.py`:
   - `GET /api/comparison` — compare vs benchmark (accepts `?ticker=^GSPC&range=1Y`)
   - `GET /api/leaderboard` — top politicians by return %

4. Implement `src/api/routes_subscriptions.py`:
   - `POST /api/subscriptions` — subscribe to politician alerts
   - `DELETE /api/subscriptions/{id}` — unsubscribe
   - `GET /api/subscriptions` — list active subscriptions

5. Implement `src/api/routes_misc.py`:
   - `GET /api/benchmarks` — list popular benchmark tickers for dropdown
   - `GET /health` — health check

6. **API tests:** FastAPI test client for all endpoints

7. Update `main.py`:
   - Start FastAPI app on port 8000
   - Serve static files

**Deliverable:** All API endpoints working; can test via `curl` or Postman.

**Time estimate:** 2 days

---

## Phase 4: Frontend Dashboard

**Goal:** Single-page dashboard with interactive charts and controls.

**Tasks:**
1. Implement `static/index.html`:
   - 5 main sections:
     1. Leaderboard (table, sortable by return %)
     2. Portfolio Comparison Chart (line chart: politicians vs benchmark)
     3. Trade Feed (recent trades across all politicians)
     4. Politician Detail (click to expand, holdings + P&L breakdown)
     5. Subscription Manager (subscribe/unsubscribe)
   - Time range pills: `1D · 5D · 1M · 6M · YTD · 1Y · 5Y · MAX`
   - Benchmark selector: dropdown + free-text input

2. Implement `static/css/style.css`:
   - Dark theme, glassmorphism cards
   - Green/red profit/loss highlighting
   - Responsive grid layout
   - Smooth hover effects

3. Implement `static/js/app.js`:
   - Load leaderboard on page load
   - Handle time range pill clicks → fetch new data
   - Handle benchmark dropdown/text input → fetch new comparison chart
   - Handle subscription button clicks

4. Implement `static/js/charts.js`:
   - Chart.js line chart (politician returns vs benchmark over time)
   - Bar chart (per-stock P&L)
   - Donut chart (portfolio allocation)

5. Implement `static/js/api.js`:
   - Fetch wrapper for all `/api/` endpoints

**Deliverable:** Fully interactive dashboard; no backend changes needed for UX tweaks.

**Time estimate:** 2-3 days

---

## Phase 5: Notifications & Scheduler

**Goal:** Send Telegram alerts; run periodic scraping.

**Tasks:**
1. Implement `src/telegram/bot.py`:
   - Async Telegram client using `python-telegram-bot`
   - One-way alert format (no bot commands)
   - Mock token support (no errors if token is invalid)
   - Alert payload: politician name, ticker, trade type, amount, date

2. Update `src/services/alert_service.py`:
   - Hook up Telegram bot
   - Send alerts after new trades detected

3. Implement `scheduler.py`:
   - APScheduler AsyncIOScheduler
   - Job 1: Scrape trades from Finnhub every 1 hour
   - Job 2: Update prices via yfinance every 30 minutes
   - Job 3: Send alerts after each scrape
   - Error handling: log errors, don't crash on API failures

4. Update `main.py`:
   - Start FastAPI + Scheduler concurrently

5. **Local testing:**
   - Subscribe to a politician
   - Wait for scraper to run
   - Verify alert format (mock token = no actual message sent)
   - Once user provides real token, real messages will work

**Deliverable:** Scheduler running locally; alerts queued (send to Telegram once real token provided).

**Time estimate:** 1-2 days

---

## Phase 6: Deployment & Docker

**Goal:** Package for Intel NUC; deploy in Docker.

**Tasks:**
1. Create `Dockerfile`:
   - Python 3.12 slim base
   - Copy app, install dependencies
   - Expose port 8000

2. Create `docker-compose.yml`:
   - Single service: `capitol-trade-follower`
   - Mount `./data` volume (SQLite persistence)
   - Load `.env` for secrets
   - Restart policy: `unless-stopped`

3. Create `.dockerignore`:
   - Exclude `.git`, `__pycache__`, `.env`, `data/*`

4. Test Docker build & run locally

5. Deploy to Intel NUC (copy docker-compose.yml + .env + run `docker-compose up -d`)

6. Verify:
   - Dashboard accessible at `http://nuc-ip:8000`
   - Scraper running (check logs)
   - Telegram alerts working (with real token)

**Deliverable:** App running in Docker on NUC; persistent data; automatic restarts.

**Time estimate:** 1 day

---

## Summary

| Phase | Goal | Days |
|-------|------|------|
| 1 | DB + Finnhub spike | 3-4 |
| 2 | Portfolio logic | 2-3 |
| 3 | API endpoints | 2 |
| 4 | Frontend dashboard | 2-3 |
| 5 | Telegram + scheduler | 1-2 |
| 6 | Docker + deploy | 1 |
| **Total** | **Fully working app** | **12-16 days** |

---

## Development Tips

- **Local testing:** Run `python main.py` in terminal; dashboard at `http://localhost:8000`
- **API testing:** Use `curl` or Postman; reference `src/api/routes_*.py` for endpoint specs
- **DB inspection:** Use `sqlite3 data/capitol_trades.db` to query tables directly
- **Scheduler logs:** Check console for scraper + alert errors
- **Docker:**
  - Build: `docker-compose build`
  - Run: `docker-compose up -d`
  - Logs: `docker-compose logs -f`
  - Stop: `docker-compose down`

---

## Decision Gates

Phase 1 → Phase 2: **Does Finnhub API work?**
- ✅ Yes → proceed
- ❌ No → implement Capitol Trades wrapper fallback first

Phase 2 → Phase 3: **Is portfolio calculation accurate?**
- ✅ Yes (unit tests pass) → proceed
- ❌ No → debug calculation logic

Phase 4 → Phase 5: **Is dashboard responsive?**
- ✅ Yes → proceed
- ❌ No (UI bugs) → fix before moving on

Phase 5 → Phase 6: **Do alerts work with mock token?**
- ✅ Yes (queue structure correct) → proceed
- ❌ No → debug alert logic

---

## Next Steps

1. Start Phase 1: Create `pyproject.toml` and project structure
2. Set up `.env` with API keys
3. Build `src/models/` and `src/db/`
4. **Decision gate:** Test Finnhub API
5. Report back with results before Phase 2
