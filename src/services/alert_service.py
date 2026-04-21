import logging
from typing import List, Optional

from src.db.database import Database
from src.db.repositories import SubscriptionRepository, PoliticianRepository
from src.models.trade import Trade

logger = logging.getLogger(__name__)


def format_alert(trade: Trade, politician_name: Optional[str] = None) -> str:
    name = politician_name or trade.politician_name or "Unknown"
    party = f" ({trade.party})" if trade.party else ""
    action = "BUY" if trade.trade_type == "BUY" else "SELL"
    midpoint = trade.midpoint
    if midpoint >= 1_000_000:
        amount_str = f"${midpoint/1_000_000:.1f}M"
    elif midpoint >= 1_000:
        amount_str = f"${midpoint/1_000:.0f}K"
    else:
        amount_str = f"${midpoint:.0f}"

    range_str = f"${trade.amount_from/1000:.0f}K–${trade.amount_to/1000:.0f}K"

    return (
        f"🏛️ CAPITOL TRADE ALERT\n\n"
        f"👤 {name}{party}\n"
        f"📊 Action: {action}\n"
        f"🏢 {trade.ticker}"
        + (f" ({trade.asset_name})" if trade.asset_name else "") + "\n"
        f"💰 Amount: {range_str} (~{amount_str} estimated)\n"
        f"📅 Trade Date: {trade.trade_date}\n"
        f"📋 Disclosed: {trade.filing_date}\n"
    )


class AlertService:
    def __init__(self, db: Database, telegram_bot=None):
        self.db = db
        self.bot = telegram_bot
        self._sub_repo = SubscriptionRepository(db)
        self._pol_repo = PoliticianRepository(db)

    async def process_new_trades(self, new_trades: List[Trade]) -> int:
        """Send Telegram alerts for new trades to relevant subscribers. Returns alert count."""
        if not new_trades:
            return 0

        active_subs = await self._sub_repo.get_active()
        if not active_subs:
            return 0

        sub_map: dict[int, list[str]] = {}
        for sub in active_subs:
            sub_map.setdefault(sub.politician_id, []).append(sub.telegram_chat_id)

        alert_count = 0
        for trade in new_trades:
            chat_ids = sub_map.get(trade.politician_id, [])
            if not chat_ids:
                continue

            message = format_alert(trade)
            for chat_id in chat_ids:
                await self._send(chat_id, message)
                alert_count += 1

        return alert_count

    async def _send(self, chat_id: str, message: str) -> None:
        if self.bot is None:
            logger.info("MOCK ALERT → %s:\n%s", chat_id, message)
            return
        try:
            await self.bot.send_message(chat_id=chat_id, text=message)
        except Exception as exc:
            logger.error("Failed to send alert to %s: %s", chat_id, exc)
