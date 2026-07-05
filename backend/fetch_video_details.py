"""Fetch full snippet (description/tags) + statistics for every registered
video via videos.list (1 unit per 50 videos - negligible quota) and cache to
data/api_video_details.jsonl. Input material for video-type classification
(classify_video_types.py) and, later, engagement-based factors.

Run standalone: `python fetch_video_details.py`
Safe to re-run: refetches everything and rewrites the cache (view/like counts
go stale, and refetching is nearly free).
"""

import json
from pathlib import Path

import youtube_client
from supabase_client import get_client, select_all

OUT = Path(__file__).parent / "data" / "api_video_details.jsonl"


def fetch() -> None:
    client = get_client()
    video_ids = [
        row["video_id"] for row in select_all(client, "videos", "video_id")
    ]
    print(f"fetching details for {len(video_ids)} registered videos")

    details = youtube_client.get_videos_details(video_ids)
    with OUT.open("w", encoding="utf-8") as f:
        for d in details:
            snippet = d.get("snippet", {})
            stats = d.get("statistics", {})
            slim = {
                "id": d["id"],
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "tags": snippet.get("tags", []),
                "published_at": snippet.get("publishedAt"),
                "channel_id": snippet.get("channelId"),
                "view_count": int(stats.get("viewCount", 0)),
                "like_count": int(stats["likeCount"]) if "likeCount" in stats else None,
                "comment_count": int(stats["commentCount"]) if "commentCount" in stats else None,
            }
            f.write(json.dumps(slim, ensure_ascii=False) + "\n")
    print(f"wrote {len(details)} records -> {OUT.name}")


if __name__ == "__main__":
    fetch()
