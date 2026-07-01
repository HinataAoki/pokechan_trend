"""Discover new channels/videos via YouTube keyword search (quota-expensive).

Run standalone: `python collector.py`
Meant to run periodically (not necessarily every scheduled run - see
rss_watcher.py for the cheap/frequent path once a channel is known) to
find videos from channels we haven't seen before.
"""

from datetime import datetime, timedelta, timezone

import config
import youtube_client
from video_registrar import register_videos


def collect() -> None:
    published_after = (
        datetime.now(timezone.utc) - timedelta(hours=config.SEARCH_LOOKBACK_HOURS)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    video_ids: set[str] = set()
    for query in config.SEARCH_QUERIES:
        video_ids.update(youtube_client.search_video_ids(query, published_after))

    if not video_ids:
        print("no candidate videos found")
        return

    videos = youtube_client.get_videos_details(list(video_ids))
    print(f"fetched details for {len(videos)} videos")
    register_videos(videos)


if __name__ == "__main__":
    collect()
