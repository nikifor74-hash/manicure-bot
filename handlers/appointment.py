from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.db import get_session
from database.models import Appointment, User, Schedule
from states import AppointmentStates
from utils.scheduler import schedule_reminder, remove_reminder
from utils.helpers import is_admin
from config import ADMIN_IDS, TIMEZONE, REMINDER_HOURS
from datetime import datetime, date, time, timedelta
import logging
import pytz

router = Router()
logger = logging.getLogger(__name__)


async def get_working_slots(session, target_date: date):
    from sqlalchemy import select
    day_of_week = target_date.weekday()
    result = await session.execute(select(Schedule).where(Schedule.day_of_week == day_of_week))
    schedule = result.scalar_one_or_none()
    if not schedule or not schedule.is_working or schedule.start_time is None:
        return []
    slots = []
    start = datetime.combine(target_date, schedule.start_time)
    end = datetime.combine(target_date, schedule.end_time)
    current = start
    while current < end:
        slots.append(current.time())
        current += timedelta(minutes=30)

    booked = await session.execute(
        select(Appointment.time).where(
            Appointment.date == target_date,
            Appointment.status.in_(['scheduled', 'confirmed'])
        )
    )
    booked_times = [row[0] for row in booked]
    return [slot for slot in slots if slot not in booked_times]


@router.message(Command("book"))
@router.message(F.text == "📅 Записаться")
async def cmd_book(message: Message, state: FSMContext):
    await state.set_state(AppointmentStates.choosing_date)
    kb = InlineKeyboardBuilder()
    tz = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).date()
    for i in range(7):
        day = today + timedelta(days=i)
        day_str = day.strftime("%d.%m.%Y")
        kb.button(text=day_str, callback_data=f"date_{day.isoformat()}")
    kb.adjust(2)
    await message.answer("Выберите дату:", reply_markup=kb.as_markup())


@router.callback_query(StateFilter(AppointmentStates.choosing_date), F.data.startswith("date_"))
async def process_date(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split("_")[1]
    selected_date = date.fromisoformat(date_str)
    await state.update_data(selected_date=selected_date)
    await state.set_state(AppointmentStates.choosing_time)

    async with get_session() as session:
        slots = await get_working_slots(session, selected_date)
        if not slots:
            await callback.message.edit_text("На этот день нет свободных слотов. Попробуйте другую дату.")
            await state.clear()
            await callback.answer()
            return
        kb = InlineKeyboardBuilder()
        for slot in slots:
            slot_str = slot.strftime("%H:%M")
            kb.button(text=slot_str, callback_data=f"time_{slot_str}")
        kb.adjust(3)
        await callback.message.edit_text("Выберите время:", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(StateFilter(AppointmentStates.choosing_time), F.data.startswith("time_"))
async def process_time(callback: CallbackQuery, state: FSMContext):
    time_str = callback.data.split("_")[1]
    selected_time = datetime.strptime(time_str, "%H:%M").time()
    await state.update_data(selected_time=selected_time)
    await state.set_state(AppointmentStates.entering_name)
    await callback.message.edit_text("Введите ваше имя:")
    await callback.answer()


@router.message(StateFilter(AppointmentStates.entering_name))
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("Имя не может быть пустым. Введите имя:")
        return
    await state.update_data(client_name=name)
    await state.set_state(AppointmentStates.entering_phone)
    await message.answer("Введите ваш номер телефона для связи:")


@router.message(StateFilter(AppointmentStates.entering_phone))
async def process_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    data = await state.get_data()
    selected_date = data['selected_date']
    selected_time = data['selected_time']
    client_name = data['client_name']

    async with get_session() as session:
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(telegram_id=message.from_user.id, first_name=client_name)
            session.add(user)
            await session.commit()
            await session.refresh(user)

        # Проверяем, не занят ли слот
        existing = await session.execute(
            select(Appointment).where(
                Appointment.date == selected_date,
                Appointment.time == selected_time,
                Appointment.status.in_(['scheduled', 'confirmed'])
            )
        )
        if existing.scalar_one_or_none():
            await message.answer("К сожалению, это время только что заняли. Попробуйте выбрать другое.")
            await state.clear()
            return

        appointment = Appointment(
            user_id=user.id,
            date=selected_date,
            time=selected_time,
            comment=f"Имя: {client_name}, Телефон: {phone}",
            status='scheduled'
        )
        session.add(appointment)
        await session.commit()
        await session.refresh(appointment)

        tz = pytz.timezone(TIMEZONE)
        appointment_datetime = datetime.combine(selected_date, selected_time).replace(tzinfo=tz)
        schedule_reminder(appointment.id, user.telegram_id, appointment_datetime, message.bot)

        await message.answer(
            f"Запись подтверждена!\n"
            f"Дата: {selected_date.strftime('%d.%m.%Y')}\n"
            f"Время: {selected_time.strftime('%H:%M')}\n"
            f"Имя: {client_name}\n"
            f"Телефон: {phone}"
        )

        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_message(
                    admin_id,
                    f"Новая запись!\n{client_name}\n{phone}\n{selected_date} {selected_time}"
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")

    await state.clear()


@router.message(Command("my_appointments"))
@router.message(F.text == "📋 Мои записи")
async def my_appointments(message: Message):
    async with get_session() as session:
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("Вы еще не записывались.")
            return
        appointments = await session.execute(
            select(Appointment).where(Appointment.user_id == user.id).order_by(Appointment.date, Appointment.time)
        )
        apps = appointments.scalars().all()
        if not apps:
            await message.answer("У вас нет активных записей.")
            return

        text = "Ваши записи:\n"
        for app in apps:
            status_emoji = "✅" if app.status == 'completed' else "🕒" if app.status == 'scheduled' else "❌"
            text += f"{status_emoji} {app.date.strftime('%d.%m.%Y')} {app.time.strftime('%H:%M')} - {app.status}\n"

            if app.status == 'scheduled' and app.date >= datetime.now().date():
                kb = InlineKeyboardBuilder()
                kb.button(text="❌ Отменить", callback_data=f"cancel_app_{app.id}")
                await message.answer(text, reply_markup=kb.as_markup())
                text = ""  # чтобы не дублировать
        if text:
            await message.answer(text)


@router.callback_query(F.data.startswith("cancel_app_"))
async def cancel_appointment(callback: CallbackQuery):
    app_id = int(callback.data.split("_")[2])
    async with get_session() as session:
        appointment = await session.get(Appointment, app_id)
        if not appointment:
            await callback.answer("Запись не найдена.")
            return
        from sqlalchemy import select
        user = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = user.scalar_one_or_none()
        if not user or appointment.user_id != user.id:
            await callback.answer("Это не ваша запись.")
            return
        if appointment.status != 'scheduled':
            await callback.answer("Запись уже нельзя отменить.")
            return
        appointment.status = 'cancelled'
        await session.commit()
        remove_reminder(app_id)

        await callback.message.edit_text("Запись отменена.")
        for admin_id in ADMIN_IDS:
            try:
                await callback.bot.send_message(
                    admin_id,
                    f"Клиент отменил запись {appointment.date} {appointment.time}"
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
    await callback.answer()
