from dataclasses import dataclass
from typing import Optional


@dataclass
class Movie:
    """Kino ma'lumotlari modeli."""
    id: int
    kino_kodi: int
    nomi: str
    janri: str
    tili: str
    sifat: str
    video_file_id: str
    qoshilgan_vaqt: Optional[str] = None


@dataclass
class User:
    """Foydalanuvchi ma'lumotlari modeli."""
    id: int
    user_id: int
    full_name: Optional[str]
    username: Optional[str]
    qoshilgan_vaqt: Optional[str] = None
