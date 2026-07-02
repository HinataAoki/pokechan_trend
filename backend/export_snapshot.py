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


def export_snapshot() -> None:
    client = get_client()

    forecast_rows = client.table("pokemon_daily_forecast").select("date, pokemon_name, score").execute().data
    image_rows = client.table("pokemon_images").select("pokemon_name, image_url").execute().data
    contribution_rows = (
        client.table("pokemon_video_contribution")
        .select("date, pokemon_name, video_id, video_title, youtube_url, published_at, contribution_score")
        .execute()
        .data
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
