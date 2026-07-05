"""Quota-free backfill via yt-dlp scraping (no YouTube Data API units).

Discovers candidate videos from the game's hashtag pages plus a date-ordered
search feed, fetches per-video metadata (timestamp, views, likes, comments,
description, tags, channel subscriber count) by scraping the watch page, and
registers anything in the backfill window through the same classify/match/
disambiguate rules as video_registrar.py. The API-based path
(backfill_period_search.py) burned the 10k/day search quota in one run; this
path has no quota at the cost of ~1.5-2s per video.

Per-video metadata is cached to data/scrape_meta_cache.jsonl as it's fetched
(one JSON object per line, including description/tags/like_count/
comment_count for later engagement/video-type work), so an interrupted run
resumes without refetching.

Catch-up view snapshots are inserted directly from the scraped view counts
(same semantics as snapshotter.py's backfill branch) since the videos are
long past the normal tracking window.

Run standalone: `python backfill_scrape.py`, then forecaster.py.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

import config
from llm_classifier import filter_used_pokemon_batch
from pokemon_matcher import match_pokemon
from supabase_client import get_client, select_all
from video_registrar import classify_discovery

WINDOW_START = datetime(2026, 6, 3, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 7, 5, tzinfo=timezone.utc)

# sp=CAI%3D = "sort by upload date" so the feed reaches back through the
# whole backfill window instead of surfacing only algorithmic top hits.
SOURCES = [
    "https://www.youtube.com/hashtag/ポケモンチャンピオンズ",
    "https://www.youtube.com/hashtag/ポケチャン",
    "https://www.youtube.com/results?search_query=ポケモンチャンピオンズ&sp=CAI%3D",
]

META_CACHE = Path(__file__).parent / "data" / "scrape_meta_cache.jsonl"

META_FIELDS = [
    "id", "title", "description", "tags", "timestamp", "upload_date",
    "duration", "view_count", "like_count", "comment_count",
    "channel_id", "channel", "channel_follower_count",
]

FLAT_OPTS = {"quiet": True, "extract_flat": True, "no_warnings": True, "playlistend": 1000}
META_OPTS = {
    "quiet": True,
    "skip_download": True,
    "no_warnings": True,
    "extractor_args": {"youtube": {"player_skip": ["all"]}},
}


def collect_candidate_ids() -> list[str]:
    ids: dict[str, None] = {}
    with YoutubeDL(FLAT_OPTS) as ydl:
        for src in SOURCES:
            try:
                info = ydl.extract_info(src, download=False)
            except DownloadError as e:
                print(f"source failed, skipping: {src} ({e})")
                continue
            entries = info.get("entries") or []
            kept = 0
            for entry in entries:
                video_id = entry.get("id")
                if not video_id:
                    continue
                duration = entry.get("duration")
                if duration is not None and duration <= config.MIN_VIDEO_DURATION_SECONDS:
                    continue
                ids.setdefault(video_id, None)
                kept += 1
            print(f"{src}: {len(entries)} entries, {kept} after duration filter")
    return list(ids)


def fetch_metadata(video_ids: list[str]) -> dict[str, dict]:
    cache: dict[str, dict] = {}
    if META_CACHE.exists():
        with META_CACHE.open(encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line)
                cache[obj["id"]] = obj
        print(f"meta cache has {len(cache)} videos")

    todo = [v for v in video_ids if v not in cache]
    print(f"fetching metadata for {len(todo)} videos (~{len(todo) * 2 // 60} min)")
    with YoutubeDL(META_OPTS) as ydl, META_CACHE.open("a", encoding="utf-8") as out:
        for i, video_id in enumerate(todo):
            try:
                info = ydl.extract_info(
                    f"https://www.youtube.com/watch?v={video_id}", download=False
                )
                slim = {k: info.get(k) for k in META_FIELDS}
            except DownloadError as e:
                slim = {"id": video_id, "_error": str(e)[:200]}
            out.write(json.dumps(slim, ensure_ascii=False) + "\n")
            out.flush()
            cache[video_id] = slim
            if (i + 1) % 25 == 0:
                print(f"  {i + 1}/{len(todo)}")
            time.sleep(0.4)
    return cache


def _published_at(meta: dict) -> datetime | None:
    if meta.get("timestamp"):
        return datetime.fromtimestamp(meta["timestamp"], tz=timezone.utc)
    if meta.get("upload_date"):
        return datetime.strptime(meta["upload_date"], "%Y%m%d").replace(tzinfo=timezone.utc)
    return None


def register_scraped(cache: dict[str, dict], known_ids: set[str]) -> None:
    client = get_client()
    now = datetime.now(timezone.utc)

    candidates = []
    candidates_by_key: dict[str, tuple[str, set[str]]] = {}
    for video_id, meta in cache.items():
        if video_id in known_ids or meta.get("_error"):
            continue
        published = _published_at(meta)
        if published is None or not (WINDOW_START <= published < WINDOW_END):
            continue
        duration = meta.get("duration")
        if duration is not None and duration <= config.MIN_VIDEO_DURATION_SECONDS:
            continue
        title = meta.get("title") or ""
        discovered_via = classify_discovery(
            title, meta.get("description") or "", meta.get("tags") or []
        )
        if discovered_via is None:
            continue
        pokemon_names = match_pokemon(title)
        if not pokemon_names:
            continue
        candidates.append((meta, published, discovered_via))
        candidates_by_key[video_id] = (title, pokemon_names)

    print(f"{len(candidates)} new in-window videos to register")
    if not candidates:
        return

    filtered_by_key = filter_used_pokemon_batch(candidates_by_key)

    channel_rows = {}
    video_rows = []
    video_pokemon_rows = []
    snapshot_rows = []
    for meta, published, discovered_via in candidates:
        video_id = meta["id"]
        channel_rows[meta["channel_id"]] = {
            "channel_id": meta["channel_id"],
            "channel_name": meta.get("channel") or "",
            "subscriber_count": int(meta.get("channel_follower_count") or 0),
        }
        video_rows.append(
            {
                "video_id": video_id,
                "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
                "title": meta.get("title") or "",
                "published_at": published.isoformat(),
                "channel_id": meta["channel_id"],
                "discovered_via": discovered_via,
                "duration_seconds": int(meta["duration"]) if meta.get("duration") else None,
            }
        )
        for pokemon_name in filtered_by_key[video_id]:
            video_pokemon_rows.append({"video_id": video_id, "pokemon_name": pokemon_name})

        age_hours = max(1, round((now - published).total_seconds() / 3600))
        snapshot_rows.append(
            {
                "video_id": video_id,
                "hours_offset": age_hours,
                "view_count": int(meta.get("view_count") or 0),
            }
        )

    client.table("channels").upsert(list(channel_rows.values())).execute()
    client.table("videos").upsert(video_rows).execute()
    if video_pokemon_rows:
        client.table("video_pokemon").upsert(video_pokemon_rows).execute()
    client.table("view_snapshots").upsert(
        snapshot_rows, on_conflict="video_id,hours_offset", ignore_duplicates=True
    ).execute()
    print(
        f"upserted {len(video_rows)} videos, {len(video_pokemon_rows)} video-pokemon links, "
        f"{len(channel_rows)} channels, {len(snapshot_rows)} catch-up snapshots"
    )


def backfill() -> None:
    client = get_client()
    known_ids = {
        row["video_id"] for row in select_all(client, "videos", "video_id")
    }
    print(f"{len(known_ids)} videos already registered")

    candidate_ids = collect_candidate_ids()
    new_ids = [v for v in candidate_ids if v not in known_ids]
    print(f"{len(candidate_ids)} unique candidates, {len(new_ids)} not yet registered")

    cache = fetch_metadata(new_ids)
    register_scraped(cache, known_ids)


if __name__ == "__main__":
    backfill()
