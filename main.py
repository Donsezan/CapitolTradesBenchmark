import asyncio
import logging

import uvicorn

import config
from src.db.database import Database
from src.api.app import create_app
from src.telegram.bot import TelegramBot
from scheduler import Scheduler

logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    db = Database(config.DB_PATH)
    await db.init_schema()
    logger.info("Database initialised at %s", config.DB_PATH)

    bot = TelegramBot(token=config.TELEGRAM_BOT_TOKEN)
    await bot.start()

    scheduler = Scheduler(db=db, bot=bot)
    scheduler.start()

    app = create_app(db=db, scheduler=scheduler)

    server_config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=config.PORT,
        log_level="debug" if config.DEBUG else "info",
    )
    server = uvicorn.Server(server_config)

    try:
        await server.serve()
    finally:
        scheduler.stop()
        await bot.stop()
        await db.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
