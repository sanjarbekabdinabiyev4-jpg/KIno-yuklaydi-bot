import os
import logging
from typing import Any
import aiosqlite
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL", "").strip()
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "").strip()

# libsql:// protokolini https:// ga o'tkazish (HTTP ulanish barqaror bo'lishi uchun)
if TURSO_DATABASE_URL.startswith("libsql://"):
    TURSO_DATABASE_URL = "https://" + TURSO_DATABASE_URL[len("libsql://"):]

USE_TURSO = bool(TURSO_DATABASE_URL and TURSO_AUTH_TOKEN)

_default_db = os.path.join("/data", "movies.db") if os.path.isdir("/data") else "movies.db"
DB_NAME = os.getenv("DB_NAME", _default_db)

# ─────────────────────── TURSO CLIENT SOZLAMALARI ───────────────────────

_turso_client = None

async def get_turso_client():
    global _turso_client
    if _turso_client is None:
        import libsql_client
        _turso_client = libsql_client.create_client(
            url=TURSO_DATABASE_URL,
            auth_token=TURSO_AUTH_TOKEN,
        )
    return _turso_client


async def close() -> None:
    """Turso client sessiyasini tozalab yopadi."""
    global _turso_client
    if _turso_client:
        try:
            await _turso_client.close()
        except Exception:
            pass
        _turso_client = None


# ─────────────────────── UNIFIED QUERY RUNNER ───────────────────────

async def execute(sql: str, params: tuple | list = ()) -> Any:
    """SQL buyrug'ini bajaradi (INSERT, UPDATE, DELETE)."""
    if USE_TURSO:
        client = await get_turso_client()
        return await client.execute(sql, list(params))
    else:
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute(sql, params)
            await db.commit()
            return cursor


async def fetchone(sql: str, params: tuple | list = ()) -> dict | None:
    """Bitta qatorni dict ko'rinishida qaytaradi."""
    if USE_TURSO:
        client = await get_turso_client()
        rs = await client.execute(sql, list(params))
        if rs.rows:
            return dict(zip(rs.columns, rs.rows[0]))
        return None
    else:
        async with aiosqlite.connect(DB_NAME) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None


async def fetchall(sql: str, params: tuple | list = ()) -> list[dict]:
    """Barcha qatorlarni dict lar ro'yxati ko'rinishida qaytaradi."""
    if USE_TURSO:
        client = await get_turso_client()
        rs = await client.execute(sql, list(params))
        return [dict(zip(rs.columns, r)) for r in rs.rows]
    else:
        async with aiosqlite.connect(DB_NAME) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]


async def fetchval(sql: str, params: tuple | list = ()) -> Any:
    """Bitta qiymatni qaytaradi (masalan, COUNT yoki MAX)."""
    if USE_TURSO:
        client = await get_turso_client()
        rs = await client.execute(sql, list(params))
        if rs.rows and len(rs.rows[0]) > 0:
            return rs.rows[0][0]
        return None
    else:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute(sql, params) as cursor:
                row = await cursor.fetchone()
                return row[0] if (row and len(row) > 0) else None


# ─────────────────────── JADVALLARNI YARATISH ───────────────────────

async def create_tables() -> None:
    """Barcha jadvallarni (kinolar, foydalanuvchilar, seriallar, qismlar) yaratadi."""
    if USE_TURSO:
        logger.info("Turso Cloud Database ishlatilmoqda ☁️")
    else:
        logger.info(f"Lokal SQLite database ishlatilmoqda ({DB_NAME}) 📁")

    statements = [
        """
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
        """,
        """
        CREATE TABLE IF NOT EXISTS users (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER UNIQUE NOT NULL,
            full_name      TEXT,
            username       TEXT,
            qoshilgan_vaqt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS series (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            code           INTEGER UNIQUE NOT NULL,
            title          TEXT NOT NULL,
            genre          TEXT NOT NULL DEFAULT 'Janrsiz',
            poster_file_id TEXT,
            qoshilgan_vaqt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS series_episodes (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            series_code    INTEGER NOT NULL,
            episode_num    INTEGER NOT NULL,
            file_id        TEXT NOT NULL,
            qoshilgan_vaqt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(series_code, episode_num)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS channels (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id     TEXT UNIQUE NOT NULL,
            channel_name   TEXT NOT NULL,
            channel_url    TEXT NOT NULL,
            qoshilgan_vaqt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    ]

    for stmt in statements:
        await execute(stmt)

    # Boshlang'ich majburiy kanalni kiritish
    try:
        c_count = await fetchval("SELECT COUNT(*) FROM channels")
        if not c_count:
            await execute(
                "INSERT INTO channels (channel_id, channel_name, channel_url) VALUES (?, ?, ?)",
                ("@cinemaworldbysanjar", "Cinema World", "https://t.me/cinemaworldbysanjar"),
            )
    except Exception:
        pass

    # Migratsiya: mavjud bazalar uchun poster_file_id ustunini tekshirish
    try:
        await execute("ALTER TABLE series ADD COLUMN poster_file_id TEXT")
    except Exception:
        pass


# ─────────────────────── SANOQ SON AMALIYOTLARI ───────────────────────

async def get_next_code() -> int:
    """Kino va seriallar bo'yicha keyingi bo'sh sanoq sonni (1, 2, 3...) qaytaradi."""
    max_m = await fetchval("SELECT MAX(kino_kodi) FROM movies") or 0
    max_s = await fetchval("SELECT MAX(code) FROM series") or 0
    return max(int(max_m), int(max_s)) + 1


async def get_next_episode_num(series_code: int) -> int:
    """Serialning navbatdagi yetishmayotgan yoki keyingi qism raqamini qaytaradi."""
    rows = await fetchall(
        "SELECT episode_num FROM series_episodes WHERE series_code = ? ORDER BY episode_num ASC",
        (series_code,),
    )
    existing = {r["episode_num"] for r in rows}
    expected = 1
    while expected in existing:
        expected += 1
    return expected


# ─────────────────────── SERIALLAR AMALIYOTLARI ───────────────────────

async def add_series(code: int, title: str, genre: str = "Janrsiz", poster_file_id: str | None = None) -> bool:
    """Yangi serial yaratadi. Muvaffaqiyatli bo'lsa True, kod band bo'lsa False."""
    try:
        await execute(
            "INSERT INTO series (code, title, genre, poster_file_id) VALUES (?, ?, ?, ?)",
            (code, title, genre, poster_file_id),
        )
        return True
    except Exception as e:
        logger.warning(f"add_series xatolik: {e}")
        return False


async def update_series_poster(code: int, poster_file_id: str) -> bool:
    """Serial rasmini (posterini) yangilaydi."""
    try:
        await execute(
            "UPDATE series SET poster_file_id = ? WHERE code = ?",
            (poster_file_id, code),
        )
        return True
    except Exception as e:
        logger.warning(f"update_series_poster xatolik: {e}")
        return False


async def get_series_by_code(code: int) -> dict | None:
    """Serial kodi bo'yicha serial ma'lumotlarini qaytaradi."""
    return await fetchone("SELECT * FROM series WHERE code = ?", (code,))


async def get_all_series() -> list[dict]:
    """Barcha seriallar ro'yxatini qaytaradi."""
    return await fetchall("SELECT * FROM series ORDER BY code")


async def get_series_count() -> int:
    """Seriallar sonini qaytaradi."""
    val = await fetchval("SELECT COUNT(*) FROM series")
    return int(val or 0)


async def delete_series(code: int) -> bool:
    """Serial va uning barcha qismlarini o'chiradi."""
    try:
        await execute("DELETE FROM series_episodes WHERE series_code = ?", (code,))
        await execute("DELETE FROM series WHERE code = ?", (code,))
        return True
    except Exception as e:
        logger.warning(f"delete_series xatolik: {e}")
        return False


# ─────────────────────── QISMLAR (EPISODES) AMALIYOTLARI ───────────────────────

async def add_episode(series_code: int, episode_num: int, file_id: str) -> tuple[bool, bool]:
    """Serialga yangi qism qo'shadi yoki mavjud qism videosini yangilaydi. Qaytaradi: (success, is_new)."""
    try:
        existing = await fetchone(
            "SELECT 1 FROM series_episodes WHERE series_code = ? AND episode_num = ?",
            (series_code, episode_num),
        )
        is_new = existing is None

        await execute(
            """
            INSERT INTO series_episodes (series_code, episode_num, file_id)
            VALUES (?, ?, ?)
            ON CONFLICT(series_code, episode_num) DO UPDATE SET
                file_id = excluded.file_id
            """,
            (series_code, episode_num, file_id),
        )
        return True, is_new
    except Exception as e:
        logger.error(f"add_episode xatolik: {e}")
        return False, False


async def get_episodes(series_code: int) -> list[dict]:
    """Serialning barcha qismlarini tartiblangan holda qaytaradi."""
    return await fetchall(
        "SELECT * FROM series_episodes WHERE series_code = ? ORDER BY episode_num ASC",
        (series_code,),
    )


async def get_episode_file_id(series_code: int, episode_num: int) -> str | None:
    """Muayyan qismning Telegram file_id sini qaytaradi."""
    val = await fetchval(
        "SELECT file_id FROM series_episodes WHERE series_code = ? AND episode_num = ?",
        (series_code, episode_num),
    )
    return str(val) if val else None


async def delete_episode(series_code: int, episode_num: int) -> bool:
    """Bitta qismni o'chiradi."""
    try:
        await execute(
            "DELETE FROM series_episodes WHERE series_code = ? AND episode_num = ?",
            (series_code, episode_num),
        )
        return True
    except Exception as e:
        logger.warning(f"delete_episode xatolik: {e}")
        return False


async def clear_series_episodes(series_code: int) -> bool:
    """Serialning barcha qismlarini tozalaydi."""
    try:
        await execute("DELETE FROM series_episodes WHERE series_code = ?", (series_code,))
        return True
    except Exception as e:
        logger.warning(f"clear_series_episodes xatolik: {e}")
        return False


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
        await execute(
            """
            INSERT INTO movies (kino_kodi, nomi, janri, tili, sifat, video_file_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (kino_kodi, nomi, janri, tili, sifat, video_file_id),
        )
        return True
    except Exception as e:
        logger.warning(f"add_movie xatolik: {e}")
        return False


async def get_movie_by_code(kino_kodi: int) -> dict | None:
    """Kod bo'yicha kino ma'lumotlarini qaytaradi."""
    return await fetchone("SELECT * FROM movies WHERE kino_kodi = ?", (kino_kodi,))


async def search_movies_by_name(query: str) -> list[dict]:
    """Nom bo'yicha qidiruv (kinolar bo'yicha)."""
    return await fetchall(
        "SELECT * FROM movies WHERE nomi LIKE ? ORDER BY kino_kodi LIMIT 15",
        (f"%{query}%",),
    )


async def get_all_movies() -> list[dict]:
    """Barcha kinolar ro'yxati."""
    return await fetchall("SELECT * FROM movies ORDER BY kino_kodi")


async def get_all_cartoons() -> dict:
    """Barcha multfilmlarni (kinolar va seriallar/animelar) qaytaradi."""
    movies = await fetchall(
        "SELECT * FROM movies WHERE LOWER(janri) LIKE '%mult%' OR LOWER(janri) LIKE '%anim%' ORDER BY kino_kodi DESC"
    )
    series = await fetchall(
        "SELECT * FROM series WHERE LOWER(genre) LIKE '%mult%' OR LOWER(genre) LIKE '%anim%' ORDER BY code DESC"
    )
    return {"movies": movies, "series": series}


async def delete_movie(kino_kodi: int) -> bool:
    """Kino kodiga ko'ra kinoni o'chiradi."""
    try:
        await execute("DELETE FROM movies WHERE kino_kodi = ?", (kino_kodi,))
        return True
    except Exception as e:
        logger.warning(f"delete_movie xatolik: {e}")
        return False


async def get_movies_count() -> int:
    """Kinolar sonini qaytaradi."""
    val = await fetchval("SELECT COUNT(*) FROM movies")
    return int(val or 0)


# ─────────────────────── FOYDALANUVCHILAR ───────────────────────

async def add_or_update_user(user_id: int, full_name: str, username: str | None) -> None:
    """Foydalanuvchini bazaga qo'shadi yoki yangilaydi."""
    try:
        await execute(
            """
            INSERT INTO users (user_id, full_name, username)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                full_name = excluded.full_name,
                username  = excluded.username
            """,
            (user_id, full_name, username),
        )
    except Exception as e:
        logger.warning(f"add_or_update_user xatolik: {e}")


async def get_users_count() -> int:
    """Foydalanuvchilar soni."""
    val = await fetchval("SELECT COUNT(*) FROM users")
    return int(val or 0)


async def get_all_user_ids() -> list[int]:
    """Barcha foydalanuvchi ID lari."""
    rows = await fetchall("SELECT user_id FROM users")
    return [r["user_id"] for r in rows]


# ─────────────────────── KANALLAR (MAJBURIY OBUNA) ───────────────────────

async def add_channel(channel_id: str, channel_name: str, channel_url: str) -> bool:
    """Yangi kanal qo'shadi yoki yangilaydi."""
    try:
        await execute(
            """
            INSERT INTO channels (channel_id, channel_name, channel_url)
            VALUES (?, ?, ?)
            ON CONFLICT(channel_id) DO UPDATE SET
                channel_name = excluded.channel_name,
                channel_url  = excluded.channel_url
            """,
            (channel_id, channel_name, channel_url),
        )
        return True
    except Exception as e:
        logger.warning(f"add_channel xatolik: {e}")
        return False


async def get_all_channels() -> list[dict]:
    """Barcha majburiy obuna kanallarini qaytaradi."""
    return await fetchall("SELECT * FROM channels ORDER BY id ASC")


async def delete_channel(channel_id: str) -> bool:
    """Kanalni ro'yxatdan o'chiradi."""
    try:
        await execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
        return True
    except Exception as e:
        logger.warning(f"delete_channel xatolik: {e}")
        return False
