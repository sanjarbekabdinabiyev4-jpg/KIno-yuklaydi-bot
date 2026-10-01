import aiosqlite
from config import DB_NAME


async def create_tables() -> None:
    """Barcha jadvallarni yaratadi."""
    async with aiosqlite.connect(DB_NAME) as db:
        # Kinolar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                kino_kodi      INTEGER UNIQUE NOT NULL,
                nomi           TEXT NOT NULL,
                janri          TEXT NOT NULL DEFAULT 'Janrsiz',
                tili           TEXT NOT NULL DEFAULT 'Uzbek',
                sifat          TEXT NOT NULL DEFAULT '720p',
                video_file_id  TEXT NOT NULL,
                qoshilgan_vaqt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Foydalanuvchilar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id             INTEGER PRIMARY KEY,
                user_id        INTEGER UNIQUE NOT NULL,
                full_name      TEXT,
                username       TEXT,
                qoshilgan_vaqt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()
