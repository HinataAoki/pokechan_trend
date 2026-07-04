"""Take due view-count snapshots for videos still within the tracking window,
plus a one-off "catch-up" snapshot for older/backfilled videos that were
never tracked (e.g. seed_creators.py backfilling a month of history) so
they still have a view count to contribute to the forecast.

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

    videos_resp = client.table("videos").select("video_id, published_at").execute()
    videos = videos_resp.data
    if not videos:
        print("no videos tracked yet")
        return

    existing_resp = client.table("view_snapshots").select("video_id, hours_offset").execute()
    already_captured = {(row["video_id"], row["hours_offset"]) for row in existing_resp.data}
    videos_with_any_snapshot = {video_id for video_id, _ in already_captured}

    due_map: dict[str, list[int]] = {}
    for video in videos:
        elapsed = _hours_since(video["published_at"])
        video_id = video["video_id"]

        if elapsed <= config.MAX_TRACKING_HOURS:
            due_offsets = [
                offset
                for offset in config.SNAPSHOT_OFFSETS_HOURS
                if elapsed >= offset and (video_id, offset) not in already_captured
            ]
            if due_offsets:
                due_map[video_id] = due_offsets
        elif video_id not in videos_with_any_snapshot:
            # Backfilled video, already past the normal tracking window and
            # never snapshotted - take one catch-up reading now, recorded
            # under its actual current age, rather than leaving it with no
            # view count (and thus no forecast contribution) forever.
            due_map[video_id] = [round(elapsed)]

    if not due_map:
        print("no snapshots due")
        return

    details = youtube_client.get_videos_details(list(due_map.keys()))
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

    # Refresh subscriber counts for the channels of videos snapshotted this run.
    channel_ids_resp = (
        client.table("videos").select("channel_id").in_("video_id", list(due_map.keys())).execute()
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

    print(f"inserted {len(snapshot_rows)} snapshots across {len(due_map)} videos")


if __name__ == "__main__":
    snapshot()
