import re

from googleapiclient.discovery import build

import config

_youtube = None

_ISO8601_DURATION_RE = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$")


def parse_duration_seconds(duration: str) -> int | None:
    """Parse an ISO 8601 duration (e.g. "PT2M35S") into seconds, or None if
    unparseable (e.g. an ongoing livestream/premiere reports "P0D")."""
    match = _ISO8601_DURATION_RE.match(duration or "")
    if not match:
        return None
    hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def get_youtube():
    global _youtube
    if _youtube is None:
        _youtube = build("youtube", "v3", developerKey=config.YOUTUBE_API_KEY)
    return _youtube


def search_video_ids(query: str, published_after: str, max_pages: int = 5) -> list[str]:
    """Search videos matching a text query published since `published_after`
    (RFC3339 timestamp), paginating through all results rather than just the
    first 50 - with `order="date"` and no date bound, videos can get pushed
    off the first page (and never discovered) once upload volume is high."""
    youtube = get_youtube()
    video_ids = []
    page_token = None

    for _ in range(max_pages):
        response = (
            youtube.search()
            .list(
                part="id",
                q=query,
                type="video",
                order="date",
                publishedAfter=published_after,
                maxResults=50,
                pageToken=page_token,
            )
            .execute()
        )
        for item in response.get("items", []):
            video_ids.append(item["id"]["videoId"])

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return video_ids


def get_videos_details(video_ids: list[str]) -> list[dict]:
    """Fetch snippet+statistics+contentDetails for up to 50 video ids per
    call (batched). contentDetails.duration is used to filter out very
    short videos (see config.MIN_VIDEO_DURATION_SECONDS)."""
    youtube = get_youtube()
    results = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        response = (
            youtube.videos()
            .list(part="snippet,statistics,contentDetails", id=",".join(batch))
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
