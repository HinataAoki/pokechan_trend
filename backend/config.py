import os

from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

# Search terms used to discover candidate videos via YouTube search.list.
SEARCH_QUERIES = [
    "ポケモンチャンピオンズ",
    "Pokémon Champions",
    "Pokemon Champions",
]

# Hashtags/keywords checked against title, description and tags.
HASHTAGS = ["#ポケチャン", "#ポケモンチャンピオンズ"]
TITLE_KEYWORDS = ["ポケモンチャンピオンズ"]
GAME_TITLE_KEYWORDS = ["Pokémon Champions", "Pokemon Champions"]

# Only videos still within this many hours of publication are tracked for snapshots.
MAX_TRACKING_HOURS = 144
SNAPSHOT_OFFSETS_HOURS = [24, 48, 72, 96, 108, 120, 144]
