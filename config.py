import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# API Keys
FINNHUB_API_KEY: str | None = os.getenv("FINNHUB_API_KEY")
FMP_API_KEY: str | None = os.getenv("FMP_API_KEY")
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "MOCK_TOKEN_REPLACE_ME")
TELEGRAM_CHAT_ID: str | None = os.getenv("TELEGRAM_CHAT_ID")

# App Config
DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
PORT: int = int(os.getenv("PORT", "8000"))
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/capitol_trades.db")
RISK_FREE_RATE: float = float(os.getenv("RISK_FREE_RATE", "0.04"))

# Derived: strip the SQLite URI prefix and resolve to an absolute path.
DB_PATH: str = str(Path(DATABASE_URL.removeprefix("sqlite:///")).resolve())
