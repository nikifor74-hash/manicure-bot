import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set in .env")

admin_ids_str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = []
if admin_ids_str:
    for part in admin_ids_str.split(','):
        part = part.strip()
        if part.isdigit():
            ADMIN_IDS.append(int(part))
        else:
            print(f"⚠️ Warning: invalid admin ID '{part}' ignored")

MEDIA_DIR = os.getenv("MEDIA_DIR", "media")
DB_PATH = os.getenv("DB_PATH", "sqlite:///data/bot.db")
REMINDER_HOURS = int(os.getenv("REMINDER_HOURS", 3))
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
