from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from database.db import get_session
from database.models import User
from keyboards.reply_kb import main_menu_kb
from utils.helpers import is_admin
from config import ADMIN_IDS
import logging

router = Router()
logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def cmd_start(message: Message):
    async with get_session() as session:
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )
            session.add(user)
            await session.commit()
            logger.info(f"New user registered: {message.from_user.id}")

    await message.answer(
        f"Добро пожаловать, {message.from_user.first_name}!\n"
        "Я помогу вам записаться на маникюр, показать портфолио и многое другое.",
        reply_markup=main_menu_kb()
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Список команд:\n"
        "/start - Начало\n"
        "/portfolio - Портфолио\n"
        "/price - Прайс\n"
        "/tips - Советы\n"
        "/contacts - Контакты\n"
        "/book - Запись\n"
        "/my_appointments - Мои записи"
    )


@router.message(F.text)
async def forward_to_admin(message: Message):
    if is_admin(message.from_user.id):
        return
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f"Сообщение от {message.from_user.full_name} (id: {message.from_user.id}):\n{message.text}"
            )
        except Exception as e:
            logger.error(f"Failed to forward message to admin {admin_id}: {e}")
    await message.answer("Ваше сообщение передано мастеру. Ожидайте ответа (он свяжется с вами в личные сообщения).")
