from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta
import logging
from config import REMINDER_HOURS, TIMEZONE
import pytz
from database.db import get_session
from database.models import Appointment

logger = logging.getLogger(__name__)

# Создаем scheduler с настройками для асинхронной работы
scheduler = AsyncIOScheduler(
    timezone=TIMEZONE,
    job_defaults={
        'coalesce': True,  # Объединять пропущенные запуски
        'max_instances': 3,  # Максимум 3 одновременных выполнения
        'misfire_grace_time': 60  # Допустимое время опоздания (сек)
    }
)


async def send_reminder(bot, user_id, appointment_id, appointment_datetime):
    try:
        text = (f"Напоминаем, что у вас запись на "
                f"{appointment_datetime.strftime('%d.%m.%Y %H:%M')}. Ждем вас!")
        await bot.send_message(chat_id=user_id, text=text)

        async with get_session() as session:
            appointment = await session.get(Appointment, appointment_id)
            if appointment:
                appointment.reminder_sent = True
                await session.commit()
        logger.info(f"Reminder sent for appointment {appointment_id} to user {user_id}")
    except Exception as e:
        logger.error(f"Failed to send reminder: {e}")


def schedule_reminder(appointment_id, user_id, appointment_datetime: datetime, bot):
    remind_time = appointment_datetime - timedelta(hours=REMINDER_HOURS)
    if remind_time > datetime.now(pytz.timezone(TIMEZONE)):
        scheduler.add_job(
            send_reminder,
            trigger=DateTrigger(run_date=remind_time),
            args=[bot, user_id, appointment_id, appointment_datetime],
            id=f"reminder_{appointment_id}",
            replace_existing=True,
            misfire_grace_time=60
        )
        logger.info(f"Scheduled reminder for appointment {appointment_id} at {remind_time}")


def remove_reminder(appointment_id):
    try:
        scheduler.remove_job(f"reminder_{appointment_id}")
        logger.debug(f"Removed reminder for appointment {appointment_id}")
    except Exception as e:
        logger.warning(f"Failed to remove reminder {appointment_id}: {e}")


async def start_scheduler():
    """Запуск планировщика задач."""
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


async def stop_scheduler():
    """Остановка планировщика задач."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
