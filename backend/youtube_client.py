import functools
import re

from googleapiclient.discovery import build

import config

_youtube = None

_ISO8601_DURATION_RE = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$")


def _retry_on_connection_error(fn):
    """Rebuild the API client and retry once on connection-level errors.

    The client's underlying HTTPS connection goes stale when a run spends a
    long stretch between API calls (e.g. rate-limited Gemini classification
    inside register_videos), and the next reuse dies with BrokenPipeError /
    ConnectionReset / SSL errors - all OSError subclasses. A fresh client
    gets a fresh connection; API reads here are idempotent so a whole-call
    retry is safe."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        global _youtube
        try:
            return fn(*args, **kwargs)
        except OSError as e:
            print(f"YouTube API connection error ({e!r}) - rebuilding client, retrying once")
            _youtube = None
            return fn(*args, **kwargs)

    return wrapper


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


@_retry_on_connection_error
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


@_retry_on_connection_error
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


@_retry_on_connection_error
def get_channel_by_handle(handle: str) -> dict | None:
    """Resolve an @handle (without the @) to its channel snippet+statistics."""
    youtube = get_youtube()
    response = youtube.channels().list(part="snippet,statistics", forHandle=handle).execute()
    items = response.get("items", [])
    return items[0] if items else None


@_retry_on_connection_error
def fetch_channel_video_ids_since(channel_id: str, published_after: str) -> list[str]:
    """Page through a channel's uploads playlist (cheap: 1 unit/page,
    unlike search.list) collecting video ids published since `published_after`
    (RFC3339 timestamp). The uploads playlist is newest-first, so pagination
    stops as soon as an older video is seen."""
    youtube = get_youtube()
    uploads_playlist_id = "UU" + channel_id[2:]
    video_ids = []
    page_token = None

    while True:
        response = (
            youtube.playlistItems()
            .list(
                part="contentDetails",
                playlistId=uploads_playlist_id,
                maxResults=50,
                pageToken=page_token,
            )
            .execute()
        )

        reached_older_videos = False
        for item in response.get("items", []):
            details = item["contentDetails"]
            video_published_at = details.get("videoPublishedAt")
            if video_published_at and video_published_at < published_after:
                reached_older_videos = True
                continue
            video_ids.append(details["videoId"])

        page_token = response.get("nextPageToken")
        if reached_older_videos or not page_token:
            break

    return video_ids


@_retry_on_connection_error
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
