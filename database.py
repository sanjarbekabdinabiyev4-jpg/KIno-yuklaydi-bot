import os
import aiosqlite
from dotenv import load_dotenv

load_dotenv()

DB_NAME = os.getenv("DB_NAME", "movies.db")


# ─────────────────────── JADVALLARNI YARATISH ───────────────────────

async def create_tables() -> None:
    """Barcha jadvallarni (kinolar, foydalanuvchilar, seriallar, qismlar) yaratadi."""
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
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id        INTEGER UNIQUE NOT NULL,
                full_name      TEXT,
                username       TEXT,
                qoshilgan_vaqt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Seriallar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS series (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                code           INTEGER UNIQUE NOT NULL,
                title          TEXT NOT NULL,
                genre          TEXT NOT NULL DEFAULT 'Janrsiz',
                poster_file_id TEXT,
                qoshilgan_vaqt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Serial qismlari (episodes) jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS series_episodes (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                series_code    INTEGER NOT NULL,
                episode_num    INTEGER NOT NULL,
                file_id        TEXT NOT NULL,
                qoshilgan_vaqt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(series_code, episode_num)
            )
        """)

        await db.commit()

        # Mavjud bazalar uchun poster_file_id ustunini qo'shish (migratsiya)
        try:
            await db.execute("ALTER TABLE series ADD COLUMN poster_file_id TEXT")
            await db.commit()
        except Exception:
            pass


# ─────────────────────── SANOQ SON AMALIYOTLARI ───────────────────────

async def get_next_code() -> int:
    """Kino va seriallar bo'yicha keyingi bo'sh sanoq sonni (1, 2, 3...) qaytaradi."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT MAX(kino_kodi) FROM movies") as cursor:
            row_m = await cursor.fetchone()
            max_m = row_m[0] if (row_m and row_m[0]) else 0

        async with db.execute("SELECT MAX(code) FROM series") as cursor:
            row_s = await cursor.fetchone()
            max_s = row_s[0] if (row_s and row_s[0]) else 0

        return max(max_m, max_s) + 1


async def get_next_episode_num(series_code: int) -> int:
    """Serialning navbatdagi yetishmayotgan yoki keyingi qism raqamini qaytaradi."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT episode_num FROM series_episodes WHERE series_code = ? ORDER BY episode_num ASC",
            (series_code,),
        ) as cursor:
            rows = await cursor.fetchall()
            existing = {r[0] for r in rows}
            expected = 1
            while expected in existing:
                expected += 1
            return expected


# ─────────────────────── SERIALLAR AMALIYOTLARI ───────────────────────

async def add_series(code: int, title: str, genre: str = "Janrsiz", poster_file_id: str | None = None) -> bool:
    """Yangi serial yaratadi. Muvaffaqiyatli bo'lsa True, kod band bo'lsa False."""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT INTO series (code, title, genre, poster_file_id) VALUES (?, ?, ?, ?)",
                (code, title, genre, poster_file_id),
            )
            await db.commit()
        return True
    except aiosqlite.IntegrityError:
        return False


async def update_series_poster(code: int, poster_file_id: str) -> bool:
    """Serial rasmini (posterini) yangilaydi."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE series SET poster_file_id = ? WHERE code = ?",
            (poster_file_id, code),
        )
        await db.commit()
        return True


async def get_series_by_code(code: int) -> dict | None:
    """Serial kodi bo'yicha serial ma'lumotlarini qaytaradi."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM series WHERE code = ?", (code,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_all_series() -> list[dict]:
    """Barcha seriallar ro'yxatini qaytaradi."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM series ORDER BY code") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_series_count() -> int:
    """Seriallar sonini qaytaradi."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM series") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def delete_series(code: int) -> bool:
    """Serial va uning barcha qismlarini o'chiradi."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM series_episodes WHERE series_code = ?", (code,))
        cursor = await db.execute("DELETE FROM series WHERE code = ?", (code,))
        await db.commit()
        return cursor.rowcount > 0


# ─────────────────────── QISMLAR (EPISODES) AMALIYOTLARI ───────────────────────

async def add_episode(series_code: int, episode_num: int, file_id: str) -> tuple[bool, bool]:
    """Serialga yangi qism qo'shadi yoki mavjud qism videosini yangilaydi. Qaytaradi: (success, is_new)."""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute(
                "SELECT 1 FROM series_episodes WHERE series_code = ? AND episode_num = ?",
                (series_code, episode_num),
            ) as cursor:
                exists = await cursor.fetchone() is not None

            await db.execute(
                """
                INSERT INTO series_episodes (series_code, episode_num, file_id)
                VALUES (?, ?, ?)
                ON CONFLICT(series_code, episode_num) DO UPDATE SET
                    file_id = excluded.file_id
                """,
                (series_code, episode_num, file_id),
            )
            await db.commit()
        return True, not exists
    except Exception:
        return False, False


async def get_episodes(series_code: int) -> list[dict]:
    """Serialning barcha qismlarini tartiblangan holda qaytaradi."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT * FROM series_episodes 
            WHERE series_code = ? 
            ORDER BY episode_num ASC
            """,
            (series_code,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_episode_file_id(series_code: int, episode_num: int) -> str | None:
    """Muayyan qismning Telegram file_id sini qaytaradi."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            """
            SELECT file_id FROM series_episodes 
            WHERE series_code = ? AND episode_num = ?
            """,
            (series_code, episode_num),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def delete_episode(series_code: int, episode_num: int) -> bool:
    """Bitta qismni o'chiradi."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "DELETE FROM series_episodes WHERE series_code = ? AND episode_num = ?",
            (series_code, episode_num),
        )
        await db.commit()
        return cursor.rowcount > 0


async def clear_series_episodes(series_code: int) -> bool:
    """Serialning barcha qismlarini tozalaydi."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM series_episodes WHERE series_code = ?", (series_code,))
        await db.commit()
        return True


# ─────────────────────── KINO AMALIYOTLARI ───────────────────────

async def add_movie(
    kino_kodi: int,
    nomi: str,
    janri: str,
    tili: str,
    sifat: str,
    video_file_id: str,
) -> bool:
    """Yangi kino qo'shadi."""
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


async def get_movie_by_code(kino_kodi: int) -> dict | None:
    """Kod bo'yicha kino ma'lumotlarini qaytaradi."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM movies WHERE kino_kodi = ?", (kino_kodi,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def search_movies_by_name(query: str) -> list[dict]:
    """Nom bo'yicha qidiruv (kinolar va seriallar bo'yicha)."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM movies WHERE nomi LIKE ? ORDER BY kino_kodi LIMIT 15",
            (f"%{query}%",),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_all_movies() -> list[dict]:
    """Barcha kinolar ro'yxati."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM movies ORDER BY kino_kodi") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


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


# ─────────────────────── FOYDALANUVCHILAR ───────────────────────

async def add_or_update_user(user_id: int, full_name: str, username: str | None) -> None:
    """Foydalanuvchini bazaga qo'shadi yoki yangilaydi."""
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
    """Foydalanuvchilar soni."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_all_user_ids() -> list[int]:
    """Barcha foydalanuvchi ID lari."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]
