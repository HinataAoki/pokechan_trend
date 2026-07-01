"""Discover candidate videos and register them + their Pokemon into Supabase.

Run standalone: `python collector.py`
Meant to run once per scheduled workflow invocation, before snapshotter.py.
"""

from datetime import datetime, timedelta, timezone

import config
import youtube_client
from pokemon_matcher import match_pokemon
from supabase_client import get_client


def _classify_discovery(title: str, description: str, tags: list[str]) -> str | None:
    """Is this video about Pokemon Champions at all? Title/description/tags
    are all fair signals here - this only decides relevance, not which
    Pokemon are shown (see match_pokemon below, which is title-only)."""
    haystack_title = title or ""
    haystack_description = description or ""
    haystack_tags = "\n".join(tags or [])

    game_keywords = config.TITLE_KEYWORDS + config.GAME_TITLE_KEYWORDS

    if any(kw in haystack_title for kw in game_keywords):
        return "title_keyword"
    if any(tag in haystack_description for tag in config.HASHTAGS):
        return "hashtag"
    # YouTube tags rarely include the "#" prefix, so match the bare keywords
    # there too (e.g. a tag literally set to "ポケモンチャンピオンズ").
    if any(kw in haystack_tags for kw in game_keywords):
        return "tag"
    if any(kw in haystack_description for kw in game_keywords):
        return "game_title"
    return None


def collect() -> None:
    client = get_client()

    published_after = (
        datetime.now(timezone.utc) - timedelta(hours=config.SEARCH_LOOKBACK_HOURS)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    video_ids: set[str] = set()
    for query in config.SEARCH_QUERIES:
        video_ids.update(youtube_client.search_video_ids(query, published_after))

    if not video_ids:
        print("no candidate videos found")
        return

    videos = youtube_client.get_videos_details(list(video_ids))
    print(f"fetched details for {len(videos)} videos")

    # A video is only kept if it's recognizably about the game (title/
    # description/tags) AND names at least one Pokemon in its title -
    # titles without a named Pokemon give us nothing to attribute usage to.
    relevant_videos = []
    for video in videos:
        snippet = video["snippet"]
        title = snippet.get("title", "")
        description = snippet.get("description", "")
        tags = snippet.get("tags", [])

        discovered_via = _classify_discovery(title, description, tags)
        if discovered_via is None:
            continue

        pokemon_names = match_pokemon(title)
        if not pokemon_names:
            continue

        relevant_videos.append((video, discovered_via, pokemon_names))

    if not relevant_videos:
        print("no relevant videos with a Pokemon named in the title")
        return

    channel_ids = [v["snippet"]["channelId"] for v, _, _ in relevant_videos]
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
    for video, discovered_via, pokemon_names in relevant_videos:
        snippet = video["snippet"]
        video_id = video["id"]

        video_rows.append(
            {
                "video_id": video_id,
                "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
                "title": snippet.get("title", ""),
                "published_at": snippet["publishedAt"],
                "channel_id": snippet["channelId"],
                "discovered_via": discovered_via,
            }
        )

        for pokemon_name in pokemon_names:
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
