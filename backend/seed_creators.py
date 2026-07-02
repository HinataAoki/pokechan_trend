"""Seed a curated list of known creators (with a skill-tier category) and
backfill their uploads since a given start date.

Run standalone: `python seed_creators.py`
Not part of the scheduled pipeline - this is for deliberately re-focusing
collection on a hand-picked roster of streamers rather than broad keyword
search discovery. Re-run collector.py/rss_watcher.py as usual afterward to
pick up new uploads from these (now-known) channels going forward.
"""

import youtube_client
from supabase_client import get_client
from video_registrar import register_videos

BACKFILL_SINCE = "2026-06-01T00:00:00Z"

# category: light/mid/high/top skill tier - not used in scoring yet, just
# recorded for future use.
CREATORS = [
    {"handle": "mokoustream", "category": "light"},
    {"handle": "bannbee_poke", "category": "mid"},
    {"handle": "Kuroko_965", "category": "mid"},
    {"handle": "raibarori_0318", "category": "mid"},
    {"handle": "shigumapk", "category": "mid"},
    {"handle": "channelzayo", "category": "mid"},
]


def seed() -> None:
    client = get_client()

    channel_rows = []
    for creator in CREATORS:
        channel = youtube_client.get_channel_by_handle(creator["handle"])
        if channel is None:
            print(f"channel not found for handle: @{creator['handle']}")
            continue
        channel_rows.append(
            {
                "channel_id": channel["id"],
                "channel_name": channel["snippet"]["title"],
                "subscriber_count": int(channel["statistics"].get("subscriberCount", 0)),
                "category": creator["category"],
            }
        )

    if not channel_rows:
        print("no channels resolved, aborting")
        return

    client.table("channels").upsert(channel_rows).execute()
    print(f"seeded {len(channel_rows)} channels")
    for row in channel_rows:
        print(f"  [{row['category']}] {row['channel_name']} ({row['channel_id']})")

    all_video_ids: set[str] = set()
    for row in channel_rows:
        video_ids = youtube_client.fetch_channel_video_ids_since(row["channel_id"], BACKFILL_SINCE)
        print(f"{row['channel_name']}: {len(video_ids)} uploads since {BACKFILL_SINCE}")
        all_video_ids.update(video_ids)

    if not all_video_ids:
        print("no videos found across seeded channels")
        return

    videos = youtube_client.get_videos_details(list(all_video_ids))
    print(f"fetched details for {len(videos)} videos")
    register_videos(videos)


if __name__ == "__main__":
    seed()
