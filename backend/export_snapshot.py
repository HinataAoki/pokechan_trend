"""Bake the current calendar data into a single static JSON file, uploaded
to Supabase Storage, so the public frontend fetches one cheap CDN-served
file instead of querying tables directly on every visit.

Run standalone: `python export_snapshot.py`
Meant to run once per scheduled workflow invocation, after forecaster.py.
"""

import json
from datetime import datetime, timezone

from supabase_client import get_client

STORAGE_BUCKET = "public-data"
STORAGE_PATH = "snapshot.json"
PAGE_SIZE = 1000  # PostgREST's default/max rows per response


def _select_all(client, table: str, columns: str) -> list[dict]:
    """Page through a table's rows - a plain .execute() silently caps out
    at PostgREST's default row limit (1000), which truncated this export
    once the calendar's dataset grew past it."""
    rows = []
    offset = 0
    while True:
        page = client.table(table).select(columns).range(offset, offset + PAGE_SIZE - 1).execute().data
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def export_snapshot() -> None:
    client = get_client()

    forecast_rows = _select_all(client, "pokemon_daily_forecast", "date, pokemon_name, score")
    image_rows = _select_all(client, "pokemon_images", "pokemon_name, image_url")
    contribution_rows = _select_all(
        client,
        "pokemon_video_contribution",
        "date, pokemon_name, video_id, video_title, youtube_url, published_at, contribution_score",
    )

    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "forecast": forecast_rows,
        "images": {row["pokemon_name"]: row["image_url"] for row in image_rows},
        "contributions": contribution_rows,
    }

    payload = json.dumps(snapshot, ensure_ascii=False).encode("utf-8")
    client.storage.from_(STORAGE_BUCKET).upload(
        STORAGE_PATH,
        payload,
        {"content-type": "application/json", "upsert": "true", "cache-control": "300"},
    )

    print(
        f"exported snapshot: {len(forecast_rows)} forecast rows, "
        f"{len(image_rows)} images, {len(contribution_rows)} contributions"
    )


if __name__ == "__main__":
    export_snapshot()
