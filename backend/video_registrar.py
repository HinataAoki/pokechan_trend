"""Shared classify/match/register pipeline for candidate videos.

Used by both collector.py (search.list-discovered videos, expensive quota)
and rss_watcher.py (RSS-discovered videos from already-known channels,
free) so the relevance/Pokemon-matching rules stay identical regardless of
how a video was found.
"""

import config
import youtube_client
from llm_classifier import filter_used_pokemon_batch
from pokemon_matcher import match_pokemon
from supabase_client import get_client


def classify_discovery(title: str, description: str, tags: list[str]) -> str | None:
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


def register_videos(videos: list[dict]) -> None:
    """Classify, match, and upsert a batch of videos().list() items
    (snippet+statistics) into Supabase. Videos that aren't recognizably
    about the game, or that name no Pokemon in their title, are dropped."""
    client = get_client()

    candidate_videos = []
    candidates_by_key: dict[str, tuple[str, set[str]]] = {}
    for video in videos:
        snippet = video["snippet"]
        title = snippet.get("title", "")
        description = snippet.get("description", "")
        tags = snippet.get("tags", [])

        duration_seconds = youtube_client.parse_duration_seconds(
            video.get("contentDetails", {}).get("duration")
        )
        if duration_seconds is not None and duration_seconds <= config.MIN_VIDEO_DURATION_SECONDS:
            continue

        discovered_via = classify_discovery(title, description, tags)
        if discovered_via is None:
            continue

        pokemon_names = match_pokemon(title)
        if not pokemon_names:
            continue

        candidate_videos.append((video, discovered_via, duration_seconds))
        candidates_by_key[video["id"]] = (title, pokemon_names)

    if not candidate_videos:
        print("no relevant videos with a Pokemon named in the title")
        return

    # When multiple names are matched in one title, one can be an opponent/
    # counter rather than something actually used - ask an LLM to narrow
    # each down (skipped automatically for videos with only one candidate).
    filtered_by_key = filter_used_pokemon_batch(candidates_by_key)

    relevant_videos = [
        (video, discovered_via, duration_seconds, filtered_by_key[video["id"]])
        for video, discovered_via, duration_seconds in candidate_videos
    ]

    channel_ids = [v["snippet"]["channelId"] for v, _, _, _ in relevant_videos]
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
    for video, discovered_via, duration_seconds, pokemon_names in relevant_videos:
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
                "duration_seconds": duration_seconds,
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
