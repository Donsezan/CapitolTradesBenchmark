from typing import Optional
from pydantic import BaseModel


class TelegramSubscription(BaseModel):
    id: Optional[int] = None
    politician_id: int
    telegram_chat_id: str
    active: bool = True
