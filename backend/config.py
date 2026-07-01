import os

from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

# Used to disambiguate which Pokemon a title is actually "about" when more
# than one name is matched (e.g. one used, one merely mentioned as an
# opponent/counter/comparison) - see llm_classifier.py.
GEMINI_MODEL = "gemini-3.1-flash-lite"

# Search terms used to discover candidate videos via YouTube search.list.
SEARCH_QUERIES = [
    "ポケモンチャンピオンズ",
    "Pokémon Champions",
    "Pokemon Champions",
]

# Hashtags/keywords checked against title, description and tags.
HASHTAGS = ["#ポケチャン", "#ポケモンチャンピオンズ"]
TITLE_KEYWORDS = ["ポケモンチャンピオンズ", "ポケチャン"]
GAME_TITLE_KEYWORDS = ["Pokémon Champions", "Pokemon Champions"]

# Videos this short or shorter are excluded entirely (typically low-effort
# clips/#shorts reposts that don't represent a real "use" of a Pokemon).
MIN_VIDEO_DURATION_SECONDS = 180

# Only videos still within this many hours of publication are tracked for snapshots.
MAX_TRACKING_HOURS = 144
SNAPSHOT_OFFSETS_HOURS = [24, 48, 72, 96, 108, 120, 144]

# How far back to search for candidate videos each run. Should comfortably
# exceed the scheduled run interval so a slow/missed run doesn't lose videos,
# while staying within MAX_TRACKING_HOURS since older videos can't be
# meaningfully snapshotted anyway.
SEARCH_LOOKBACK_HOURS = MAX_TRACKING_HOURS
