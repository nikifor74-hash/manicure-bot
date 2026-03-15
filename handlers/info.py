from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from database.db import get_session
from database.models import Price
import logging

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("price"))
@router.message(F.text == "💰 Прайс")
async def show_price(message: Message):
    async with get_session() as session:
        from sqlalchemy import select
        result = await session.execute(select(Price))
        prices = result.scalars().all()
        if not prices:
            await message.answer("Прайс-лист пока не заполнен.")
            return
        text = "💰 Прайс-лист:\n\n"
        for p in prices:
            text += f"• {p.service_name}: {p.price}\n"
            if p.description:
                text += f"  {p.description}\n"
        await message.answer(text)


@router.message(Command("tips"))
@router.message(F.text == "💡 Советы")
async def show_tips(message: Message):
    tips_text = (
        "💡 Советы по уходу за ногтями:\n"
        "1. Ежедневно используйте масло для кутикулы.\n"
        "2. Избегайте использования ногтей как инструментов.\n"
        "3. Увлажняйте руки кремом после каждого мытья.\n"
        "4. Делайте перерывы между покрытиями, чтобы ногти дышали."
    )
    await message.answer(tips_text)


@router.message(Command("contacts"))
@router.message(F.text == "📞 Контакты")
async def show_contacts(message: Message):
    contact_text = (
        "📞 Наши контакты:\n"
        "Адрес: ул. Примерная, д. 1\n"
        "Телефон: +7 (123) 456-78-90\n"
        "Instagram: @example\n"
        "Часы работы: Пн-Пт 10:00-20:00, Сб 11:00-18:00, Вс выходной"
    )
    await message.answer(contact_text)
