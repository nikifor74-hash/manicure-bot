import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from database.db import init_db
from utils.scheduler import start_scheduler, stop_scheduler
from utils.cache import init_cache
from handlers import common, appointment, portfolio, info, admin
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    await init_db()
    os.makedirs("media", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    
    # Инициализация кэша
    await init_cache(max_size=1000, default_ttl=300)
    
    # Запуск асинхронного планировщика
    await start_scheduler()
    
    logger.info("Bot started with optimizations")


async def on_shutdown(bot: Bot):
    await stop_scheduler()
    logger.info("Bot stopped")


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Сначала специализированные роутеры
    dp.include_router(appointment.router)  # запись
    dp.include_router(portfolio.router)  # портфолио
    dp.include_router(info.router)  # прайс, советы, контакты
    dp.include_router(admin.router)  # админ-панель
    # Общий роутер (обработка /start и пересылка остальных сообщений) — в самом конце
    dp.include_router(common.router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())
