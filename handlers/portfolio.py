from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InputFile
from database.db import get_session
from database.models import Category, PortfolioImage
from keyboards.inline_kb import categories_kb, portfolio_pagination_kb
import os
from config import MEDIA_DIR
import logging

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("portfolio"))
@router.message(F.text == "🖼 Портфолио")
async def portfolio_categories(message: Message):
    async with get_session() as session:
        from sqlalchemy import select
        result = await session.execute(select(Category))
        categories = result.scalars().all()
        if not categories:
            await message.answer("Портфолио пока пусто.")
            return
        await message.answer("Выберите категорию:", reply_markup=categories_kb(categories))


@router.callback_query(F.data.startswith("category_"))
async def show_category(callback: CallbackQuery):
    category_id = int(callback.data.split("_")[1])
    async with get_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(PortfolioImage).where(PortfolioImage.category_id == category_id)
        )
        images = result.scalars().all()
        if not images:
            await callback.answer("В этой категории пока нет фото.")
            return
        await send_portfolio_image(callback.message, images, 0)
    await callback.answer()


async def send_portfolio_image(message: Message, images: list, index: int):
    image = images[index]
    file_path = os.path.join(MEDIA_DIR, image.file_path)
    caption = f"{image.caption}\nЦена: {image.price}" if image.price else image.caption
    if os.path.exists(file_path):
        photo = InputFile(file_path)
        await message.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=portfolio_pagination_kb(index, len(images), image.category_id)
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
        result = await session.execute(
            select(PortfolioImage).where(PortfolioImage.category_id == category_id)
        )
        images = result.scalars().all()
        if action == "prev":
            index = (index - 1) % len(images)
        elif action == "next":
            index = (index + 1) % len(images)
        await callback.message.delete()
        await send_portfolio_image(callback.message.chat, images, index)
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()
