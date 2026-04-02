"""
Модуль кэширования для оптимизации производительности.
Использует in-memory кэш с TTL для хранения часто используемых данных.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Any, Optional, Dict
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)


class MemoryCache:
    """In-memory кэш с поддержкой TTL и ограничением размера."""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl  # секунд
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Получить значение из кэша."""
        async with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            if entry['expires_at'] < datetime.now():
                del self._cache[key]
                return None
            
            # Перемещаем в конец (LRU)
            self._cache.move_to_end(key)
            return entry['value']
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Установить значение в кэш."""
        async with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                if len(self._cache) >= self._max_size:
                    # Удаляем самый старый элемент
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]
                    logger.debug(f"Cache full, removed oldest key: {oldest_key}")
            
            expires_at = datetime.now() + timedelta(seconds=ttl or self._default_ttl)
            self._cache[key] = {
                'value': value,
                'expires_at': expires_at
            }
    
    async def delete(self, key: str) -> bool:
        """Удалить значение из кэша."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    async def clear(self) -> None:
        """Очистить весь кэш."""
        async with self._lock:
            self._cache.clear()
    
    async def cleanup_expired(self) -> int:
        """Удалить просроченные записи. Возвращает количество удалённых."""
        async with self._lock:
            now = datetime.now()
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry['expires_at'] < now
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)


# Глобальный экземпляр кэша
_cache: Optional[MemoryCache] = None


def get_cache(max_size: int = 1000, default_ttl: int = 300) -> MemoryCache:
    """Получить глобальный экземпляр кэша."""
    global _cache
    if _cache is None:
        _cache = MemoryCache(max_size=max_size, default_ttl=default_ttl)
    return _cache


async def init_cache(max_size: int = 1000, default_ttl: int = 300) -> MemoryCache:
    """Инициализировать кэш и запустить задачу очистки."""
    cache = get_cache(max_size, default_ttl)
    
    # Запускаем фоновую задачу для периодической очистки
    asyncio.create_task(_cleanup_loop(cache))
    logger.info(f"Cache initialized with max_size={max_size}, default_ttl={default_ttl}s")
    return cache


async def _cleanup_loop(cache: MemoryCache) -> None:
    """Периодическая очистка просроченных записей."""
    while True:
        await asyncio.sleep(60)  # Каждую минуту
        try:
            removed = await cache.cleanup_expired()
            if removed > 0:
                logger.debug(f"Cache cleanup: removed {removed} expired entries")
        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")


# Утилитные функции для работы с кэшем
async def cached_get(key: str) -> Optional[Any]:
    """Получить значение из кэша."""
    return await get_cache().get(key)


async def cached_set(key: str, value: Any, ttl: Optional[int] = None) -> None:
    """Установить значение в кэш."""
    await get_cache().set(key, value, ttl)


async def cached_delete(key: str) -> bool:
    """Удалить значение из кэша."""
    return await get_cache().delete(key)


# Ключи для кэширования
class CacheKeys:
    """Константы ключей кэша."""
    SCHEDULE_PREFIX = "schedule:"
    USER_PREFIX = "user:"
    APPOINTMENTS_PREFIX = "appointments:"
    CATEGORIES_PREFIX = "categories"
    PRICES_PREFIX = "prices"
    PORTFOLIO_PREFIX = "portfolio:"
    
    @staticmethod
    def schedule(day_of_week: int) -> str:
        return f"{CacheKeys.SCHEDULE_PREFIX}{day_of_week}"
    
    @staticmethod
    def user(telegram_id: int) -> str:
        return f"{CacheKeys.USER_PREFIX}{telegram_id}"
    
    @staticmethod
    def user_by_id(user_id: int) -> str:
        return f"{CacheKeys.USER_PREFIX}id:{user_id}"
    
    @staticmethod
    def appointments(user_id: int) -> str:
        return f"{CacheKeys.APPOINTMENTS_PREFIX}{user_id}"
    
    @staticmethod
    def portfolio_category(category_id: int) -> str:
        return f"{CacheKeys.PORTFOLIO_PREFIX}cat:{category_id}"
