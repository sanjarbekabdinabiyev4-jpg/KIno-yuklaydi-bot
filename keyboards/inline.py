from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ─────────────────────── ASOSIY MENYU ───────────────────────

def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Asosiy menyu inline klaviaturasi."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🔍 Nom bo'yicha qidirish", callback_data="search_by_name"),
        InlineKeyboardButton(text="🔢 Kod bo'yicha qidirish", callback_data="search_by_code"),
    )
    builder.row(
        InlineKeyboardButton(text="📋 Barcha kinolar", callback_data="all_movies"),
    )
    if is_admin:
        builder.row(
            InlineKeyboardButton(text="⚙️ Admin Panel", callback_data="admin_panel"),
        )

    return builder.as_markup()


# ─────────────────────── ADMIN PANEL ───────────────────────

def admin_panel_kb() -> InlineKeyboardMarkup:
    """Admin panel klaviaturasi."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="➕ Kino qo'shish", callback_data="add_movie"),
        InlineKeyboardButton(text="📊 Statistika",    callback_data="statistics"),
    )
    builder.row(
        InlineKeyboardButton(text="🗑️ Kino o'chirish", callback_data="delete_movie"),
        InlineKeyboardButton(text="📋 Kinolar ro'yxati", callback_data="movie_list_admin"),
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu"),
    )

    return builder.as_markup()


# ─────────────────────── ORQAGA TUGMASI ───────────────────────

def back_to_menu_kb() -> InlineKeyboardMarkup:
    """Bosh menyuga qaytish tugmasi."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu"),
    )
    return builder.as_markup()


def back_to_admin_kb() -> InlineKeyboardMarkup:
    """Admin panelga qaytish tugmasi."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Admin panel", callback_data="admin_panel"),
        InlineKeyboardButton(text="🏠 Bosh menyu",  callback_data="main_menu"),
    )
    return builder.as_markup()


# ─────────────────────── TASDIQLASH ───────────────────────

def confirm_kb() -> InlineKeyboardMarkup:
    """Tasdiqlash / bekor qilish tugmalari."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Saqlash",     callback_data="confirm_save"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_add"),
    )
    return builder.as_markup()


# ─────────────────────── QIDIRUV NATIJALARI ───────────────────────

def movie_results_kb(movie_codes: list[int]) -> InlineKeyboardMarkup:
    """Qidiruv natijalarida har bir kinoga tugma."""
    builder = InlineKeyboardBuilder()
    for code in movie_codes:
        builder.row(
            InlineKeyboardButton(
                text=f"🎬 Kod: {code}",
                callback_data=f"get_movie:{code}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu"),
    )
    return builder.as_markup()


# ─────────────────────── SAHIFALASH ───────────────────────

def paginate_movies_kb(
    movies: list,
    page: int = 0,
    per_page: int = 8,
) -> InlineKeyboardMarkup:
    """Kinolar ro'yxatini sahifalab ko'rsatish."""
    builder = InlineKeyboardBuilder()
    start = page * per_page
    end   = start + per_page
    chunk = movies[start:end]

    for movie in chunk:
        builder.row(
            InlineKeyboardButton(
                text=f"🎬 [{movie.kino_kodi}] {movie.nomi}",
                callback_data=f"get_movie:{movie.kino_kodi}",
            )
        )

    nav_buttons: list[InlineKeyboardButton] = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="◀️", callback_data=f"page:{page - 1}")
        )
    if end < len(movies):
        nav_buttons.append(
            InlineKeyboardButton(text="▶️", callback_data=f"page:{page + 1}")
        )
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(
        InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu"),
    )
    return builder.as_markup()
