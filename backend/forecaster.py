"""Recompute pokemon_daily_forecast from raw videos/snapshots/channels.

Run standalone: `python forecaster.py`
Meant to run once per scheduled workflow invocation, after snapshotter.py.
Safe to re-run any time (e.g. after tuning forecast_config.py) since it
fully recomputes scores for the lookback/horizon window from raw data.
"""

import math
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone

import forecast_config as fc
from supabase_client import get_client


def _decay(hours_elapsed: float) -> float:
    if hours_elapsed < 0:
        return 0.0
    return 1.0 - math.tanh(hours_elapsed / fc.TAU_HOURS)


def _channel_weight(subscriber_count: int) -> float:
    return max(1.0, 1.0 + math.log10(max(subscriber_count, 1) / fc.SUBSCRIBER_BASELINE))


def _latest_view_count(snapshots: list[dict]) -> int | None:
    if not snapshots:
        return None
    return max(snapshots, key=lambda s: s["hours_offset"])["view_count"]


def forecast() -> None:
    client = get_client()
    now = datetime.now(timezone.utc)
    lookback_start = now - timedelta(days=fc.LOOKBACK_DAYS)

    videos_resp = (
        client.table("videos")
        .select("video_id, title, youtube_url, published_at, channel_id")
        .gte("published_at", lookback_start.isoformat())
        .execute()
    )
    videos = videos_resp.data
    if not videos:
        print("no videos in lookback window")
        return

    video_ids = [v["video_id"] for v in videos]

    pokemon_resp = (
        client.table("video_pokemon")
        .select("video_id, pokemon_name")
        .in_("video_id", video_ids)
        .execute()
    )
    pokemon_by_video: dict[str, list[str]] = defaultdict(list)
    for row in pokemon_resp.data:
        pokemon_by_video[row["video_id"]].append(row["pokemon_name"])

    snapshots_resp = (
        client.table("view_snapshots")
        .select("video_id, hours_offset, view_count")
        .in_("video_id", video_ids)
        .execute()
    )
    snapshots_by_video: dict[str, list[dict]] = defaultdict(list)
    for row in snapshots_resp.data:
        snapshots_by_video[row["video_id"]].append(row)

    channel_ids = list({v["channel_id"] for v in videos})
    channels_resp = (
        client.table("channels")
        .select("channel_id, subscriber_count")
        .in_("channel_id", channel_ids)
        .execute()
    )
    subscribers_by_channel = {
        row["channel_id"]: row["subscriber_count"] for row in channels_resp.data
    }

    dates = [
        (now + timedelta(days=offset)).date()
        for offset in range(fc.FORECAST_HORIZON_DAYS + 1)
    ]

    forecast_rows: dict[tuple, float] = defaultdict(float)
    contribution_rows = []
    for video in videos:
        pokemon_names = pokemon_by_video.get(video["video_id"])
        if not pokemon_names:
            continue

        view_count = _latest_view_count(snapshots_by_video.get(video["video_id"], []))
        if view_count is None:
            continue

        subscriber_count = subscribers_by_channel.get(video["channel_id"], 0)
        weight = _channel_weight(subscriber_count)
        published = datetime.fromisoformat(video["published_at"].replace("Z", "+00:00"))

        for date in dates:
            target = datetime.combine(date, time(hour=12), tzinfo=timezone.utc)
            elapsed_hours = (target - published).total_seconds() / 3600
            score = view_count * _decay(elapsed_hours) * weight
            if score <= 0:
                continue
            for pokemon_name in pokemon_names:
                forecast_rows[(date, pokemon_name)] += score
                contribution_rows.append(
                    {
                        "date": date.isoformat(),
                        "pokemon_name": pokemon_name,
                        "video_id": video["video_id"],
                        "video_title": video["title"],
                        "youtube_url": video["youtube_url"],
                        "published_at": video["published_at"],
                        "contribution_score": round(score, 2),
                    }
                )

    if not forecast_rows:
        print("no forecast rows computed")
        return

    rows = [
        {"date": date.isoformat(), "pokemon_name": pokemon_name, "score": round(score, 2)}
        for (date, pokemon_name), score in forecast_rows.items()
    ]
    client.table("pokemon_daily_forecast").upsert(rows).execute()
    client.table("pokemon_video_contribution").upsert(contribution_rows).execute()
    print(
        f"upserted {len(rows)} forecast rows and {len(contribution_rows)} "
        f"contribution rows across {len(dates)} dates"
    )


if __name__ == "__main__":
    forecast()
