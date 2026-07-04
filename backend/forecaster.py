"""Recompute pokemon_daily_forecast from raw videos/snapshots/channels.

Implements the influence-score model documented in docs/influence_model.md
(incremental-view/lag-kernel reach, sublinear scaling, channel subscriber +
skill-tier weighting, #shorts discount, bandwagon effect).

Run standalone: `python forecaster.py`
Meant to run once per scheduled workflow invocation, after snapshotter.py.
Safe to re-run any time (e.g. after tuning forecast_config.py) since it
fully recomputes scores for the calendar window from raw data.
"""

import math
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone

import forecast_config as fc
from supabase_client import get_client, select_all


def _lag_kernel(delta_t_hours: float) -> float:
    """Lognormal kernel: a view converts to a "play" roughly LAG_MU_HOURS
    later. Zero for delta_t <= 0 (a burst can't influence a date before it
    happened)."""
    if delta_t_hours <= 0:
        return 0.0
    x = math.log(delta_t_hours) - math.log(fc.LAG_MU_HOURS)
    return math.exp(-(x * x) / (2 * fc.LAG_SIGMA * fc.LAG_SIGMA))


def _view_increments(snapshots: list[dict]) -> list[tuple[float, float]]:
    """Turn a video's snapshots into [(delta_views, center_hours_since_publish), ...],
    treating the gap between consecutive snapshots (with an implicit 0 views
    at hour 0) as one incremental viewing burst centered at the gap's
    midpoint. A lone "catch-up" snapshot on an old backfilled video (see
    snapshotter.py) becomes one big burst - centered hours are capped at
    MAX_INCREMENT_CENTER_HOURS since we don't know its true accumulation
    curve, only that most videos' views arrive within the first day or two.
    """
    ordered = sorted(snapshots, key=lambda s: s["hours_offset"])
    increments = []
    prev_offset, prev_views = 0.0, 0
    for snap in ordered:
        offset, views = snap["hours_offset"], snap["view_count"]
        delta = views - prev_views
        if delta > 0:
            center = min((prev_offset + offset) / 2, fc.MAX_INCREMENT_CENTER_HOURS)
            increments.append((delta, center))
        prev_offset, prev_views = offset, views
    return increments


def _reach(increments: list[tuple[float, float]], published: datetime, target: datetime) -> float:
    total = 0.0
    for delta_views, center_hours in increments:
        burst_time = published + timedelta(hours=center_hours)
        delta_t_hours = (target - burst_time).total_seconds() / 3600
        total += delta_views * _lag_kernel(delta_t_hours)
    return total


def _channel_weight(subscriber_count: int) -> float:
    return max(1.0, 1.0 + math.log10(max(subscriber_count, 1) / fc.SUBSCRIBER_BASELINE))


def _tier_weight(category: str | None) -> float:
    return fc.TIER_WEIGHTS.get(category, fc.DEFAULT_TIER_WEIGHT)


def _shorts_weight(title: str) -> float:
    return fc.SHORTS_WEIGHT if "#shorts" in title.lower() else 1.0


def forecast() -> None:
    client = get_client()
    now = datetime.now(timezone.utc)
    lookback_start = now - timedelta(days=fc.LOOKBACK_DAYS)

    videos = select_all(
        client,
        "videos",
        "video_id, title, youtube_url, published_at, channel_id",
        lambda q: q.gte("published_at", lookback_start.isoformat()),
    )
    if not videos:
        print("no videos in lookback window")
        return

    video_ids = [v["video_id"] for v in videos]

    pokemon_rows = select_all(
        client, "video_pokemon", "video_id, pokemon_name", lambda q: q.in_("video_id", video_ids)
    )
    pokemon_by_video: dict[str, list[str]] = defaultdict(list)
    for row in pokemon_rows:
        pokemon_by_video[row["video_id"]].append(row["pokemon_name"])

    snapshot_rows = select_all(
        client,
        "view_snapshots",
        "video_id, hours_offset, view_count",
        lambda q: q.in_("video_id", video_ids),
    )
    snapshots_by_video: dict[str, list[dict]] = defaultdict(list)
    for row in snapshot_rows:
        snapshots_by_video[row["video_id"]].append(row)

    channel_ids = list({v["channel_id"] for v in videos})
    channel_rows = select_all(
        client,
        "channels",
        "channel_id, subscriber_count, category",
        lambda q: q.in_("channel_id", channel_ids),
    )
    channel_by_id = {row["channel_id"]: row for row in channel_rows}

    # Calendar window ends at tomorrow and spans CALENDAR_TOTAL_DAYS days back
    # from there (i.e. mostly past days, plus tomorrow as the one forecasted
    # day), in ascending order.
    tomorrow = (now + timedelta(days=1)).date()
    dates = [
        tomorrow - timedelta(days=offset)
        for offset in range(fc.CALENDAR_TOTAL_DAYS - 1, -1, -1)
    ]

    # Pass 1: per-video/date score *before* the bandwagon multiplier (which
    # depends on how many distinct channels used a pokemon on that date -
    # only known once every video has been scored once).
    per_video_date_score: dict[tuple[str, object], float] = {}
    base_scores: dict[tuple, float] = defaultdict(float)
    adopting_channels: dict[tuple, set] = defaultdict(set)

    for video in videos:
        pokemon_names = pokemon_by_video.get(video["video_id"])
        if not pokemon_names:
            continue

        increments = _view_increments(snapshots_by_video.get(video["video_id"], []))
        if not increments:
            continue

        channel = channel_by_id.get(video["channel_id"], {})
        weight = (
            _channel_weight(channel.get("subscriber_count", 0))
            * _tier_weight(channel.get("category"))
            * _shorts_weight(video["title"])
        )
        published = datetime.fromisoformat(video["published_at"].replace("Z", "+00:00"))

        for date in dates:
            target = datetime.combine(date, time(hour=12), tzinfo=timezone.utc)
            reach = _reach(increments, published, target)
            if reach <= 0:
                continue

            score = (reach ** fc.REACH_SUBLINEAR_ALPHA) * weight
            per_video_date_score[(video["video_id"], date)] = score
            for pokemon_name in pokemon_names:
                base_scores[(date, pokemon_name)] += score
                adopting_channels[(date, pokemon_name)].add(video["channel_id"])

    # Pass 2: apply the bandwagon multiplier and build final rows.
    def bandwagon(date, pokemon_name) -> float:
        n_channels = len(adopting_channels[(date, pokemon_name)])
        return 1 + fc.BANDWAGON_BETA * math.log(n_channels) if n_channels > 0 else 1.0

    forecast_rows: dict[tuple, float] = {
        key: score * bandwagon(*key) for key, score in base_scores.items()
    }

    contribution_rows = []
    for video in videos:
        pokemon_names = pokemon_by_video.get(video["video_id"])
        if not pokemon_names:
            continue
        for date in dates:
            base_score = per_video_date_score.get((video["video_id"], date))
            if base_score is None:
                continue
            for pokemon_name in pokemon_names:
                contribution_rows.append(
                    {
                        "date": date.isoformat(),
                        "pokemon_name": pokemon_name,
                        "video_id": video["video_id"],
                        "video_title": video["title"],
                        "youtube_url": video["youtube_url"],
                        "published_at": video["published_at"],
                        "contribution_score": round(base_score * bandwagon(date, pokemon_name), 2),
                    }
                )

    date_strs = [d.isoformat() for d in dates]

    # Fully replace these tables for the computed date window rather than
    # just upserting - otherwise a pokemon/video association that no longer
    # applies (e.g. a corrected match, or a video that dropped out of the
    # lookback window) leaves a stale row behind forever.
    client.table("pokemon_daily_forecast").delete().in_("date", date_strs).execute()
    client.table("pokemon_video_contribution").delete().in_("date", date_strs).execute()

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
        f"replaced {len(rows)} forecast rows and {len(contribution_rows)} "
        f"contribution rows across {len(dates)} dates"
    )


if __name__ == "__main__":
    forecast()
