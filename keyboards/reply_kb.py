from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_menu_kb():
    kb = [
        [KeyboardButton(text="📅 Записаться"), KeyboardButton(text="🖼 Портфолио")],
        [KeyboardButton(text="💰 Прайс"), KeyboardButton(text="💡 Советы")],
        [KeyboardButton(text="📞 Контакты"), KeyboardButton(text="📋 Мои записи")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def admin_menu_kb():
    kb = [
        [KeyboardButton(text="➕ Добавить фото"), KeyboardButton(text="❌ Удалить фото")],
        [KeyboardButton(text="✏ Редактировать прайс"), KeyboardButton(text="📅 Просмотр записей")],
        [KeyboardButton(text="⏰ Установить расписание"), KeyboardButton(text="📢 Рассылка")],
        [KeyboardButton(text="🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
