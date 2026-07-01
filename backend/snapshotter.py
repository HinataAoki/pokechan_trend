"""Take due view-count snapshots for videos still within the tracking window.

Run standalone: `python snapshotter.py`
Meant to run once per scheduled workflow invocation, after collector.py.
"""

from datetime import datetime, timezone

import config
import youtube_client
from supabase_client import get_client


def _hours_since(published_at: str) -> float:
    published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - published).total_seconds() / 3600


def snapshot() -> None:
    client = get_client()

    videos_resp = (
        client.table("videos")
        .select("video_id, published_at")
        .execute()
    )
    videos = videos_resp.data
    if not videos:
        print("no videos tracked yet")
        return

    tracked = [v for v in videos if _hours_since(v["published_at"]) <= config.MAX_TRACKING_HOURS]
    if not tracked:
        print("no videos within tracking window")
        return

    existing_resp = (
        client.table("view_snapshots")
        .select("video_id, hours_offset")
        .in_("video_id", [v["video_id"] for v in tracked])
        .execute()
    )
    already_captured = {(row["video_id"], row["hours_offset"]) for row in existing_resp.data}

    due_video_ids = []
    due_map: dict[str, list[int]] = {}
    for video in tracked:
        elapsed = _hours_since(video["published_at"])
        due_offsets = [
            offset
            for offset in config.SNAPSHOT_OFFSETS_HOURS
            if elapsed >= offset and (video["video_id"], offset) not in already_captured
        ]
        if due_offsets:
            due_video_ids.append(video["video_id"])
            due_map[video["video_id"]] = due_offsets

    if not due_video_ids:
        print("no snapshots due")
        return

    details = youtube_client.get_videos_details(due_video_ids)
    stats_by_id = {d["id"]: int(d["statistics"].get("viewCount", 0)) for d in details}

    snapshot_rows = []
    for video_id, offsets in due_map.items():
        view_count = stats_by_id.get(video_id)
        if view_count is None:
            continue  # video may have been deleted/made private since discovery
        for offset in offsets:
            snapshot_rows.append(
                {
                    "video_id": video_id,
                    "hours_offset": offset,
                    "view_count": view_count,
                }
            )

    if snapshot_rows:
        client.table("view_snapshots").upsert(snapshot_rows).execute()

    # Refresh subscriber counts for tracked videos' channels while we're at it.
    channel_ids_resp = (
        client.table("videos")
        .select("channel_id")
        .in_("video_id", due_video_ids)
        .execute()
    )
    channel_ids = [row["channel_id"] for row in channel_ids_resp.data]
    if channel_ids:
        channels = youtube_client.get_channels_details(channel_ids)
        channel_rows = [
            {
                "channel_id": ch["id"],
                "channel_name": ch["snippet"]["title"],
                "subscriber_count": int(ch["statistics"].get("subscriberCount", 0)),
            }
            for ch in channels
        ]
        client.table("channels").upsert(channel_rows).execute()

    print(f"inserted {len(snapshot_rows)} snapshots across {len(due_video_ids)} videos")


if __name__ == "__main__":
    snapshot()
