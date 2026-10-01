from typing import Optional
import aiosqlite
from config import DB_NAME
from database.schemas import Movie, User


# ─────────────────────── KINO AMALIYOTLARI ───────────────────────

async def add_movie(
    kino_kodi: int,
    nomi: str,
    janri: str,
    tili: str,
    sifat: str,
    video_file_id: str,
) -> bool:
    """Yangi kino qo'shadi. Muvaffaqiyatli bo'lsa True qaytaradi."""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                """
                INSERT INTO movies (kino_kodi, nomi, janri, tili, sifat, video_file_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (kino_kodi, nomi, janri, tili, sifat, video_file_id),
            )
            await db.commit()
        return True
    except aiosqlite.IntegrityError:
        return False


async def get_movie_by_code(kino_kodi: int) -> Optional[Movie]:
    """Kod bo'yicha kino topadi."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM movies WHERE kino_kodi = ?", (kino_kodi,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Movie(**dict(row))
    return None


async def search_movies_by_name(query: str) -> list[Movie]:
    """Nom bo'yicha kinolarni qidiradi (qisman moslik)."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM movies WHERE nomi LIKE ? ORDER BY kino_kodi LIMIT 20",
            (f"%{query}%",),
        ) as cursor:
            rows = await cursor.fetchall()
            return [Movie(**dict(r)) for r in rows]


async def get_all_movies() -> list[Movie]:
    """Barcha kinolar ro'yxatini qaytaradi."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM movies ORDER BY kino_kodi") as cursor:
            rows = await cursor.fetchall()
            return [Movie(**dict(r)) for r in rows]


async def delete_movie(kino_kodi: int) -> bool:
    """Kino kodiga ko'ra kinoni o'chiradi."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "DELETE FROM movies WHERE kino_kodi = ?", (kino_kodi,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_movies_count() -> int:
    """Kinolar sonini qaytaradi."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM movies") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


# ─────────────────────── FOYDALANUVCHI AMALIYOTLARI ───────────────────────

async def add_or_update_user(user_id: int, full_name: str, username: Optional[str]) -> None:
    """Foydalanuvchini qo'shadi yoki yangilaydi."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, full_name, username)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                full_name = excluded.full_name,
                username  = excluded.username
            """,
            (user_id, full_name, username),
        )
        await db.commit()


async def get_users_count() -> int:
    """Foydalanuvchilar sonini qaytaradi."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_all_user_ids() -> list[int]:
    """Barcha foydalanuvchi ID'larini qaytaradi (xabar yuborish uchun)."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]
