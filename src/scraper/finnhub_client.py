import asyncio
import logging
from datetime import date, datetime
from typing import List, Optional

import requests

from src.models.trade import Trade

logger = logging.getLogger(__name__)

BASE_URL = "https://finnhub.io/api/v1"

_TRANSACTION_MAP = {
    "purchase": "BUY",
    "buy": "BUY",
    "sale": "SELL",
    "sell": "SELL",
    "sale (partial)": "SELL",
    "sale (full)": "SELL",
}


class FinnhubClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = BASE_URL
        self._session = requests.Session()
        self._session.headers["X-Finnhub-Token"] = api_key

    def parse_response(self, response: dict) -> List[Trade]:
        raw = response.get("data", [])
        trades: List[Trade] = []
        for item in raw:
            trade = self._parse_item(item)
            if trade is not None:
                trades.append(trade)
        return trades

    def _parse_item(self, item: dict) -> Optional[Trade]:
        try:
            tx_raw = item["transactionType"].lower().strip()
            trade_type = _TRANSACTION_MAP.get(tx_raw)
            if trade_type is None:
                logger.warning("Unknown transactionType %r — skipping", item.get("transactionType"))
                return None

            trade_date = datetime.strptime(item["transactionDate"], "%Y-%m-%d").date()
            filing_date = datetime.strptime(item["filingDate"], "%Y-%m-%d").date()

            return Trade(
                politician_id=0,
                politician_name=item["name"],
                ticker=item["symbol"],
                asset_name=item.get("assetName"),
                trade_type=trade_type,
                amount_from=float(item["amountFrom"]),
                amount_to=float(item["amountTo"]),
                trade_date=trade_date,
                filing_date=filing_date,
            )
        except (KeyError, ValueError) as exc:
            logger.warning("Skipping malformed Finnhub item %r: %s", item.get("symbol"), exc)
            return None

    async def fetch_trades(self, from_date: Optional[date] = None, to_date: Optional[date] = None) -> List[Trade]:
        params: dict = {}
        if from_date:
            params["from"] = from_date.isoformat()
        if to_date:
            params["to"] = to_date.isoformat()

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, lambda: self._get_congressional_trading(params))
        return self.parse_response(response)

    def _get_congressional_trading(self, params: dict) -> dict:
        url = f"{self.base_url}/congressional-trading"
        resp = self._session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
