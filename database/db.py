import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import StaticPool
from config import DB_PATH
import logging

logger = logging.getLogger(__name__)

_engine: AsyncEngine = None
_async_session_maker = None


def get_engine():
    """Ленивое создание движка с проверкой существования директории для SQLite и connection pooling."""
    global _engine
    if _engine is None:
        db_url = DB_PATH

        if db_url.startswith("sqlite:///"):
            db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
            file_path = db_url.replace("sqlite+aiosqlite:///", "", 1)
            dir_name = os.path.dirname(file_path)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)
        elif db_url.startswith("sqlite://"):
            db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://", 1)

        # Для SQLite используем StaticPool для улучшения производительности при конкурентном доступе
        # Для production с PostgreSQL/MySQL следует использовать QueuePool с pool_size и max_overflow
        _engine = create_async_engine(
            db_url,
            echo=False,
            poolclass=StaticPool,  # Улучшает производительность для SQLite
            connect_args={"check_same_thread": False}  # Разрешаем использование в разных потоках
        )
        logger.info(f"Database engine created for {db_url}")
    return _engine


def get_session_maker():
    """Ленивое создание фабрики сессий."""
    global _async_session_maker
    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _async_session_maker


async def init_db():
    """Инициализация базы данных: создание таблиц и начальных категорий."""
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from database.models import Category
    from sqlalchemy import select

    async with get_session_maker()() as session:
        result = await session.execute(select(Category))
        if result.first() is None:
            default_cats = ["Маникюр", "Педикюр", "Дизайн", "Наращивание"]
            for cat_name in default_cats:
                session.add(Category(name=cat_name))
            await session.commit()


def get_session() -> AsyncSession:
    """Получить новую сессию для работы с БД (синхронно возвращает объект сессии)."""
    return get_session_maker()()


Base = declarative_base()
