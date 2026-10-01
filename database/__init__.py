import importlib.util
from pathlib import Path

# database.py dan barcha funksiyalarni yuklash
_db_py_path = Path(__file__).parent.parent / "database.py"
_spec = importlib.util.spec_from_file_location("root_db_module", str(_db_py_path))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

create_tables = _mod.create_tables
add_movie = _mod.add_movie
get_movie_by_code = _mod.get_movie_by_code
search_movies_by_name = _mod.search_movies_by_name
get_all_movies = _mod.get_all_movies
delete_movie = _mod.delete_movie
get_movies_count = _mod.get_movies_count
add_or_update_user = _mod.add_or_update_user
get_users_count = _mod.get_users_count
get_all_user_ids = _mod.get_all_user_ids

# Sanoq sonlar
get_next_code = _mod.get_next_code
get_next_episode_num = _mod.get_next_episode_num

# Serial va qismlar
add_series = _mod.add_series
update_series_poster = _mod.update_series_poster
get_series_by_code = _mod.get_series_by_code
get_all_series = _mod.get_all_series
get_series_count = _mod.get_series_count
delete_series = _mod.delete_series
add_episode = _mod.add_episode
get_episodes = _mod.get_episodes
get_episode_file_id = _mod.get_episode_file_id
delete_episode = _mod.delete_episode
clear_series_episodes = _mod.clear_series_episodes
close = getattr(_mod, "close", lambda: None)

# Kanallar
add_channel = getattr(_mod, "add_channel", None)
get_all_channels = getattr(_mod, "get_all_channels", None)
delete_channel = getattr(_mod, "delete_channel", None)

__all__ = [
    "create_tables",
    "close",
    "add_movie",
    "get_movie_by_code",
    "search_movies_by_name",
    "get_all_movies",
    "delete_movie",
    "get_movies_count",
    "add_or_update_user",
    "get_users_count",
    "get_all_user_ids",
    "add_series",
    "get_series_by_code",
    "get_all_series",
    "get_series_count",
    "delete_series",
    "add_episode",
    "get_episodes",
    "get_episode_file_id",
    "delete_episode",
    "clear_series_episodes",
    "add_channel",
    "get_all_channels",
    "delete_channel",
]
