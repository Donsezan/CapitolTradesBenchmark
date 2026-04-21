import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self._app = None
        self._is_mock = token in ("MOCK_TOKEN_REPLACE_ME", "", None)

    async def start(self) -> None:
        if self._is_mock:
            logger.info("TelegramBot running in mock mode — messages will be logged only")
            return
        try:
            from telegram import Bot
            self._app = Bot(token=self.token)
            await self._app.initialize()
            logger.info("TelegramBot initialized")
        except Exception as exc:
            logger.error("Failed to initialize Telegram bot: %s — falling back to mock mode", exc)
            self._is_mock = True

    async def send_message(self, chat_id: str, text: str) -> None:
        if self._is_mock:
            logger.info("[MOCK TELEGRAM] → %s\n%s", chat_id, text)
            return
        try:
            await self._app.send_message(chat_id=chat_id, text=text)
        except Exception as exc:
            logger.error("send_message to %s failed: %s", chat_id, exc)

    async def stop(self) -> None:
        if self._app is not None:
            try:
                await self._app.shutdown()
            except Exception:
                pass
