from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from src.db.repositories import SubscriptionRepository
from src.models.subscription import TelegramSubscription

router = APIRouter()


class SubscriptionCreate(BaseModel):
    politician_id: int
    telegram_chat_id: str


@router.post("/subscriptions", status_code=201)
async def create_subscription(body: SubscriptionCreate, request: Request):
    db = request.app.state.db
    repo = SubscriptionRepository(db)
    sub = TelegramSubscription(
        politician_id=body.politician_id,
        telegram_chat_id=body.telegram_chat_id,
        active=True,
    )
    created = await repo.create(sub)
    return created.model_dump()


@router.get("/subscriptions")
async def list_subscriptions(request: Request):
    db = request.app.state.db
    repo = SubscriptionRepository(db)
    subs = await repo.get_all()
    return [s.model_dump() for s in subs]


@router.delete("/subscriptions/{sub_id}", status_code=204)
async def delete_subscription(sub_id: int, request: Request):
    db = request.app.state.db
    repo = SubscriptionRepository(db)
    existing = await repo.get_by_id(sub_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    await repo.delete(sub_id)
