"""Discover candidate videos and register them + their Pokemon into Supabase.

Run standalone: `python collector.py`
Meant to run once per scheduled workflow invocation, before snapshotter.py.
"""

import config
import youtube_client
from pokemon_matcher import match_pokemon
from supabase_client import get_client


def _classify_discovery(title: str, description: str, tags: list[str]) -> str | None:
    haystack_title = title or ""
    haystack_rest = "\n".join([description or "", "\n".join(tags or [])])

    if any(kw in haystack_title for kw in config.TITLE_KEYWORDS):
        return "title_keyword"
    if any(tag in haystack_rest for tag in config.HASHTAGS):
        return "hashtag"
    if any(kw in haystack_title or kw in haystack_rest for kw in config.GAME_TITLE_KEYWORDS):
        return "game_title"
    return None


def collect() -> None:
    client = get_client()

    video_ids: set[str] = set()
    for query in config.SEARCH_QUERIES:
        video_ids.update(youtube_client.search_video_ids(query))

    if not video_ids:
        print("no candidate videos found")
        return

    videos = youtube_client.get_videos_details(list(video_ids))
    print(f"fetched details for {len(videos)} videos")

    relevant_videos = []
    for video in videos:
        snippet = video["snippet"]
        title = snippet.get("title", "")
        description = snippet.get("description", "")
        tags = snippet.get("tags", [])

        discovered_via = _classify_discovery(title, description, tags)
        if discovered_via is None:
            continue  # search hit was noise, not actually about this game

        relevant_videos.append((video, discovered_via))

    if not relevant_videos:
        print("no relevant videos after keyword/hashtag filtering")
        return

    channel_ids = [v["snippet"]["channelId"] for v, _ in relevant_videos]
    channels = youtube_client.get_channels_details(channel_ids)

    channel_rows = [
        {
            "channel_id": ch["id"],
            "channel_name": ch["snippet"]["title"],
            "subscriber_count": int(ch["statistics"].get("subscriberCount", 0)),
        }
        for ch in channels
    ]
    if channel_rows:
        client.table("channels").upsert(channel_rows).execute()

    video_rows = []
    video_pokemon_rows = []
    for video, discovered_via in relevant_videos:
        snippet = video["snippet"]
        video_id = video["id"]
        title = snippet.get("title", "")
        description = snippet.get("description", "")
        tags = snippet.get("tags", [])

        video_rows.append(
            {
                "video_id": video_id,
                "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
                "title": title,
                "published_at": snippet["publishedAt"],
                "channel_id": snippet["channelId"],
                "discovered_via": discovered_via,
            }
        )

        for pokemon_name in match_pokemon(title, description, "\n".join(tags)):
            video_pokemon_rows.append({"video_id": video_id, "pokemon_name": pokemon_name})

    if video_rows:
        client.table("videos").upsert(video_rows).execute()
    if video_pokemon_rows:
        client.table("video_pokemon").upsert(video_pokemon_rows).execute()

    print(
        f"upserted {len(video_rows)} videos, "
        f"{len(video_pokemon_rows)} video-pokemon links, "
        f"{len(channel_rows)} channels"
    )


if __name__ == "__main__":
    collect()
