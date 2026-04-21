from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.api.routes_politicians import router as politicians_router
from src.api.routes_portfolio import router as portfolio_router
from src.api.routes_subscriptions import router as subscriptions_router
from src.api.routes_misc import router as misc_router


def create_app(db=None, scheduler=None) -> FastAPI:
    app = FastAPI(title="Capitol Trade Follower", version="0.1.0")

    app.state.db = db
    app.state.scheduler = scheduler

    app.include_router(politicians_router, prefix="/api")
    app.include_router(portfolio_router, prefix="/api")
    app.include_router(subscriptions_router, prefix="/api")
    app.include_router(misc_router)

    static_dir = Path(__file__).parent.parent.parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/", include_in_schema=False)
        async def root():
            return FileResponse(str(static_dir / "index.html"))

    return app
