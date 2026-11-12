"""Точка входа: запуск Telegram-бота «Склад»."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import Config, load_config
from database import Database
from handlers import setup_routers
from middlewares import AccessMiddleware

BOT_COMMANDS = [
    BotCommand(command="start", description="Главное меню"),
    BotCommand(command="list", description="Остатки на складе"),
    BotCommand(command="find", description="Найти товар: /find <запрос>"),
    BotCommand(command="history", description="История операций"),
    BotCommand(command="cancel", description="Отменить текущее действие"),
]


def build_dispatcher(db: Database, config: Config) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    # Доступны в хендлерах как аргументы db и config.
    dp["db"] = db
    dp["config"] = config

    access = AccessMiddleware(config.allowed_users)
    dp.message.outer_middleware(access)
    dp.callback_query.outer_middleware(access)

    dp.include_router(setup_routers())
    return dp


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = load_config()

    db = Database(config.db_path)
    await db.connect()
    logging.info("База данных: %s", config.db_path)

    bot = Bot(token=config.bot_token)
    dp = build_dispatcher(db, config)
    try:
        await bot.set_my_commands(BOT_COMMANDS)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        await db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
