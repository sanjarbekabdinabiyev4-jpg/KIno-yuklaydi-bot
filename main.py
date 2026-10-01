import os
import sys
import logging
import asyncio
from aiohttp import web

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command, Filter, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# database.py dan barcha amaliyotlarni import qilish
import database as db

# ─────────────────────── SOZLAMALAR ───────────────────────

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
_admin_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in _admin_raw.split(",") if x.strip().isdigit()]
BOT_NAME = os.getenv("BOT_NAME", "Kino & Serial Bot")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN .env faylida ko'rsatilmagan!")

# Logging sozlamalari
_log_handlers = [logging.StreamHandler(stream=sys.stdout)]
try:
    _log_handlers.append(logging.FileHandler("bot.log", encoding="utf-8"))
except Exception:
    pass  # Render yoki read-only filesystem da fayl yaratib bo'lmasa o'tkazib yuboriladi

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=_log_handlers,
)
logger = logging.getLogger(__name__)

import re


def extract_episode_number(caption: str | None, filename: str | None = None) -> int | None:
    """Telegram kanalidan forward qilingan videoning izohidan (caption) yoki fayl nomidan qism raqamini aniqlaydi."""
    for text in (caption or "", filename or ""):
        if not text:
            continue

        # 1. 1-qism, 01-qism, 1 - qism, 1_qism, 1-seriya, 1-серия, 1-қисм, 1-bölüm
        m = re.search(r'(\d+)\s*[-_.]?\s*(?:qism|qismi|seriya|seriyasi|seriy|ep|episode|серия|серии|серияси|қисм|қисми|кисм|кисми|bölüm|bolum)', text, re.IGNORECASE)
        if m:
            val = int(m.group(1))
            if val > 0:
                return val

        # 2. Qism 1, Seriya: 5, Серия 1, Ep. 06, Episode 5
        m = re.search(r'(?:qism|qismi|seriya|seriyasi|seriy|ep|episode|серия|серии|серияси|қисм|қисми|кисм|кисми|bölüm|bolum)[\s.:#№\-_]*(\d+)', text, re.IGNORECASE)
        if m:
            val = int(m.group(1))
            if val > 0:
                return val

        # 3. S01E08 or E08 / e8
        m = re.search(r'(?:[sS]\d+)?\s*[eE](\d+)', text)
        if m:
            val = int(m.group(1))
            if val > 0:
                return val

        # 4. #25, №05, [01], (12)
        m = re.search(r'(?:[#№]|\[|\()(\d{1,3})(?:\]|\))?', text)
        if m:
            val = int(m.group(1))
            if val > 0:
                return val

        # 5. Fayl nomidagi raqam (masalan: Serial_01.mp4 yoki 01.mp4)
        m = re.search(r'(?:^|[_\-\s])(\d{1,3})(?:\.mp4|\.mkv|\.avi|$)', text, re.IGNORECASE)
        if m:
            val = int(m.group(1))
            if val > 0:
                return val

    return None


bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


# ─────────────────────── FSM HOLATLARI ───────────────────────

class AddMovieStates(StatesGroup):
    waiting_video = State()
    waiting_nomi  = State()
    waiting_janri = State()
    waiting_tili  = State()
    waiting_sifat = State()
    confirm       = State()


class AddSeriesStates(StatesGroup):
    waiting_title  = State()   # Serial nomi
    waiting_genre  = State()   # Serial janri
    waiting_poster = State()   # Serial posteri/rasmi


class SetPosterStates(StatesGroup):
    waiting_series_code = State()  # Qaysi serialga rasm qo'yiladi
    waiting_photo       = State()  # Yuborilgan rasm


class AddEpisodeStates(StatesGroup):
    waiting_series_code = State()  # Qaysi serial kodi
    waiting_video       = State()  # Qismlar videosi (ketma-ket yoki birdaniga)


class SearchStates(StatesGroup):
    waiting_query = State()


# ─────────────────────── ADMIN FILTRI ───────────────────────

class IsAdmin(Filter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id if event.from_user else 0
        return user_id in ADMIN_IDS


# ─────────────────────── KLAVIATURALAR ───────────────────────

def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔍 Nom bo'yicha qidirish", callback_data="search_by_name"),
        InlineKeyboardButton(text="🔢 Kod bo'yicha qidirish", callback_data="search_by_code"),
    )
    builder.row(
        InlineKeyboardButton(text="🎬 Barcha kinolar",   callback_data="all_movies"),
        InlineKeyboardButton(text="📺 Barcha seriallar", callback_data="all_series"),
    )
    if is_admin:
        builder.row(
            InlineKeyboardButton(text="⚙️ Admin Panel", callback_data="admin_panel"),
        )
    return builder.as_markup()


def admin_panel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Kino qo'shish", callback_data="admin_add_movie"),
        InlineKeyboardButton(text="📺 Yangi serial yaratish", callback_data="admin_create_series"),
    )
    builder.row(
        InlineKeyboardButton(text="➕ Serialga qism qo'shish", callback_data="admin_add_episode"),
        InlineKeyboardButton(text="🖼️ Serialga rasm qo'yish", callback_data="admin_set_poster"),
    )
    builder.row(
        InlineKeyboardButton(text="🗑️ Qismlarni tozalash", callback_data="admin_clear_episodes"),
        InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu"),
    )
    return builder.as_markup()


def back_to_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu"))
    return builder.as_markup()


def back_to_admin_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚙️ Admin Panel", callback_data="admin_panel"),
        InlineKeyboardButton(text="🏠 Bosh menyu",   callback_data="main_menu"),
    )
    return builder.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Saqlash", callback_data="confirm_save"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_action"),
    )
    return builder.as_markup()


def episodes_paginated_kb(
    series_code: int,
    episodes: list[dict],
    page: int = 0,
    per_page: int = 10,
) -> InlineKeyboardMarkup:
    """Serialning qismlarini 10 tadan sahifalab chiqaruvchi klaviatura."""
    builder = InlineKeyboardBuilder()
    total_episodes = len(episodes)
    total_pages = max(1, (total_episodes + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))

    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_episodes = episodes[start_idx:end_idx]

    # 10 ta qism tugmasi (qatoriga 2 tadan)
    for ep in page_episodes:
        num = ep["episode_num"]
        builder.button(
            text=f"▶️ {num}-qism",
            callback_data=f"ep_{series_code}_{num}",
        )
    builder.adjust(2)

    # 10 ta 10 ta sahifalash navigatsiyasi
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"eppage_{series_code}_{page - 1}")
        )
    if total_pages > 1:
        nav_buttons.append(
            InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop")
        )
    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"eppage_{series_code}_{page + 1}")
        )
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu"))
    return builder.as_markup()


# ─────────────────────── FOYDALANUVCHI: /start, /myid, MENYU ───────────────────────

@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = message.from_user
    await db.add_or_update_user(user.id, user.full_name, user.username)
    is_admin = user.id in ADMIN_IDS

    await message.answer(
        f"👋 Assalomu alaykum, <b>{user.full_name}</b>!\n\n"
        f"🎬 <b>{BOT_NAME}</b> ga xush kelibsiz!\n\n"
        f"Qidirayotgan kino yoki serialingizning <b>kodini</b> (raqamini) yuboring, "
        f"yoki quyidagi tugmalardan birini tanlang 👇",
        reply_markup=main_menu_kb(is_admin=is_admin),
    )


@dp.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    user = message.from_user
    is_admin = user.id in ADMIN_IDS
    role = "Admin" if is_admin else "Foydalanuvchi"
    await message.answer(
        f"<b>Sizning ma'lumotlaringiz:</b>\n\n"
        f"ID: <code>{user.id}</code>\n"
        f"Ism: {user.full_name}\n"
        f"Username: @{user.username or 'yoq'}\n"
        f"Rol: {role}",
    )


@dp.callback_query(F.data == "main_menu")
async def cb_main_menu(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    is_admin = call.from_user.id in ADMIN_IDS
    text = f"🎬 <b>{BOT_NAME}</b>\n\nQuyidagi tugmalardan birini tanlang 👇"
    markup = main_menu_kb(is_admin=is_admin)
    if call.message.photo:
        await call.message.delete()
        await call.message.answer(text, reply_markup=markup)
    else:
        await call.message.edit_text(text, reply_markup=markup)


@dp.callback_query(F.data == "search_by_code")
async def cb_search_by_code(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "🔢 <b>Kod bo'yicha qidiruv</b>\n\n"
        "Kino yoki serial kodini (raqamni) yuboring.\n"
        "<i>Misol: 101 yoki 200</i>",
        reply_markup=back_to_menu_kb(),
    )


@dp.callback_query(F.data == "search_by_name")
async def cb_search_by_name(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SearchStates.waiting_query)
    await call.message.edit_text(
        "🔍 <b>Nom bo'yicha qidiruv</b>\n\n"
        "Qidirayotgan kino nomini kiriting:",
        reply_markup=back_to_menu_kb(),
    )


@dp.message(SearchStates.waiting_query)
async def handle_search_query(message: Message, state: FSMContext) -> None:
    await state.clear()
    query = message.text.strip()
    movies = await db.search_movies_by_name(query)

    if not movies:
        await message.answer(
            f"😔 <b>'{query}'</b> bo'yicha kino topilmadi.",
            reply_markup=back_to_menu_kb(),
        )
        return

    builder = InlineKeyboardBuilder()
    text = f"🔍 <b>'{query}'</b> bo'yicha natijalar:\n\n"
    for m in movies:
        text += f"• <b>{m['nomi']}</b> (Kod: <code>{m['kino_kodi']}</code>)\n"
        builder.button(text=f"🎬 {m['nomi']}", callback_data=f"get_movie_{m['kino_kodi']}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu"))

    await message.answer(text, reply_markup=builder.as_markup())


@dp.callback_query(F.data == "all_movies")
async def cb_all_movies(call: CallbackQuery) -> None:
    movies = await db.get_all_movies()
    if not movies:
        await call.message.edit_text("📭 Bazada hali kino yo'q.", reply_markup=back_to_menu_kb())
        return

    builder = InlineKeyboardBuilder()
    text = f"🎬 <b>Kinolar ro'yxati</b> ({len(movies)} ta):\n\n"
    for m in movies[:15]:
        text += f"• [{m['kino_kodi']}] {m['nomi']} ({m['sifat']})\n"
        builder.button(text=f"🎬 {m['nomi']}", callback_data=f"get_movie_{m['kino_kodi']}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu"))

    await call.message.edit_text(text, reply_markup=builder.as_markup())


@dp.callback_query(F.data == "all_series")
async def cb_all_series(call: CallbackQuery) -> None:
    series_list = await db.get_all_series()
    if not series_list:
        await call.message.edit_text("📭 Bazada hali serial yo'q.", reply_markup=back_to_menu_kb())
        return

    builder = InlineKeyboardBuilder()
    text = f"📺 <b>Seriallar ro'yxati</b> ({len(series_list)} ta):\n\n"
    for s in series_list:
        text += f"• [{s['code']}] <b>{s['title']}</b> — {s['genre']}\n"
        builder.button(text=f"📺 {s['title']}", callback_data=f"series_info_{s['code']}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu"))

    await call.message.edit_text(text, reply_markup=builder.as_markup())


@dp.callback_query(F.data.startswith("series_info_"))
async def cb_series_info(call: CallbackQuery) -> None:
    code = int(call.data.split("_")[2])
    series = await db.get_series_by_code(code)
    if not series:
        await call.answer("Serial topilmadi!", show_alert=True)
        return

    episodes = await db.get_episodes(code)
    if not episodes:
        await call.message.edit_text(
            f"📺 <b>{series['title']}</b>\n\n"
            f"🔢 <b>Kodi:</b> <code>{series['code']}</code>\n"
            f"🎭 <b>Janr:</b> {series['genre']}\n\n"
            f"⚠️ <i>Bu serialga hali qismlar yuklanmagan.</i>",
            reply_markup=back_to_menu_kb(),
        )
        return

    text = (
        f"📺 <b>{series['title']}</b>\n\n"
        f"🔢 <b>Kodi:</b> <code>{series['code']}</code>\n"
        f"🎭 <b>Janr:</b> {series['genre']}\n"
        f"📼 <b>Mavjud qismlar:</b> {len(episodes)} ta\n\n"
        f"Tomosha qilish uchun kerakli qismni tanlang 👇"
    )
    markup = episodes_paginated_kb(code, episodes, page=0, per_page=10)
    if series.get("poster_file_id"):
        try:
            await call.message.delete()
            await call.message.answer_photo(
                photo=series["poster_file_id"],
                caption=text,
                reply_markup=markup,
            )
        except Exception:
            await call.message.edit_text(text, reply_markup=markup)
    else:
        await call.message.edit_text(text, reply_markup=markup)


# ─────────────────────── KOD YUBORILGANDA (KINO VA SERIAL) ───────────────────────

@dp.message(StateFilter(None), F.text.regexp(r"^\d+$"))
async def handle_code(message: Message) -> None:
    code = int(message.text.strip())

    # 1. Seriallar bazasidan tekshiramiz
    series = await db.get_series_by_code(code)
    if series:
        episodes = await db.get_episodes(code)
        if episodes:
            text = (
                f"📺 <b>{series['title']}</b>\n\n"
                f"🔢 <b>Serial kodi:</b> <code>{series['code']}</code>\n"
                f"🎭 <b>Janr:</b> {series['genre']}\n"
                f"📼 <b>Mavjud qismlar:</b> {len(episodes)} ta\n\n"
                f"<i>Tomosha qilish uchun quyidagi qismlardan birini tanlang 👇</i>"
            )
            markup = episodes_paginated_kb(code, episodes, page=0, per_page=10)
            if series.get("poster_file_id"):
                try:
                    await message.answer_photo(
                        photo=series["poster_file_id"],
                        caption=text,
                        reply_markup=markup,
                    )
                except Exception:
                    await message.answer(text, reply_markup=markup)
            else:
                await message.answer(text, reply_markup=markup)
        else:
            await message.answer(
                f"📺 <b>{series['title']}</b>\n\n"
                f"🔢 <b>Serial kodi:</b> <code>{series['code']}</code>\n"
                f"🎭 <b>Janr:</b> {series['genre']}\n\n"
                f"⚠️ <i>Bu serial uchun hali qismlar yuklanmagan.</i>",
                reply_markup=back_to_menu_kb(),
            )
        return

    # 2. Kinolar bazasidan tekshiramiz
    movie = await db.get_movie_by_code(code)
    if movie:
        caption = (
            f"🎬 <b>{movie['nomi']}</b>\n\n"
            f"🔢 <b>Kod:</b> <code>{movie['kino_kodi']}</code>\n"
            f"🎭 <b>Janr:</b> {movie['janri']}\n"
            f"🌍 <b>Til:</b> {movie['tili']}\n"
            f"📺 <b>Sifat:</b> {movie['sifat']}\n\n"
            f"🔒 <i>Ushbu video himoyalangan (uzatish cheklangan).</i>"
        )
        try:
            await message.answer_video(
                video=movie["video_file_id"],
                caption=caption,
                reply_markup=back_to_menu_kb(),
                protect_content=True,
            )
        except Exception:
            try:
                await message.answer_document(
                    document=movie["video_file_id"],
                    caption=caption,
                    reply_markup=back_to_menu_kb(),
                    protect_content=True,
                )
            except Exception as e:
                logger.error(f"Kino yuborishda xatolik: {e}")
                await message.answer("❌ Videoni yuklashda xatolik yuz berdi!", reply_markup=back_to_menu_kb())
        return

    # 3. Topilmadi
    await message.answer(
        f"😔 <b>{code}</b> kodli kino yoki serial topilmadi.\n\n"
        f"Iltimos, kodni to'g'ri kiritganingizni tekshiring.",
        reply_markup=back_to_menu_kb(),
    )


# ─────────────────────── QISMLAR SAHIFALASH (10 ta 10 ta) ───────────────────────

@dp.callback_query(F.data.startswith("eppage_"))
async def cb_episodes_page(call: CallbackQuery) -> None:
    parts = call.data.split("_")
    series_code = int(parts[1])
    page = int(parts[2])

    episodes = await db.get_episodes(series_code)
    markup = episodes_paginated_kb(series_code, episodes, page=page, per_page=10)
    try:
        await call.message.edit_reply_markup(reply_markup=markup)
    except Exception:
        pass
    await call.answer()


@dp.callback_query(F.data == "noop")
async def cb_noop(call: CallbackQuery) -> None:
    await call.answer()


# ─────────────────────── SERIAL QISMI BOSILGANDA (ep_ callback) ───────────────────────

@dp.callback_query(F.data.startswith("ep_"))
async def cb_send_episode(call: CallbackQuery) -> None:
    parts = call.data.split("_")
    series_code = int(parts[1])
    episode_num = int(parts[2])

    file_id = await db.get_episode_file_id(series_code, episode_num)
    if not file_id:
        await call.answer("❌ Bu qism videosi topilmadi!", show_alert=True)
        return

    series = await db.get_series_by_code(series_code)
    title = series["title"] if series else "Serial"

    caption = (
        f"📺 <b>{title}</b>\n"
        f"🎬 <b>{episode_num}-qism</b>\n\n"
        f"🔢 Serial kodi: <code>{series_code}</code>"
    )

    try:
        await call.message.answer_video(video=file_id, caption=caption, protect_content=True)
    except Exception:
        try:
            await call.message.answer_document(document=file_id, caption=caption, protect_content=True)
        except Exception as e:
            logger.error(f"Qism yuborishda xatolik: {e}")
            await call.answer("❌ Ushbu qism videosini yuborib bo'lmadi!", show_alert=True)
            return
    await call.answer()


@dp.callback_query(F.data.startswith("get_movie_"))
async def cb_get_movie(call: CallbackQuery) -> None:
    kino_kodi = int(call.data.split("_")[2])
    movie = await db.get_movie_by_code(kino_kodi)
    if not movie:
        await call.answer("Kino topilmadi!", show_alert=True)
        return

    caption = (
        f"🎬 <b>{movie['nomi']}</b>\n\n"
        f"🔢 <b>Kod:</b> <code>{movie['kino_kodi']}</code>\n"
        f"🎭 <b>Janr:</b> {movie['janri']}\n"
        f"📺 <b>Sifat:</b> {movie['sifat']}\n\n"
        f"🔒 <i>Ushbu video himoyalangan (uzatish cheklangan).</i>"
    )
    try:
        await call.message.answer_video(video=movie["video_file_id"], caption=caption, protect_content=True)
    except Exception:
        try:
            await call.message.answer_document(document=movie["video_file_id"], caption=caption, protect_content=True)
        except Exception as e:
            logger.error(f"Kino yuborishda xatolik: {e}")
            await call.answer("❌ Ushbu kinoni yuborib bo'lmadi!", show_alert=True)
            return
    await call.answer()


# ─────────────────────── ADMIN PANEL VA STATISTIKA ───────────────────────

@dp.callback_query(F.data == "admin_panel", IsAdmin())
async def cb_admin_panel(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "⚙️ <b>Admin Panel</b>\n\nKerakli amaliyotni tanlang 👇",
        reply_markup=admin_panel_kb(),
    )


@dp.callback_query(F.data == "admin_stats", IsAdmin())
async def cb_admin_stats(call: CallbackQuery) -> None:
    movies_count = await db.get_movies_count()
    series_count = await db.get_series_count()
    users_count  = await db.get_users_count()

    text = (
        f"📊 <b>Bot Statistikasi</b>\n\n"
        f"🎬 Kinolar soni:      <b>{movies_count}</b> ta\n"
        f"📺 Seriallar soni:    <b>{series_count}</b> ta\n"
        f"👥 Foydalanuvchilar: <b>{users_count}</b> ta"
    )
    await call.message.edit_text(text, reply_markup=back_to_admin_kb())


# ─────────────────────── ADMIN: YANGI SERIAL YARATISH (FSM) ───────────────────────

@dp.callback_query(F.data == "admin_create_series", IsAdmin())
async def cb_create_series_start(call: CallbackQuery, state: FSMContext) -> None:
    next_code = await db.get_next_code()
    await state.update_data(code=next_code)
    await state.set_state(AddSeriesStates.waiting_title)
    await call.message.edit_text(
        f"📺 <b>Yangi serial yaratish</b>\n\n"
        f"🔢 Ushbu serial uchun avtomatik kod: <b>{next_code}</b>\n\n"
        f"<b>1-qadam:</b> Serial nomini kiriting:\n"
        f"<i>Misol: Qashqirlar Makoni</i>\n\n"
        f"<i>Bekor qilish uchun /cancel yozing</i>",
    )


@dp.message(AddSeriesStates.waiting_title, IsAdmin())
async def fsm_series_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(AddSeriesStates.waiting_genre)
    await message.answer(
        "<b>3-qadam:</b> Serial janrini kiriting:\n"
        "<i>Misol: Jangari, Kriminal, Drama</i>"
    )


@dp.message(AddSeriesStates.waiting_genre, IsAdmin())
async def fsm_series_genre(message: Message, state: FSMContext) -> None:
    genre = message.text.strip()
    await state.update_data(genre=genre)
    await state.set_state(AddSeriesStates.waiting_poster)
    await message.answer(
        "<b>3-qadam:</b> Serial rasmini (posterni) yuboring 👇\n\n"
        "<i>(Agar rasm qo'ymoqchi bo'lmasangiz, /skip deb yozing)</i>"
    )


@dp.message(AddSeriesStates.waiting_poster, IsAdmin(), F.photo)
async def fsm_series_poster_photo(message: Message, state: FSMContext) -> None:
    poster_id = message.photo[-1].file_id
    data = await state.get_data()
    await state.clear()

    success = await db.add_series(
        code=data["code"],
        title=data["title"],
        genre=data["genre"],
        poster_file_id=poster_id,
    )
    if success:
        await message.answer_photo(
            photo=poster_id,
            caption=(
                f"✅ <b>Yangi serial yaratildi va rasmi o'rnatildi!</b>\n\n"
                f"📺 <b>Nomi:</b> {data['title']}\n"
                f"🔢 <b>Kodi:</b> <code>{data['code']}</code>\n"
                f"🎭 <b>Janr:</b> {data['genre']}\n\n"
                f"Endi '➕ Serialga qism qo'shish' orqali qismlarini yuklashingiz mumkin."
            ),
            reply_markup=admin_panel_kb(),
        )
    else:
        await message.answer("❌ Xatolik yuz berdi. Qayta urinib ko'ring.", reply_markup=back_to_admin_kb())


@dp.message(AddSeriesStates.waiting_poster, IsAdmin(), Command("skip"))
async def fsm_series_poster_skip(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()

    success = await db.add_series(
        code=data["code"],
        title=data["title"],
        genre=data["genre"],
        poster_file_id=None,
    )
    if success:
        await message.answer(
            f"✅ <b>Yangi serial muvaffaqiyatli yaratildi (rasmsiz)!</b>\n\n"
            f"📺 <b>Nomi:</b> {data['title']}\n"
            f"🔢 <b>Kodi:</b> <code>{data['code']}</code>\n"
            f"🎭 <b>Janr:</b> {data['genre']}\n\n"
            f"Keyinchalik '🖼️ Serialga rasm qo'yish' orqali ham rasm qo'yishingiz mumkin.",
            reply_markup=admin_panel_kb(),
        )
    else:
        await message.answer("❌ Xatolik yuz berdi. Qayta urinib ko'ring.", reply_markup=back_to_admin_kb())


@dp.message(AddSeriesStates.waiting_poster, IsAdmin())
async def fsm_series_poster_invalid(message: Message) -> None:
    await message.answer("❌ Iltimos, rasm (foto) yuboring yoki o'tkazib yuborish uchun /skip yozing!")


# ─────────────────────── ADMIN: SERIALGA RASM QO'YISH (FSM) ───────────────────────

@dp.callback_query(F.data == "admin_set_poster", IsAdmin())
async def cb_set_poster_start(call: CallbackQuery, state: FSMContext) -> None:
    series_list = await db.get_all_series()
    if not series_list:
        await call.message.edit_text("⚠️ Bazada seriallar yo'q!", reply_markup=back_to_admin_kb())
        return

    await state.set_state(SetPosterStates.waiting_series_code)
    builder = InlineKeyboardBuilder()
    text = "🖼️ <b>Serialga rasm qo'yish</b>\n\nQaysi serialga rasm (poster) o'rnatmoqchisiz? Tanlang yoki kodini yozing:\n\n"
    for s in series_list:
        status_icon = "🖼️ Rasm bor" if s.get("poster_file_id") else "❌ Rasmsiz"
        text += f"• <code>{s['code']}</code> — <b>{s['title']}</b> ({status_icon})\n"
        builder.button(text=f"📺 {s['title']} ({s['code']})", callback_data=f"sel_post_{s['code']}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ Admin Panel", callback_data="admin_panel"))

    await call.message.edit_text(text, reply_markup=builder.as_markup())


@dp.callback_query(F.data.startswith("sel_post_"), IsAdmin())
async def cb_sel_post_series(call: CallbackQuery, state: FSMContext) -> None:
    code = int(call.data.split("_")[2])
    series = await db.get_series_by_code(code)
    if not series:
        await call.answer("Serial topilmadi!", show_alert=True)
        return

    await state.update_data(series_code=code, series_title=series["title"])
    await state.set_state(SetPosterStates.waiting_photo)
    await call.message.edit_text(
        f"📸 <b>{series['title']}</b> (Kodi: <code>{code}</code>)\n\n"
        f"Ushbu serial uchun rasmni (posterni) yuboring 👇\n\n"
        f"<i>Bekor qilish uchun /cancel yozing</i>",
        reply_markup=back_to_admin_kb(),
    )


@dp.message(SetPosterStates.waiting_series_code, IsAdmin())
async def fsm_poster_code(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip().isdigit():
        await message.answer("❌ Iltimos, serial kodini raqam ko'rinishida yuboring!")
        return

    code = int(message.text.strip())
    series = await db.get_series_by_code(code)
    if not series:
        await message.answer(f"❌ <b>{code}</b> kodli serial topilmadi! Qayta kiriting:")
        return

    await state.update_data(series_code=code, series_title=series["title"])
    await state.set_state(SetPosterStates.waiting_photo)
    await message.answer(
        f"📸 <b>{series['title']}</b> (Kodi: <code>{code}</code>)\n\n"
        f"Ushbu serial uchun rasmni (posterni) yuboring 👇\n\n"
        f"<i>Bekor qilish uchun /cancel yozing</i>"
    )


@dp.message(SetPosterStates.waiting_photo, IsAdmin(), F.photo)
async def fsm_poster_photo(message: Message, state: FSMContext) -> None:
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    series_code = data["series_code"]
    series_title = data["series_title"]
    await state.clear()

    await db.update_series_poster(series_code, photo_id)
    await message.answer_photo(
        photo=photo_id,
        caption=(
            f"✅ <b>{series_title}</b> serialiga rasm muvaffaqiyatli o'rnatildi!\n\n"
            f"Endi foydalanuvchilar <code>{series_code}</code> kodini yuborganda ushbu rasm va 10 tadan sahifalangan qismlar chiqadi."
        ),
        reply_markup=admin_panel_kb(),
    )


@dp.message(SetPosterStates.waiting_photo, IsAdmin())
async def fsm_poster_photo_wrong(message: Message) -> None:
    await message.answer("❌ Iltimos, rasm (foto) yuboring! Bekor qilish uchun /cancel yozing.")


# ─────────────────────── ADMIN: SERIALGA QISM QO'SHISH (FSM) ───────────────────────

episode_upload_lock = asyncio.Lock()


def format_episode_ranges(episodes: list[dict]) -> str:
    """[1, 2, 3, 5, 6] -> '1-3, 5-6'"""
    if not episodes:
        return "Hali qism yo'q"
    nums = sorted({e["episode_num"] for e in episodes if e["episode_num"] > 0})
    if not nums:
        return "Hali qism yo'q"
    ranges = []
    start = prev = nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
        else:
            ranges.append(f"{start}-{prev}" if start != prev else str(start))
            start = prev = n
    ranges.append(f"{start}-{prev}" if start != prev else str(start))
    return ", ".join(ranges)


def find_missing_ranges(episodes: list[dict]) -> str | None:
    """Mavjud qismlar orasidagi tushib qolgan oraliqlarni topadi (masalan: 15-37)."""
    if not episodes:
        return None
    nums = sorted({e["episode_num"] for e in episodes if e["episode_num"] > 0})
    if not nums or len(nums) == 1:
        return None
    max_num = nums[-1]
    missing = [x for x in range(1, max_num + 1) if x not in nums]
    if not missing:
        return None
    ranges = []
    start = prev = missing[0]
    for n in missing[1:]:
        if n == prev + 1:
            prev = n
        else:
            ranges.append(f"{start}-{prev}" if start != prev else str(start))
            start = prev = n
    ranges.append(f"{start}-{prev}" if start != prev else str(start))
    return ", ".join(ranges)


async def enter_episode_upload_mode(target_message: Message, state: FSMContext, code: int, is_callback: bool = False) -> None:
    """Serial tanlangach, uzluksiz qism yuklash holatiga o'tkazadi."""
    series = await db.get_series_by_code(code)
    if not series:
        if is_callback:
            await target_message.answer(f"❌ <b>{code}</b> kodli serial topilmadi!")
        else:
            await target_message.answer(f"❌ <b>{code}</b> kodli serial topilmadi! Qayta kiriting:")
        return

    await state.update_data(series_code=code, series_title=series["title"])
    await state.set_state(AddEpisodeStates.waiting_video)

    episodes = await db.get_episodes(code)
    ranges_text = format_episode_ranges(episodes)
    missing_text = find_missing_ranges(episodes)
    next_ep = await db.get_next_episode_num(code)
    total = len(episodes)

    missing_notice = f"\n⚠️ <b>Yetishmayotgan qismlar:</b> {missing_text}\n" if missing_text else ""

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Yuklashni tugatish", callback_data="finish_episodes"))

    text = (
        f"📺 Tanlangan serial: <b>{series['title']}</b> (Kodi: <code>{code}</code>)\n"
        f"📼 Mavjud qismlar: <b>{ranges_text}</b> (Jami: {total} ta){missing_notice}\n"
        f"▶️ <b>Navbatdagi kutilayotgan qism: {next_ep}-qism</b>\n\n"
        f"📥 <b>Videolarni yuboring (yoki kanaldan forward qiling)!</b>\n\n"
        f"<i>💡 Bot videolarni izohidan (1-qism, 2-qism...) avtomatik aniqlab saqlaydi. "
        f"Agar izoh bo'lmasa, navbatdagi yetishmayotgan ({next_ep}-qism...) qilib joylashtiradi!</i>\n\n"
        f"Yuklab bo'lgach, pastdagi <b>'✅ Yuklashni tugatish'</b> tugmasini bosing 👇"
    )

    if is_callback:
        await target_message.edit_text(text, reply_markup=builder.as_markup())
    else:
        await target_message.answer(text, reply_markup=builder.as_markup())


@dp.callback_query(F.data == "admin_add_episode", IsAdmin())
async def cb_add_episode_start(call: CallbackQuery, state: FSMContext) -> None:
    series_list = await db.get_all_series()
    if not series_list:
        await call.message.edit_text(
            "⚠️ Bazada hech qanday serial yo'q!\n"
            "Avval <b>'📺 Yangi serial yaratish'</b> tugmasi orqali serial yarating.",
            reply_markup=back_to_admin_kb(),
        )
        return

    await state.set_state(AddEpisodeStates.waiting_series_code)
    builder = InlineKeyboardBuilder()
    text = "➕ <b>Serialga qism qo'shish</b>\n\nQaysi serialga qism qo'shmoqchisiz? Quyidagilardan birini tanlang yoki kodini yuboring:\n\n"
    for s in series_list:
        text += f"• <code>{s['code']}</code> — <b>{s['title']}</b>\n"
        builder.button(text=f"📺 {s['title']} ({s['code']})", callback_data=f"sel_ser_{s['code']}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ Admin Panel", callback_data="admin_panel"))

    await call.message.edit_text(text, reply_markup=builder.as_markup())


@dp.callback_query(F.data.startswith("sel_ser_"), IsAdmin())
async def cb_sel_series_for_ep(call: CallbackQuery, state: FSMContext) -> None:
    code = int(call.data.split("_")[2])
    await enter_episode_upload_mode(call.message, state, code, is_callback=True)


@dp.message(AddEpisodeStates.waiting_series_code, IsAdmin())
async def fsm_episode_series_code(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip().isdigit():
        await message.answer("❌ Iltimos, serial kodini raqam ko'rinishida yuboring!")
        return
    code = int(message.text.strip())
    await enter_episode_upload_mode(message, state, code, is_callback=False)


# Batch upload debounce tracking
batch_upload_tasks: dict[int, asyncio.Task] = {}
batch_upload_data: dict[int, list[dict]] = {}


async def _flush_batch_summary(chat_id: int, user_id: int, series_code: int, series_title: str) -> None:
    """Barcha forward qilingan videolar kelib bo'lgach (1.5s jimlikdan so'ng) umumiy hisobot yuboradi."""
    await asyncio.sleep(1.5)
    items = batch_upload_data.pop(user_id, [])
    batch_upload_tasks.pop(user_id, None)

    if not items:
        return

    episodes = await db.get_episodes(series_code)
    total = len(episodes)
    ranges_text = format_episode_ranges(episodes)
    missing_text = find_missing_ranges(episodes)

    new_eps = [i["ep_num"] for i in items if i["is_new"]]
    updated_eps = [i["ep_num"] for i in items if not i["is_new"]]

    lines = []
    lines.append(f"📥 <b>{len(items)} ta video muvaffaqiyatli qabul qilindi!</b>\n")
    if new_eps:
        lines.append(f"✅ <b>Yangi qo'shildi ({len(new_eps)} ta):</b> {format_episode_ranges([{'episode_num': x} for x in new_eps])}")
    if updated_eps:
        lines.append(f"🔄 <b>Yangilandi ({len(updated_eps)} ta):</b> {format_episode_ranges([{'episode_num': x} for x in updated_eps])}")

    lines.append(f"\n📼 <b>Bazada jami:</b> <b>{ranges_text}</b> (<b>{total} ta</b>)")
    if missing_text:
        lines.append(f"⚠️ <b>Yetishmayotgan qismlar:</b> <code>{missing_text}</code>")
        next_ep = await db.get_next_episode_num(series_code)
        lines.append(f"▶️ <b>Navbatdagi kutilayotgan:</b> {next_ep}-qism")
    else:
        lines.append("🎉 <i>Barcha qismlar to'liq saqlandi!</i>")

    lines.append("\n▶️ Yana video tashlashingiz yoki tugatish tugmasini bosishingiz mumkin:")

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Yuklashni tugatish", callback_data="finish_episodes"))

    try:
        await bot.send_message(chat_id=chat_id, text="\n".join(lines), reply_markup=builder.as_markup())
    except Exception as e:
        logger.warning(f"Failed to send batch summary: {e}")


@dp.message(AddEpisodeStates.waiting_video, IsAdmin(), F.video | F.document)
async def fsm_episode_video(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    series_code = data.get("series_code")
    series_title = data.get("series_title", "Serial")
    if not series_code:
        await message.answer("❌ Qaysi serialga yuklanayotgani aniqlanmadi. Qaytadan 'Serialga qism qo'shish'ni bosing.", reply_markup=admin_panel_kb())
        await state.clear()
        return

    # Video yoki Hujjat (fayl ko'rinishida yuborilgan video)
    if message.video:
        file_id = message.video.file_id
        filename = message.video.file_name or ""
    elif message.document:
        file_id = message.document.file_id
        filename = message.document.file_name or ""
    else:
        await message.answer("❌ Iltimos, video yoki video-fayl yuboring!")
        return

    caption = message.caption or ""

    # Kanaldan forward qilingan videoning izohidan yoki nomidan qismni aniqlash
    detected_ep = extract_episode_number(caption, filename)

    async with episode_upload_lock:
        if detected_ep is not None and detected_ep > 0:
            ep_num = detected_ep
        else:
            ep_num = await db.get_next_episode_num(series_code)

        success, is_new = await db.add_episode(series_code, ep_num, file_id)

    # Debounce orqali yagona hisobot yuborish
    user_id = message.from_user.id
    if user_id not in batch_upload_data:
        batch_upload_data[user_id] = []
    batch_upload_data[user_id].append({
        "ep_num": ep_num,
        "is_new": is_new,
    })

    if user_id in batch_upload_tasks and not batch_upload_tasks[user_id].done():
        batch_upload_tasks[user_id].cancel()

    batch_upload_tasks[user_id] = asyncio.create_task(
        _flush_batch_summary(message.chat.id, user_id, series_code, series_title)
    )


@dp.callback_query(F.data == "finish_episodes", IsAdmin())
async def cb_finish_episodes(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    series_title = data.get("series_title", "Serial")
    series_code = data.get("series_code")
    await state.clear()

    episodes = await db.get_episodes(series_code) if series_code else []
    total = len(episodes)
    ranges_text = format_episode_ranges(episodes)
    missing_text = find_missing_ranges(episodes)

    missing_info = f"\n⚠️ <b>Yetishmayotgan qismlar:</b> {missing_text}" if missing_text else ""

    await call.message.edit_text(
        f"🎉 <b>Qismlar yuklash yakunlandi!</b>\n\n"
        f"📺 Serial: <b>{series_title}</b> (Kodi: <code>{series_code}</code>)\n"
        f"📼 Mavjud qismlar: <b>{ranges_text}</b>\n"
        f"🔢 Jami qismlar soni: <b>{total}</b> ta{missing_info}\n\n"
        f"Foydalanuvchilar <code>{series_code}</code> kodini yuborib tomosha qilishlari mumkin.",
        reply_markup=admin_panel_kb(),
    )


@dp.message(AddEpisodeStates.waiting_video, IsAdmin())
async def fsm_episode_video_wrong(message: Message) -> None:
    await message.answer("❌ Iltimos, video yoki video-fayl yuboring! (Yuklashni to'xtatish uchun /cancel yoki tugmani bosing)")


@dp.message(StateFilter(None), IsAdmin(), F.video | F.document)
async def handle_unprompted_media(message: Message) -> None:
    series_list = await db.get_all_series()
    builder = InlineKeyboardBuilder()
    if series_list:
        for s in series_list:
            builder.button(text=f"📺 {s['title']} ({s['code']})", callback_data=f"sel_ser_{s['code']}")
        builder.adjust(1)
    builder.row(InlineKeyboardButton(text="⚙️ Admin Panel", callback_data="admin_panel"))

    await message.answer(
        "💡 <b>Video qabul qilindi, ammo qaysi serialga yuklash kerakligi tanlanmagan!</b>\n\n"
        "Serialga qism qo'shish uchun quyidagi ro'yxatdan kerakli serialni tanlang, so'ng videolarni forward qiling 👇",
        reply_markup=builder.as_markup(),
    )


# ─────────────────────── ADMIN: QISMLARNI TOZALASH ───────────────────────

@dp.callback_query(F.data == "admin_clear_episodes", IsAdmin())
async def cb_clear_episodes_start(call: CallbackQuery) -> None:
    series_list = await db.get_all_series()
    if not series_list:
        await call.message.edit_text("⚠️ Bazada seriallar yo'q!", reply_markup=back_to_admin_kb())
        return

    builder = InlineKeyboardBuilder()
    text = (
        "🗑️ <b>Serial qismlarini tozalash (qaytadan to'g'ri yuklash uchun)</b>\n\n"
        "Qaysi serialning qismlarini o'chirib, qaytadan to'g'ri tartibda yuklamoqchisiz? Tanlang:\n\n"
    )
    for s in series_list:
        ep_count = len(await db.get_episodes(s["code"]))
        text += f"• <code>{s['code']}</code> — <b>{s['title']}</b> ({ep_count} ta qism)\n"
        builder.button(text=f"🗑️ {s['title']} ({ep_count} ta)", callback_data=f"conf_clr_{s['code']}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ Admin Panel", callback_data="admin_panel"))

    await call.message.edit_text(text, reply_markup=builder.as_markup())


@dp.callback_query(F.data.startswith("conf_clr_"), IsAdmin())
async def cb_confirm_clear_episodes(call: CallbackQuery) -> None:
    code = int(call.data.split("_")[2])
    series = await db.get_series_by_code(code)
    if not series:
        await call.answer("Serial topilmadi!", show_alert=True)
        return

    await db.clear_series_episodes(code)
    await call.message.edit_text(
        f"✅ <b>{series['title']}</b> (Kodi: <code>{code}</code>) ning barcha qismlari tozalandi!\n\n"
        f"Endi <b>'➕ Serialga qism qo'shish'</b> bo'limiga kirib, kanaldan videolarni forward qilib tashlasangiz, "
        f"bot har bir qismni izohidan (caption: 1-qism, 2-qism...) avtomatik o'qib, 100% to'g'ri tartibda saqlab oladi!",
        reply_markup=admin_panel_kb(),
    )


# ─────────────────────── ADMIN: KINO QO'SHISH (FSM) ───────────────────────

@dp.callback_query(F.data == "admin_add_movie", IsAdmin())
async def cb_add_movie_start(call: CallbackQuery, state: FSMContext) -> None:
    next_code = await db.get_next_code()
    await state.update_data(kino_kodi=next_code)
    await state.set_state(AddMovieStates.waiting_video)
    await call.message.edit_text(
        f"🎬 <b>Yangi kino qo'shish</b>\n\n"
        f"🔢 Ushbu kino uchun avtomatik kod: <b>{next_code}</b>\n\n"
        f"<b>1-qadam:</b> Kino videosini yuboring 👇\n\n"
        f"<i>Bekor qilish uchun /cancel yozing</i>",
    )


@dp.message(AddMovieStates.waiting_video, IsAdmin(), F.video)
async def fsm_movie_video(message: Message, state: FSMContext) -> None:
    await state.update_data(video_file_id=message.video.file_id)
    await state.set_state(AddMovieStates.waiting_nomi)
    await message.answer("✅ Video qabul qilindi!\n\n<b>2-qadam:</b> Kino nomini kiriting:")


@dp.message(AddMovieStates.waiting_video, IsAdmin())
async def fsm_movie_video_invalid(message: Message) -> None:
    await message.answer("❌ Iltimos, video yuboring!")


@dp.message(AddMovieStates.waiting_nomi, IsAdmin())
async def fsm_movie_title(message: Message, state: FSMContext) -> None:
    await state.update_data(nomi=message.text.strip())
    await state.set_state(AddMovieStates.waiting_janri)
    await message.answer("<b>4-qadam:</b> Janrini kiriting:")


@dp.message(AddMovieStates.waiting_janri, IsAdmin())
async def fsm_movie_genre(message: Message, state: FSMContext) -> None:
    await state.update_data(janri=message.text.strip())
    await state.set_state(AddMovieStates.waiting_tili)
    await message.answer("<b>5-qadam:</b> Tilini kiriting (masalan: O'zbek):")


@dp.message(AddMovieStates.waiting_tili, IsAdmin())
async def fsm_movie_lang(message: Message, state: FSMContext) -> None:
    await state.update_data(tili=message.text.strip())
    await state.set_state(AddMovieStates.waiting_sifat)
    await message.answer("<b>6-qadam:</b> Sifatini kiriting (masalan: 720p, 1080p):")


@dp.message(AddMovieStates.waiting_sifat, IsAdmin())
async def fsm_movie_quality(message: Message, state: FSMContext) -> None:
    await state.update_data(sifat=message.text.strip())
    data = await state.get_data()
    await state.set_state(AddMovieStates.confirm)
    await message.answer(
        f"📋 <b>Ma'lumotlarni tekshiring:</b>\n\n"
        f"🔢 Kod:   <code>{data['kino_kodi']}</code>\n"
        f"🎬 Nomi:  <b>{data['nomi']}</b>\n"
        f"🎭 Janr:  {data['janri']}\n"
        f"🌍 Til:   {data['tili']}\n"
        f"📺 Sifat: {data['sifat']}\n\n"
        f"Saqlashni tasdiqlaysizmi?",
        reply_markup=confirm_kb(),
    )


@dp.callback_query(AddMovieStates.confirm, F.data == "confirm_save", IsAdmin())
async def fsm_movie_confirm(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    ok = await db.add_movie(
        kino_kodi=data["kino_kodi"],
        nomi=data["nomi"],
        janri=data["janri"],
        tili=data["tili"],
        sifat=data["sifat"],
        video_file_id=data["video_file_id"],
    )
    if ok:
        await call.message.edit_text(
            f"✅ <b>{data['nomi']}</b> muvaffaqiyatli saqlandi! (Kod: <code>{data['kino_kodi']}</code>)",
            reply_markup=back_to_admin_kb(),
        )
    else:
        await call.message.edit_text("❌ Bu kodli kino allaqachon mavjud!", reply_markup=back_to_admin_kb())


@dp.callback_query(F.data == "cancel_action")
async def cb_cancel_action(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text("❌ Bekor qilindi.", reply_markup=back_to_menu_kb())


@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Jarayon bekor qilindi.", reply_markup=back_to_menu_kb())


# ─────────────────────── ASOSIY FUNKSIYA ───────────────────────

async def start_web_server() -> None:
    """Render.com Web Service uchun fon rejimida kichik HTTP server ishga tushiradi."""
    app = web.Application()

    async def handle_ping(request: web.Request) -> web.Response:
        return web.Response(text="Bot is running 24/7! 🚀", content_type="text/plain")

    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)

    port = int(os.getenv("PORT", "8080"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Render Web Server ishga tushdi (port: {port})")


async def main() -> None:
    await db.create_tables()
    logger.info("Malumotlar bazasi tayyor.")

    # Render Web Service uchun port ochish
    try:
        await start_web_server()
    except Exception as e:
        logger.warning(f"Web serverni ishga tushirishda ogohlantirish: {e}")

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot ishga tushdi! Seriallar va kinolar qidirishga tayyor.")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
