from aiogram.fsm.state import State, StatesGroup


class AddMovieStates(StatesGroup):
    """Admin kino qo'shish uchun FSM holatlari."""
    waiting_video       = State()   # Video yuborish
    waiting_kino_kodi   = State()   # Kino kodi kiritish
    waiting_nomi        = State()   # Kino nomi kiritish
    waiting_janri       = State()   # Janr kiritish
    waiting_tili        = State()   # Til kiritish
    waiting_sifat       = State()   # Sifat kiritish
    confirm             = State()   # Tasdiqlash


class SearchStates(StatesGroup):
    """Foydalanuvchi qidiruv uchun FSM holatlari."""
    waiting_query = State()  # Qidiruv so'zi kutish
