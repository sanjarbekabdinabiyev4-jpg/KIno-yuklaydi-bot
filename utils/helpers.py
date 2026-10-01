from database.schemas import Movie


def movie_caption(movie: Movie) -> str:
    """Kino uchun chiroyli izoh matni yaratadi."""
    return (
        f"🎬 <b>{movie.nomi}</b>\n\n"
        f"🔢 <b>Kod:</b> <code>{movie.kino_kodi}</code>\n"
        f"🎭 <b>Janr:</b> {movie.janri}\n"
        f"🌍 <b>Til:</b> {movie.tili}\n"
        f"📺 <b>Sifat:</b> {movie.sifat}\n\n"
        f"📥 <i>Yuklab olish uchun videoni saqlang.</i>"
    )


def movie_short_info(movie: Movie) -> str:
    """Qisqa ma'lumot (ro'yxat uchun)."""
    return f"🎬 [{movie.kino_kodi}] {movie.nomi} — {movie.janri} | {movie.sifat}"


def stats_text(movies_count: int, users_count: int) -> str:
    """Statistika xabari."""
    return (
        f"📊 <b>Bot Statistikasi</b>\n\n"
        f"🎬 Kinolar soni:      <b>{movies_count}</b>\n"
        f"👥 Foydalanuvchilar: <b>{users_count}</b>"
    )
