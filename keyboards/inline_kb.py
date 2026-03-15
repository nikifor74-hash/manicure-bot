from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def categories_kb(categories):
    buttons = []
    for cat in categories:
        buttons.append([InlineKeyboardButton(text=cat.name, callback_data=f"category_{cat.id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def portfolio_pagination_kb(current_index, total, category_id):
    buttons = []
    if total > 1:
        nav_buttons = [
            InlineKeyboardButton(text="◀", callback_data=f"nav_prev_{current_index}_{category_id}"),
            InlineKeyboardButton(text=f"{current_index + 1}/{total}", callback_data="noop"),
            InlineKeyboardButton(text="▶", callback_data=f"nav_next_{current_index}_{category_id}")
        ]
        buttons.append(nav_buttons)
    return InlineKeyboardMarkup(inline_keyboard=buttons)
