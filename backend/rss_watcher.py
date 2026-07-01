"""Cheaply discover new uploads from already-known channels via YouTube's
free per-channel RSS feed (no API quota), instead of re-running expensive
search.list queries every scheduled run.

Run standalone: `python rss_watcher.py`
Meant to run every scheduled invocation; collector.py (search.list-based,
quota-expensive) only needs to run occasionally to find brand-new channels -
once a channel is known, this script picks up its future uploads for free.
"""

import urllib.request
import xml.etree.ElementTree as ET

import youtube_client
from supabase_client import get_client
from video_registrar import register_videos

FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
USER_AGENT = "pokechan-trend/1.0 (+https://github.com/HinataAoki/pokechan_trend)"
ATOM_NS = "{http://www.w3.org/2005/Atom}"
YT_NS = "{http://www.youtube.com/xml/schemas/2015}"


def _fetch_channel_video_ids(channel_id: str) -> list[str]:
    req = urllib.request.Request(
        FEED_URL.format(channel_id=channel_id), headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(req) as resp:
            root = ET.fromstring(resp.read())
    except Exception as e:
        print(f"failed to fetch/parse RSS feed for channel {channel_id}: {e}")
        return []

    return [
        video_id_el.text
        for entry in root.findall(f"{ATOM_NS}entry")
        if (video_id_el := entry.find(f"{YT_NS}videoId")) is not None
    ]


def watch() -> None:
    client = get_client()

    channel_ids = [row["channel_id"] for row in client.table("channels").select("channel_id").execute().data]
    if not channel_ids:
        print("no known channels yet - run collector.py first")
        return

    existing_video_ids = {
        row["video_id"] for row in client.table("videos").select("video_id").execute().data
    }

    new_video_ids: set[str] = set()
    for channel_id in channel_ids:
        for video_id in _fetch_channel_video_ids(channel_id):
            if video_id not in existing_video_ids:
                new_video_ids.add(video_id)

    print(f"checked {len(channel_ids)} known channels via RSS, found {len(new_video_ids)} new video(s)")
    if not new_video_ids:
        return

    videos = youtube_client.get_videos_details(list(new_video_ids))
    register_videos(videos)


if __name__ == "__main__":
    watch()
