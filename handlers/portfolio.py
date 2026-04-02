from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InputFile
from database.db import get_session
from database.models import Category, PortfolioImage
from keyboards.inline_kb import categories_kb, portfolio_pagination_kb
from utils.cache import CacheKeys, cached_set, cached_get
import os
from config import MEDIA_DIR
import logging

router = Router()
logger = logging.getLogger(__name__)

ITEMS_PER_PAGE = 5  # Количество элементов на странице


@router.message(Command("portfolio"))
@router.message(F.text == "🖼 Портфолио")
async def portfolio_categories(message: Message):
    async with get_session() as session:
        from sqlalchemy import select
        
        # Проверяем кэш категорий
        categories_data = await cached_get(CacheKeys.CATEGORIES_PREFIX)
        
        if categories_data is None:
            result = await session.execute(select(Category))
            categories = result.scalars().all()
            if not categories:
                await message.answer("Портфолио пока пусто.")
                return
            # Кэшируем категории
            categories_data = [{'id': cat.id, 'name': cat.name} for cat in categories]
            await cached_set(CacheKeys.CATEGORIES_PREFIX, categories_data, ttl=3600)
        else:
            # Восстанавливаем объекты из кэша
            categories = [type('Category', (), item) for item in categories_data]
        
        kb = InlineKeyboardBuilder()
        for cat in categories:
            kb.button(text=cat.name, callback_data=f"category_{cat.id}")
        kb.adjust(2)
        await message.answer("Выберите категорию:", reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("category_"))
async def show_category(callback: CallbackQuery):
    category_id = int(callback.data.split("_")[1])
    
    async with get_session() as session:
        from sqlalchemy import select, func
        
        # Получаем общее количество изображений
        count_result = await session.execute(
            select(func.count()).select_from(PortfolioImage).where(PortfolioImage.category_id == category_id)
        )
        total_count = count_result.scalar()
        
        if total_count == 0:
            await callback.answer("В этой категории пока нет фото.")
            return
        
        # Получаем первую страницу
        result = await session.execute(
            select(PortfolioImage)
            .where(PortfolioImage.category_id == category_id)
            .order_by(PortfolioImage.created_at.desc())
            .limit(ITEMS_PER_PAGE)
        )
        images = result.scalars().all()
        
        await send_portfolio_image(callback.message, images, 0, total_count, category_id)
    await callback.answer()


async def send_portfolio_image(message: Message, images: list, index: int, total_count: int, category_id: int):
    if not images or index >= len(images):
        await message.answer("Изображение не найдено.")
        return
    
    image = images[index]
    file_path = os.path.join(MEDIA_DIR, image.file_path)
    caption = f"{image.caption}\nЦена: {image.price}" if image.price else image.caption
    
    if os.path.exists(file_path):
        photo = InputFile(file_path)
        await message.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=portfolio_pagination_kb(index, len(images), category_id, total_count)
        )
    else:
        await message.answer(f"Файл {image.file_path} не найден.")


@router.callback_query(F.data.startswith("nav_"))
async def paginate_portfolio(callback: CallbackQuery):
    data = callback.data.split("_")
    action = data[1]
    index = int(data[2])
    category_id = int(data[3])
    
    async with get_session() as session:
        from sqlalchemy import select
        
        # Получаем все изображения категории (для простоты, в production лучше использовать offset/limit)
        result = await session.execute(
            select(PortfolioImage)
            .where(PortfolioImage.category_id == category_id)
            .order_by(PortfolioImage.created_at.desc())
        )
        all_images = result.scalars().all()
        
        if action == "prev":
            index = (index - 1) % len(all_images)
        elif action == "next":
            index = (index + 1) % len(all_images)
        
        # Определяем текущую страницу
        page_index = index // ITEMS_PER_PAGE
        start_idx = page_index * ITEMS_PER_PAGE
        end_idx = min(start_idx + ITEMS_PER_PAGE, len(all_images))
        page_images = all_images[start_idx:end_idx]
        relative_index = index % ITEMS_PER_PAGE
        
        await callback.message.delete()
        await send_portfolio_image(callback.message, page_images, relative_index, len(all_images), category_id)
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()
