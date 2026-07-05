"""One-off backfill: search.list over an explicit past date range, day by day.

Unlike collector.py (which only looks back SEARCH_LOOKBACK_HOURS from now),
this walks a fixed window with publishedAfter/publishedBefore pairs so a
whole month of history can be discovered. Each daily window is registered
immediately, so a quota failure mid-run keeps everything fetched so far.

Raw videos().list() items (snippet incl. description/tags, statistics incl.
likeCount/commentCount, contentDetails) are dumped to backend/data/ for every
video in the window - including ones already registered - so engagement
metrics and description-based classification can be added later without
re-spending quota.

Run standalone: `python backfill_period_search.py`
Follow with snapshotter.py (catch-up view snapshots for the new old videos)
and forecaster.py.
"""

import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from googleapiclient.errors import HttpError

import youtube_client
from supabase_client import get_client, select_all
from video_registrar import register_videos

# Only the thin-coverage early stretch is re-searched: from 2026-06-17 on,
# the daily collector was already capturing 20-30 videos/day, and a full
# 32-window sweep (~10.5k units) would blow the 10k/day search quota.
BACKFILL_START = date(2026, 6, 3)
BACKFILL_END = date(2026, 6, 16)  # inclusive
QUERY = "ポケモンチャンピオンズ"
MAX_PAGES_PER_DAY = 4
RAW_DUMP = Path(__file__).parent / "data" / "backfill_20260604_20260704_raw.json"

# Day-window search results are cached here as {"YYYY-MM-DD": [video_id, ...]}
# so a rate-limit/quota abort (or a rerun tomorrow) never re-spends the 100
# units/page already used on a completed window.
SEARCH_CACHE = Path(__file__).parent / "data" / "backfill_search_cache.json"


def _search_window(query: str, after: datetime, before: datetime) -> list[str]:
    youtube = youtube_client.get_youtube()
    video_ids = []
    page_token = None
    for _ in range(MAX_PAGES_PER_DAY):
        response = (
            youtube.search()
            .list(
                part="id",
                q=query,
                type="video",
                order="date",
                publishedAfter=after.strftime("%Y-%m-%dT%H:%M:%SZ"),
                publishedBefore=before.strftime("%Y-%m-%dT%H:%M:%SZ"),
                maxResults=50,
                pageToken=page_token,
            )
            .execute()
        )
        video_ids.extend(item["id"]["videoId"] for item in response.get("items", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return video_ids


def _is_rate_limit(e: HttpError) -> bool:
    return e.resp.status == 429 or (e.resp.status == 403 and b"rateLimitExceeded" in e.content)


def backfill() -> None:
    client = get_client()
    known_ids = {
        row["video_id"]
        for row in select_all(client, "videos", "video_id", lambda q: q)
    }
    print(f"{len(known_ids)} videos already registered")

    cache: dict[str, list[str]] = {}
    if SEARCH_CACHE.exists():
        cache = json.loads(SEARCH_CACHE.read_text(encoding="utf-8"))
        print(f"search cache covers {len(cache)} day windows")

    day = BACKFILL_START
    quota_hit = False
    while day <= BACKFILL_END and not quota_hit:
        key = day.isoformat()
        if key in cache:
            day += timedelta(days=1)
            continue
        after = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
        before = after + timedelta(days=1)
        for attempt in range(3):
            try:
                ids = _search_window(QUERY, after, before)
            except HttpError as e:
                if _is_rate_limit(e) and attempt < 2:
                    print(f"  {day}: rate limited - sleeping 70s (attempt {attempt + 1})")
                    time.sleep(70)
                    continue
                print(f"quota/rate limit exhausted at {day} - processing what was fetched so far")
                quota_hit = True
                break
            cache[key] = ids
            SEARCH_CACHE.write_text(json.dumps(cache), encoding="utf-8")
            print(f"  {day}: {len(ids)} candidates")
            break
        day += timedelta(days=1)

    unique_ids = list(dict.fromkeys(vid for ids in cache.values() for vid in ids))
    print(f"{len(unique_ids)} unique candidates from {len(cache)} day windows")
    if not unique_ids:
        return

    try:
        details = youtube_client.get_videos_details(unique_ids)
    except HttpError as e:
        print(f"videos.list failed ({e.resp.status}) - search cache is saved, rerun later")
        return

    RAW_DUMP.parent.mkdir(exist_ok=True)
    RAW_DUMP.write_text(
        json.dumps(
            {
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "query": QUERY,
                "window": [BACKFILL_START.isoformat(), BACKFILL_END.isoformat()],
                "complete": not quota_hit,
                "videos": details,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"dumped {len(details)} raw video records -> {RAW_DUMP.name}")

    new_details = [d for d in details if d["id"] not in known_ids]
    print(f"{len(new_details)} candidates not yet registered - classifying/registering")
    if new_details:
        register_videos(new_details)


if __name__ == "__main__":
    backfill()
