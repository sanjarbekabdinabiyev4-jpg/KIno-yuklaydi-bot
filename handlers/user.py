from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

from config import ADMIN_IDS, BOT_NAME
from keyboards import main_menu_kb, back_to_menu_kb
from database import get_movie_by_code, search_movies_by_name, get_all_movies
from keyboards import movie_results_kb, paginate_movies_kb
from utils.helpers import movie_caption, movie_short_info
from utils.states import SearchStates
from aiogram.fsm.context import FSMContext

router = Router()


# ─────────────────────── /myid — ID ko'rish ───────────────────────

@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    """Foydalanuvchining Telegram ID'sini ko'rsatadi."""
    user = message.from_user
    is_admin = user.id in ADMIN_IDS
    role = "Admin" if is_admin else "Foydalanuvchi"
    await message.answer(
        f"<b>Sizning ma'lumotlaringiz:</b>\n\n"
        f"ID: <code>{user.id}</code>\n"
        f"Ism: {user.full_name}\n"
        f"Username: @{user.username or 'yoq'}\n"
        f"Rol: {role}\n\n"
        f"<i>Admin bo'lish uchun shu ID ni .env faylidagi ADMIN_IDS ga yozing.</i>",
        parse_mode="HTML",
    )


# ─────────────────────── /start ───────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Botni ishga tushirish."""
    is_admin = message.from_user.id in ADMIN_IDS
    await message.answer(
        f"👋 Xush kelibsiz, <b>{message.from_user.full_name}</b>!\n\n"
        f"🎬 <b>{BOT_NAME}</b> ga xush kelibsiz!\n\n"
        f"Bu bot orqali siz kinolarni:\n"
        f"  🔢 <b>Kod</b> yoki\n"
        f"  🔍 <b>Nom</b> bo'yicha qidirishingiz mumkin.\n\n"
        f"Quyidagi tugmalardan birini tanlang 👇",
        parse_mode="HTML",
        reply_markup=main_menu_kb(is_admin=is_admin),
    )


# ─────────────────────── BOSH MENYU (callback) ───────────────────────

@router.callback_query(F.data == "main_menu")
async def cb_main_menu(call: CallbackQuery) -> None:
    """Bosh menyuga qaytish."""
    is_admin = call.from_user.id in ADMIN_IDS
    await call.message.edit_text(
        f"🎬 <b>{BOT_NAME}</b>\n\nQuyidagi tugmalardan birini tanlang 👇",
        parse_mode="HTML",
        reply_markup=main_menu_kb(is_admin=is_admin),
    )


# ─────────────────────── KOD BO'YICHA QIDIRUV (callback) ───────────────────────

@router.callback_query(F.data == "search_by_code")
async def cb_search_by_code(call: CallbackQuery) -> None:
    """Kod bo'yicha qidiruv yo'riqnomasi."""
    await call.message.edit_text(
        "🔢 <b>Kod bo'yicha qidiruv</b>\n\n"
        "Kino kodini (raqamni) yuboring.\n"
        "<i>Misol: 101</i>",
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(),
    )


# ─────────────────────── NOM BO'YICHA QIDIRUV ───────────────────────

@router.callback_query(F.data == "search_by_name")
async def cb_search_by_name(call: CallbackQuery, state: FSMContext) -> None:
    """Nom bo'yicha qidiruv holatini boshlaydi."""
    await state.set_state(SearchStates.waiting_query)
    await call.message.edit_text(
        "🔍 <b>Nom bo'yicha qidiruv</b>\n\n"
        "Kino nomini (yoki qismini) yuboring:\n"
        "<i>Misol: Avengers</i>",
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(),
    )


@router.message(SearchStates.waiting_query)
async def handle_search_query(message: Message, state: FSMContext) -> None:
    """Nom bo'yicha qidiruv natijalarini ko'rsatadi."""
    await state.clear()
    query = message.text.strip()
    movies = await search_movies_by_name(query)

    if not movies:
        await message.answer(
            f"😔 <b>'{query}'</b> bo'yicha hech narsa topilmadi.\n\n"
            "Boshqa so'z bilan urinib ko'ring.",
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(),
        )
        return

    text = f"🔍 <b>'{query}'</b> bo'yicha <b>{len(movies)}</b> ta natija topildi:\n\n"
    for m in movies:
        text += f"  • {movie_short_info(m)}\n"
    text += "\nQuyidagi tugmadan kinoni tanlang 👇"

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=movie_results_kb([m.kino_kodi for m in movies]),
    )


# ─────────────────────── /search BUYRUG'I ───────────────────────

@router.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext) -> None:
    """Nom bo'yicha qidiruv buyrug'i."""
    await state.set_state(SearchStates.waiting_query)
    await message.answer(
        "🔍 <b>Nom bo'yicha qidiruv</b>\n\nKino nomini yuboring:",
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(),
    )


# ─────────────────────── BARCHA KINOLAR ───────────────────────

@router.callback_query(F.data == "all_movies")
async def cb_all_movies(call: CallbackQuery) -> None:
    """Barcha kinolarni sahifalab ko'rsatadi."""
    movies = await get_all_movies()
    if not movies:
        await call.message.edit_text(
            "📭 Bazada hali kino yo'q.",
            reply_markup=back_to_menu_kb(),
        )
        return
    await call.message.edit_text(
        f"📋 <b>Barcha kinolar</b> ({len(movies)} ta):\n\nKinoni tanlang 👇",
        parse_mode="HTML",
        reply_markup=paginate_movies_kb(movies, page=0),
    )


@router.callback_query(F.data.startswith("page:"))
async def cb_paginate(call: CallbackQuery) -> None:
    """Sahifalar orasida harakat qilish."""
    page = int(call.data.split(":")[1])
    movies = await get_all_movies()
    await call.message.edit_reply_markup(
        reply_markup=paginate_movies_kb(movies, page=page)
    )


# ─────────────────────── KINO OLISH (callback) ───────────────────────

@router.callback_query(F.data.startswith("get_movie:"))
async def cb_get_movie(call: CallbackQuery) -> None:
    """Tanlangan kino videosini yuboradi."""
    kino_kodi = int(call.data.split(":")[1])
    movie = await get_movie_by_code(kino_kodi)
    if not movie:
        await call.answer("❌ Kino topilmadi!", show_alert=True)
        return

    await call.message.answer_video(
        video=movie.video_file_id,
        caption=movie_caption(movie),
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(),
    )
    await call.answer()


# ─────────────────────── RAQAM YUBORILGANDA (kod bo'yicha) ───────────────────────

@router.message(F.text.regexp(r"^\d+$"))
async def handle_movie_code(message: Message) -> None:
    """Foydalanuvchi raqam yuborganda bazadan kino qidiradi."""
    kino_kodi = int(message.text.strip())
    movie = await get_movie_by_code(kino_kodi)

    if not movie:
        await message.answer(
            f"😔 <b>{kino_kodi}</b> kodli kino topilmadi.\n\n"
            "Boshqa kod bilan urinib ko'ring.",
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(),
        )
        return

    await message.answer_video(
        video=movie.video_file_id,
        caption=movie_caption(movie),
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(),
    )
