"""Discover new videos by scraping YouTube's hashtag pages and date-sorted
search results with yt-dlp - no search.list quota (search.list costs 100
units/call; this costs zero API units and a few HTTP requests).

Only *discovery* is scraped: details for candidate videos still come from
the API's videos.list (1 unit per 50 videos), so register_videos() receives
the exact same input shape as the collector.py path and every downstream
rule (duration filter, relevance classification, pokemon matching, type
classification) stays identical.

collector.py (API keyword search) remains as a lower-frequency safety net
in the workflow since the scraped feeds and search.list have different
recall characteristics.

Run standalone: `python scrape_collector.py`
"""

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

import config
import youtube_client
from supabase_client import get_client, select_all
from video_registrar import register_videos

# sp=CAI%3D = "sort by upload date" so new uploads surface immediately.
SOURCES = [
    "https://www.youtube.com/hashtag/ポケモンチャンピオンズ",
    "https://www.youtube.com/hashtag/ポケチャン",
    "https://www.youtube.com/results?search_query=ポケモンチャンピオンズ&sp=CAI%3D",
]

# Recent slice only - this runs hourly, so anything new is near the top of
# each feed. backfill_scrape.py is the deep-history variant.
FLAT_OPTS = {"quiet": True, "extract_flat": True, "no_warnings": True, "playlistend": 120}


def collect() -> None:
    client = get_client()
    known_ids = {row["video_id"] for row in select_all(client, "videos", "video_id")}

    candidate_ids: dict[str, None] = {}
    with YoutubeDL(FLAT_OPTS) as ydl:
        for src in SOURCES:
            try:
                info = ydl.extract_info(src, download=False)
            except DownloadError as e:
                print(f"source failed, skipping: {src} ({e})")
                continue
            for entry in info.get("entries") or []:
                video_id = entry.get("id")
                if not video_id or video_id in known_ids:
                    continue
                duration = entry.get("duration")
                if duration is not None and duration <= config.MIN_VIDEO_DURATION_SECONDS:
                    continue
                candidate_ids.setdefault(video_id, None)

    if not candidate_ids:
        print("no new candidate videos found")
        return

    print(f"{len(candidate_ids)} new candidates discovered via scraping")
    videos = youtube_client.get_videos_details(list(candidate_ids))
    register_videos(videos)


if __name__ == "__main__":
    collect()
