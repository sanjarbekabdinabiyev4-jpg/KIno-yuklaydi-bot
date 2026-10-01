import os
from dotenv import load_dotenv

load_dotenv()

# Bot Token
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# Admin ro'yxati
_admin_ids_raw: str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = [
    int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip().isdigit()
]

# Ma'lumotlar bazasi
DB_NAME: str = os.getenv("DB_NAME", "movies.db")

# Bot nomi
BOT_NAME: str = os.getenv("BOT_NAME", "🎬 Kino Bot")

# Majburiy kanal (ixtiyoriy)
CHANNEL_ID: str | None = os.getenv("CHANNEL_ID")


def validate_config() -> None:
    """Konfiguratsiya to'g'riligini tekshiradi."""
    if not BOT_TOKEN:
        raise ValueError("❌ BOT_TOKEN .env faylida topilmadi!")
    if not ADMIN_IDS:
        raise ValueError("❌ ADMIN_IDS .env faylida topilmadi!")
