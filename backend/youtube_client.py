from googleapiclient.discovery import build

import config

_youtube = None


def get_youtube():
    global _youtube
    if _youtube is None:
        _youtube = build("youtube", "v3", developerKey=config.YOUTUBE_API_KEY)
    return _youtube


def search_video_ids(query: str, max_results: int = 50) -> list[str]:
    """Search recent videos matching a text query, return video ids."""
    youtube = get_youtube()
    video_ids = []
    request = youtube.search().list(
        part="id",
        q=query,
        type="video",
        order="date",
        maxResults=min(max_results, 50),
    )
    response = request.execute()
    for item in response.get("items", []):
        video_ids.append(item["id"]["videoId"])
    return video_ids


def get_videos_details(video_ids: list[str]) -> list[dict]:
    """Fetch snippet+statistics for up to 50 video ids per call (batched)."""
    youtube = get_youtube()
    results = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        response = (
            youtube.videos()
            .list(part="snippet,statistics", id=",".join(batch))
            .execute()
        )
        results.extend(response.get("items", []))
    return results


def get_channels_details(channel_ids: list[str]) -> list[dict]:
    """Fetch snippet+statistics for up to 50 channel ids per call (batched)."""
    youtube = get_youtube()
    results = []
    unique_ids = list(dict.fromkeys(channel_ids))
    for i in range(0, len(unique_ids), 50):
        batch = unique_ids[i : i + 50]
        response = (
            youtube.channels()
            .list(part="snippet,statistics", id=",".join(batch))
            .execute()
        )
        results.extend(response.get("items", []))
    return results
