from aiogram import Router, F
from aiogram.filters import Filter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS
from database import (
    add_movie,
    delete_movie,
    get_movies_count,
    get_users_count,
    get_all_movies,
    get_movie_by_code,
)
from keyboards import (
    admin_panel_kb,
    back_to_admin_kb,
    back_to_menu_kb,
    confirm_kb,
    paginate_movies_kb,
)
from utils.states import AddMovieStates
from utils.helpers import stats_text, movie_caption

router = Router()


# ─────────────────────── ADMIN FILTRI ───────────────────────

class IsAdmin(Filter):
    """Faqat adminlarga ruxsat beruvchi filtr."""
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id if event.from_user else 0
        return user_id in ADMIN_IDS


# Barcha router'dagi handlerlar uchun admin filtrini qo'shish
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# ─────────────────────── ADMIN PANEL ───────────────────────

@router.callback_query(F.data == "admin_panel")
async def cb_admin_panel(call: CallbackQuery) -> None:
    """Admin panel menyusini ko'rsatadi."""
    await call.message.edit_text(
        "⚙️ <b>Admin Panel</b>\n\nNimani amalga oshirmoqchisiz?",
        parse_mode="HTML",
        reply_markup=admin_panel_kb(),
    )


# ─────────────────────── STATISTIKA ───────────────────────

@router.callback_query(F.data == "statistics")
async def cb_statistics(call: CallbackQuery) -> None:
    """Bot statistikasini ko'rsatadi."""
    movies_count = await get_movies_count()
    users_count  = await get_users_count()
    await call.message.edit_text(
        stats_text(movies_count, users_count),
        parse_mode="HTML",
        reply_markup=back_to_admin_kb(),
    )


# ─────────────────────── KINOLAR RO'YXATI (ADMIN) ───────────────────────

@router.callback_query(F.data == "movie_list_admin")
async def cb_movie_list_admin(call: CallbackQuery) -> None:
    """Admin uchun kinolar ro'yxati."""
    movies = await get_all_movies()
    if not movies:
        await call.message.edit_text(
            "📭 Bazada hali kino yo'q.",
            reply_markup=back_to_admin_kb(),
        )
        return
    await call.message.edit_text(
        f"📋 <b>Barcha kinolar</b> ({len(movies)} ta):",
        parse_mode="HTML",
        reply_markup=paginate_movies_kb(movies, page=0),
    )


# ─────────────────────── KINO QO'SHISH — FSM ───────────────────────

@router.callback_query(F.data == "add_movie")
async def cb_add_movie_start(call: CallbackQuery, state: FSMContext) -> None:
    """Kino qo'shish jarayonini boshlaydi."""
    await state.set_state(AddMovieStates.waiting_video)
    await call.message.edit_text(
        "🎬 <b>Yangi kino qo'shish</b>\n\n"
        "<b>1-qadam:</b> Kino videosini yuboring 👇\n\n"
        "<i>Bekor qilish uchun /cancel yozing</i>",
        parse_mode="HTML",
    )


@router.message(AddMovieStates.waiting_video, F.video)
async def fsm_get_video(message: Message, state: FSMContext) -> None:
    """Video file_id saqlanadi."""
    await state.update_data(video_file_id=message.video.file_id)
    await state.set_state(AddMovieStates.waiting_kino_kodi)
    await message.answer(
        "✅ Video qabul qilindi!\n\n"
        "<b>2-qadam:</b> Kino kodini kiriting (faqat raqam):\n"
        "<i>Misol: 101</i>",
        parse_mode="HTML",
    )


@router.message(AddMovieStates.waiting_video)
async def fsm_video_wrong(message: Message) -> None:
    """Video o'rniga boshqa narsa yuborilsa."""
    await message.answer("❌ Iltimos, faqat <b>video</b> yuboring!", parse_mode="HTML")


@router.message(AddMovieStates.waiting_kino_kodi)
async def fsm_get_kino_kodi(message: Message, state: FSMContext) -> None:
    """Kino kodini qabul qiladi."""
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("❌ Kod faqat <b>raqam</b> bo'lishi kerak!", parse_mode="HTML")
        return
    await state.update_data(kino_kodi=int(text))
    await state.set_state(AddMovieStates.waiting_nomi)
    await message.answer(
        "<b>3-qadam:</b> Kino nomini kiriting:\n<i>Misol: Avengers: Endgame</i>",
        parse_mode="HTML",
    )


@router.message(AddMovieStates.waiting_nomi)
async def fsm_get_nomi(message: Message, state: FSMContext) -> None:
    """Kino nomini qabul qiladi."""
    await state.update_data(nomi=message.text.strip())
    await state.set_state(AddMovieStates.waiting_janri)
    await message.answer(
        "<b>4-qadam:</b> Janrini kiriting:\n"
        "<i>Misol: Jangari, Komediya, Drama, Fantastika ...</i>",
        parse_mode="HTML",
    )


@router.message(AddMovieStates.waiting_janri)
async def fsm_get_janri(message: Message, state: FSMContext) -> None:
    """Janrini qabul qiladi."""
    await state.update_data(janri=message.text.strip())
    await state.set_state(AddMovieStates.waiting_tili)
    await message.answer(
        "<b>5-qadam:</b> Tilini kiriting:\n"
        "<i>Misol: O'zbek, Rus, Ingliz ...</i>",
        parse_mode="HTML",
    )


@router.message(AddMovieStates.waiting_tili)
async def fsm_get_tili(message: Message, state: FSMContext) -> None:
    """Tilni qabul qiladi."""
    await state.update_data(tili=message.text.strip())
    await state.set_state(AddMovieStates.waiting_sifat)
    await message.answer(
        "<b>6-qadam:</b> Sifatini kiriting:\n"
        "<i>Misol: 480p, 720p, 1080p ...</i>",
        parse_mode="HTML",
    )


@router.message(AddMovieStates.waiting_sifat)
async def fsm_get_sifat(message: Message, state: FSMContext) -> None:
    """Sifatni qabul qiladi va tasdiqlash so'raydi."""
    await state.update_data(sifat=message.text.strip())
    data = await state.get_data()

    await state.set_state(AddMovieStates.confirm)
    await message.answer(
        f"📋 <b>Ma'lumotlarni tekshiring:</b>\n\n"
        f"🔢 Kod:    <code>{data['kino_kodi']}</code>\n"
        f"🎬 Nomi:   <b>{data['nomi']}</b>\n"
        f"🎭 Janr:   {data['janri']}\n"
        f"🌍 Til:    {data['tili']}\n"
        f"📺 Sifat:  {data['sifat']}\n\n"
        f"To'g'rimi?",
        parse_mode="HTML",
        reply_markup=confirm_kb(),
    )


@router.callback_query(AddMovieStates.confirm, F.data == "confirm_save")
async def fsm_confirm_save(call: CallbackQuery, state: FSMContext) -> None:
    """Kino bazaga saqlanadi."""
    data = await state.get_data()
    await state.clear()

    success = await add_movie(
        kino_kodi=data["kino_kodi"],
        nomi=data["nomi"],
        janri=data["janri"],
        tili=data["tili"],
        sifat=data["sifat"],
        video_file_id=data["video_file_id"],
    )

    if success:
        await call.message.edit_text(
            f"✅ <b>{data['nomi']}</b> muvaffaqiyatli qo'shildi!\n"
            f"📌 Kino kodi: <code>{data['kino_kodi']}</code>",
            parse_mode="HTML",
            reply_markup=back_to_admin_kb(),
        )
    else:
        await call.message.edit_text(
            f"❌ <b>{data['kino_kodi']}</b> kodli kino allaqachon mavjud!\n"
            "Boshqa kod bilan qayta urinib ko'ring.",
            parse_mode="HTML",
            reply_markup=back_to_admin_kb(),
        )


@router.callback_query(F.data == "cancel_add")
async def cb_cancel_add(call: CallbackQuery, state: FSMContext) -> None:
    """Kino qo'shishni bekor qiladi."""
    await state.clear()
    await call.message.edit_text(
        "❌ Bekor qilindi.",
        reply_markup=back_to_admin_kb(),
    )


@router.message(F.text == "/cancel")
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """/cancel — joriy holatni bekor qiladi."""
    current = await state.get_state()
    if current is None:
        await message.answer("Hech qanday faol jarayon yo'q.")
        return
    await state.clear()
    await message.answer("❌ Bekor qilindi.", reply_markup=back_to_admin_kb())


# ─────────────────────── KINO O'CHIRISH ───────────────────────

@router.callback_query(F.data == "delete_movie")
async def cb_delete_movie_prompt(call: CallbackQuery) -> None:
    """Kino o'chirishdan oldin kod so'raydi."""
    await call.message.edit_text(
        "🗑️ <b>Kino o'chirish</b>\n\n"
        "O'chirmoqchi bo'lgan kinoning kodini yuboring:",
        parse_mode="HTML",
        reply_markup=back_to_admin_kb(),
    )


@router.message(F.text.regexp(r"^del:(\d+)$"))
async def handle_delete_by_code(message: Message) -> None:
    """del:KOD formatida kino o'chiradi."""
    kino_kodi = int(message.text.split(":")[1])
    success = await delete_movie(kino_kodi)
    if success:
        await message.answer(
            f"✅ <b>{kino_kodi}</b> kodli kino o'chirildi.",
            parse_mode="HTML",
            reply_markup=back_to_admin_kb(),
        )
    else:
        await message.answer(
            f"❌ <b>{kino_kodi}</b> kodli kino topilmadi.",
            parse_mode="HTML",
            reply_markup=back_to_admin_kb(),
        )
