from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.db import get_session
from database.models import User, Appointment, Category, PortfolioImage, Price, Schedule
from states import AddPhoto, EditPrice, SetSchedule, Broadcast
from utils.helpers import is_admin
from config import MEDIA_DIR
import os
import logging
from datetime import datetime, time

router = Router()
logger = logging.getLogger(__name__)


def admin_filter(message: Message) -> bool:
    return is_admin(message.from_user.id)


@router.message(Command("admin"), admin_filter)
async def cmd_admin(message: Message):
    from keyboards.reply_kb import admin_menu_kb
    await message.answer("Админ-панель", reply_markup=admin_menu_kb())


# ================== Добавление фото ==================
@router.message(F.text == "➕ Добавить фото", admin_filter)
async def add_photo_start(message: Message, state: FSMContext):
    async with get_session() as session:
        from sqlalchemy import select
        result = await session.execute(select(Category))
        categories = result.scalars().all()
        if not categories:
            await message.answer("Сначала создайте категории через /add_category")
            return
        kb = InlineKeyboardBuilder()
        for cat in categories:
            kb.button(text=cat.name, callback_data=f"addphoto_cat_{cat.id}")
        await message.answer("Выберите категорию:", reply_markup=kb.as_markup())
    await state.set_state(AddPhoto.choosing_category)


@router.callback_query(StateFilter(AddPhoto.choosing_category), F.data.startswith("addphoto_cat_"))
async def add_photo_category(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split("_")[2])
    await state.update_data(category_id=cat_id)
    await state.set_state(AddPhoto.uploading_photo)
    await callback.message.edit_text("Отправьте фото (как файл или изображение).")
    await callback.answer()


@router.message(StateFilter(AddPhoto.uploading_photo), F.photo | F.document, admin_filter)
async def add_photo_upload(message: Message, state: FSMContext):
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document and message.document.mime_type.startswith('image/'):
        file_id = message.document.file_id
    else:
        await message.answer("Пожалуйста, отправьте изображение.")
        return

    file = await message.bot.get_file(file_id)
    ext = file.file_path.split('.')[-1]
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{message.from_user.id}.{ext}"
    file_path = os.path.join(MEDIA_DIR, filename)
    await message.bot.download_file(file.file_path, destination=file_path)

    await state.update_data(file_path=filename)
    await state.set_state(AddPhoto.entering_caption)
    await message.answer("Фото сохранено. Введите описание:")


@router.message(StateFilter(AddPhoto.entering_caption), admin_filter)
async def add_photo_caption(message: Message, state: FSMContext):
    caption = message.text.strip()
    await state.update_data(caption=caption)
    await state.set_state(AddPhoto.entering_price)
    await message.answer("Введите цену (или отправьте '-' если не нужно):")


@router.message(StateFilter(AddPhoto.entering_price), admin_filter)
async def add_photo_price(message: Message, state: FSMContext):
    price = message.text.strip()
    if price == '-':
        price = None
    data = await state.get_data()
    async with get_session() as session:
        image = PortfolioImage(
            category_id=data['category_id'],
            file_path=data['file_path'],
            caption=data['caption'],
            price=price
        )
        session.add(image)
        await session.commit()
    await message.answer("Фото добавлено в портфолио!")
    await state.clear()


# ================== Удаление фото ==================
@router.message(F.text == "❌ Удалить фото", admin_filter)
async def del_photo_start(message: Message):
    async with get_session() as session:
        from sqlalchemy import select
        images = await session.execute(select(PortfolioImage).order_by(PortfolioImage.id))
        images = images.scalars().all()
        if not images:
            await message.answer("Нет фото для удаления.")
            return
        for img in images:
            kb = InlineKeyboardBuilder()
            kb.button(text="❌ Удалить", callback_data=f"delphoto_{img.id}")
            await message.answer(
                f"ID: {img.id}\n{img.caption}\nЦена: {img.price}",
                reply_markup=kb.as_markup()
            )


@router.callback_query(F.data.startswith("delphoto_"))
async def del_photo_confirm(callback: CallbackQuery):
    img_id = int(callback.data.split("_")[1])
    async with get_session() as session:
        img = await session.get(PortfolioImage, img_id)
        if img:
            file_path = os.path.join(MEDIA_DIR, img.file_path)
            if os.path.exists(file_path):
                os.remove(file_path)
            await session.delete(img)
            await session.commit()
            await callback.message.edit_text("Фото удалено.")
        else:
            await callback.answer("Фото не найдено.")
    await callback.answer()


# ================== Редактирование прайса ==================
@router.message(F.text == "✏ Редактировать прайс", admin_filter)
async def edit_price_start(message: Message, state: FSMContext):
    await state.set_state(EditPrice.choosing_action)
    kb = InlineKeyboardBuilder()
    kb.button(text="Добавить услугу", callback_data="price_add")
    kb.button(text="Удалить услугу", callback_data="price_del")
    kb.button(text="Изменить цену", callback_data="price_edit")
    await message.answer("Выберите действие:", reply_markup=kb.as_markup())


@router.callback_query(StateFilter(EditPrice.choosing_action), F.data.startswith("price_"))
async def edit_price_action(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split("_")[1]
    await state.update_data(action=action)
    if action == "add":
        await state.set_state(EditPrice.entering_service)
        await callback.message.edit_text("Введите название услуги:")
    elif action == "del":
        async with get_session() as session:
            from sqlalchemy import select
            prices = await session.execute(select(Price))
            prices = prices.scalars().all()
            if not prices:
                await callback.message.edit_text("Прайс пуст.")
                await state.clear()
                return
            kb = InlineKeyboardBuilder()
            for p in prices:
                kb.button(text=p.service_name, callback_data=f"delprice_{p.id}")
            await callback.message.edit_text("Выберите услугу для удаления:", reply_markup=kb.as_markup())
    elif action == "edit":
        async with get_session() as session:
            from sqlalchemy import select
            prices = await session.execute(select(Price))
            prices = prices.scalars().all()
            if not prices:
                await callback.message.edit_text("Прайс пуст.")
                await state.clear()
                return
            kb = InlineKeyboardBuilder()
            for p in prices:
                kb.button(text=p.service_name, callback_data=f"editprice_{p.id}")
            await callback.message.edit_text("Выберите услугу для изменения:", reply_markup=kb.as_markup())
            await state.set_state(EditPrice.entering_price)
    await callback.answer()


@router.message(StateFilter(EditPrice.entering_service), admin_filter)
async def add_price_service(message: Message, state: FSMContext):
    service = message.text.strip()
    await state.update_data(service=service)
    await state.set_state(EditPrice.entering_price)
    await message.answer("Введите цену:")


@router.message(StateFilter(EditPrice.entering_price), admin_filter)
async def add_price_price(message: Message, state: FSMContext):
    price = message.text.strip()
    await state.update_data(price=price)
    await state.set_state(EditPrice.entering_description)
    await message.answer("Введите описание (или '-'):")


@router.message(StateFilter(EditPrice.entering_description), admin_filter)
async def add_price_description(message: Message, state: FSMContext):
    desc = message.text.strip()
    if desc == '-':
        desc = None
    data = await state.get_data()
    if data['action'] == 'add':
        async with get_session() as session:
            price_item = Price(
                service_name=data['service'],
                price=data['price'],
                description=desc
            )
            session.add(price_item)
            await session.commit()
        await message.answer("Услуга добавлена в прайс.")
    await state.clear()


@router.callback_query(F.data.startswith("delprice_"))
async def del_price_callback(callback: CallbackQuery, state: FSMContext):
    price_id = int(callback.data.split("_")[1])
    async with get_session() as session:
        price = await session.get(Price, price_id)
        if price:
            await session.delete(price)
            await session.commit()
            await callback.message.edit_text("Услуга удалена.")
        else:
            await callback.answer("Услуга не найдена.")
    await callback.answer()
    await state.clear()


@router.callback_query(F.data.startswith("editprice_"))
async def edit_price_select(callback: CallbackQuery, state: FSMContext):
    price_id = int(callback.data.split("_")[1])
    await state.update_data(price_id=price_id)
    await state.set_state(EditPrice.entering_price)
    await callback.message.edit_text("Введите новую цену:")


@router.message(StateFilter(EditPrice.entering_price), admin_filter)
async def edit_price_update(message: Message, state: FSMContext):
    new_price = message.text.strip()
    data = await state.get_data()
    price_id = data.get('price_id')
    if price_id:
        async with get_session() as session:
            price = await session.get(Price, price_id)
            if price:
                price.price = new_price
                await session.commit()
                await message.answer("Цена обновлена.")
            else:
                await message.answer("Услуга не найдена.")
    await state.clear()


# ================== Просмотр записей (админ) ==================
@router.message(F.text == "📅 Просмотр записей", admin_filter)
async def view_appointments(message: Message):
    async with get_session() as session:
        from sqlalchemy import select
        appointments = await session.execute(
            select(Appointment).order_by(Appointment.date, Appointment.time)
        )
        apps = appointments.scalars().all()
        if not apps:
            await message.answer("Записей нет.")
            return
        for app in apps:
            user = await session.get(User, app.user_id)
            username = user.username or f"{user.first_name} {user.last_name}" if user else "Unknown"
            text = f"{app.date} {app.time} - {username}\nСтатус: {app.status}\nКоммент: {app.comment}"
            kb = InlineKeyboardBuilder()
            if app.status == 'scheduled':
                kb.button(text="✅ Выполнено", callback_data=f"app_complete_{app.id}")
                kb.button(text="❌ Отменить", callback_data=f"app_cancel_{app.id}")
            elif app.status == 'completed':
                kb.button(text="🔄 Вернуть в ожидание", callback_data=f"app_restore_{app.id}")
            await message.answer(text, reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("app_complete_"))
async def complete_appointment(callback: CallbackQuery):
    app_id = int(callback.data.split("_")[2])
    async with get_session() as session:
        app = await session.get(Appointment, app_id)
        if app:
            app.status = 'completed'
            await session.commit()
            await callback.message.edit_text(callback.message.text + "\n(Статус обновлен: выполнено)")
        else:
            await callback.answer("Запись не найдена.")
    await callback.answer()


@router.callback_query(F.data.startswith("app_cancel_"))
async def cancel_appointment_admin(callback: CallbackQuery):
    app_id = int(callback.data.split("_")[2])
    async with get_session() as session:
        app = await session.get(Appointment, app_id)
        if app:
            app.status = 'cancelled'
            await session.commit()
            from utils.scheduler import remove_reminder
            remove_reminder(app_id)
            await callback.message.edit_text(callback.message.text + "\n(Статус обновлен: отменено)")
            user = await session.get(User, app.user_id)
            if user:
                try:
                    await callback.bot.send_message(
                        user.telegram_id,
                        f"Ваша запись на {app.date} {app.time} была отменена администратором."
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user {user.telegram_id}: {e}")
        else:
            await callback.answer("Запись не найдена.")
    await callback.answer()


@router.callback_query(F.data.startswith("app_restore_"))
async def restore_appointment(callback: CallbackQuery):
    app_id = int(callback.data.split("_")[2])
    async with get_session() as session:
        app = await session.get(Appointment, app_id)
        if app:
            app.status = 'scheduled'
            await session.commit()
            await callback.message.edit_text(callback.message.text + "\n(Статус обновлен: ожидание)")
        else:
            await callback.answer("Запись не найдена.")
    await callback.answer()


# ================== Установка расписания ==================
@router.message(F.text == "⏰ Установить расписание", admin_filter)
async def set_schedule_start(message: Message, state: FSMContext):
    await state.set_state(SetSchedule.choosing_day)
    kb = InlineKeyboardBuilder()
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    for i, day in enumerate(days):
        kb.button(text=day, callback_data=f"sched_day_{i}")
    kb.adjust(3)
    await message.answer("Выберите день недели:", reply_markup=kb.as_markup())


@router.callback_query(StateFilter(SetSchedule.choosing_day), F.data.startswith("sched_day_"))
async def schedule_day(callback: CallbackQuery, state: FSMContext):
    day = int(callback.data.split("_")[2])
    await state.update_data(day=day)
    await state.set_state(SetSchedule.entering_start)
    await callback.message.edit_text("Введите время начала работы (например, 10:00) или '-' если выходной:")
    await callback.answer()


@router.message(StateFilter(SetSchedule.entering_start), admin_filter)
async def schedule_start(message: Message, state: FSMContext):
    start_str = message.text.strip()
    if start_str == '-':
        await state.update_data(start=None, end=None)
        await state.set_state(SetSchedule.confirming)
        await message.answer("Этот день будет выходным. Подтвердить? (да/нет)")
        return
    try:
        start_time = datetime.strptime(start_str, "%H:%M").time()
    except ValueError:
        await message.answer("Неверный формат. Используйте ЧЧ:ММ или '-'")
        return
    await state.update_data(start=start_time)
    await state.set_state(SetSchedule.entering_end)
    await message.answer("Введите время окончания работы (например, 20:00):")


@router.message(StateFilter(SetSchedule.entering_end), admin_filter)
async def schedule_end(message: Message, state: FSMContext):
    end_str = message.text.strip()
    try:
        end_time = datetime.strptime(end_str, "%H:%M").time()
    except ValueError:
        await message.answer("Неверный формат. Используйте ЧЧ:ММ")
        return
    data = await state.get_data()
    start = data['start']
    if end_time <= start:
        await message.answer("Время окончания должно быть позже времени начала.")
        return
    await state.update_data(end=end_time)
    await state.set_state(SetSchedule.confirming)
    day_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    day_name = day_names[data['day']]
    await message.answer(
        f"Подтвердите: {day_name} с {start.strftime('%H:%M')} до {end_time.strftime('%H:%M')} (да/нет)"
    )


@router.message(StateFilter(SetSchedule.confirming), admin_filter)
async def schedule_confirm(message: Message, state: FSMContext):
    answer = message.text.strip().lower()
    if answer in ['да', 'yes']:
        data = await state.get_data()
        async with get_session() as session:
            from sqlalchemy import select
            result = await session.execute(select(Schedule).where(Schedule.day_of_week == data['day']))
            sched = result.scalar_one_or_none()
            if not sched:
                sched = Schedule(day_of_week=data['day'])
            sched.start_time = data.get('start')
            sched.end_time = data.get('end')
            sched.is_working = data.get('start') is not None
            session.add(sched)
            await session.commit()
        await message.answer("Расписание обновлено.")
    else:
        await message.answer("Отменено.")
    await state.clear()


# ================== Рассылка ==================
@router.message(F.text == "📢 Рассылка", admin_filter)
async def broadcast_start(message: Message, state: FSMContext):
    await state.set_state(Broadcast.entering_message)
    await message.answer("Введите текст сообщения для рассылки:")


@router.message(StateFilter(Broadcast.entering_message), admin_filter)
async def broadcast_message(message: Message, state: FSMContext):
    text = message.text.strip()
    await state.update_data(text=text)
    await state.set_state(Broadcast.confirming)
    await message.answer(f"Текст сообщения:\n\n{text}\n\nОтправить всем пользователям? (да/нет)")


@router.message(StateFilter(Broadcast.confirming), admin_filter)
async def broadcast_confirm(message: Message, state: FSMContext):
    answer = message.text.strip().lower()
    if answer in ['да', 'yes']:
        data = await state.get_data()
        text = data['text']
        async with get_session() as session:
            from sqlalchemy import select
            users = await session.execute(select(User.telegram_id))
            user_ids = [row[0] for row in users]
        success = 0
        fail = 0
        for uid in user_ids:
            try:
                await message.bot.send_message(uid, text)
                success += 1
            except Exception as e:
                fail += 1
                logger.error(f"Failed to send to {uid}: {e}")
        await message.answer(f"Рассылка завершена. Успешно: {success}, ошибок: {fail}")
    else:
        await message.answer("Рассылка отменена.")
    await state.clear()


# ================== Добавление категории (простейшее) ==================
@router.message(Command("add_category"), admin_filter)
async def add_category(message: Message):
    # Упрощённо: просим ввести название и сохраняем
    await message.answer("Введите название новой категории:")
    # Здесь можно сделать FSM, но для экономии места оставим как есть
    # Рекомендуется реализовать полноценный диалог
