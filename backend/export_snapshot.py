"""Bake the current calendar data into a single static JSON file, uploaded
to Supabase Storage, so the public frontend fetches one cheap CDN-served
file instead of querying tables directly on every visit.

Run standalone: `python export_snapshot.py`
Meant to run once per scheduled workflow invocation, after forecaster.py.
"""

import json
from collections import defaultdict
from datetime import datetime, timezone

from supabase_client import get_client, select_all

STORAGE_BUCKET = "public-data"
STORAGE_PATH = "snapshot.json"


def export_snapshot() -> None:
    client = get_client()

    forecast_rows = select_all(client, "pokemon_daily_forecast", "date, pokemon_name, score")
    image_rows = select_all(client, "pokemon_images", "pokemon_name, image_url")
    contribution_rows = select_all(
        client,
        "pokemon_video_contribution",
        "date, pokemon_name, video_id, video_title, youtube_url, published_at, contribution_score",
    )

    # Share = this pokemon's portion of that date's total score (see
    # docs/influence_model.md "usage rate" normalization) - a supplementary
    # field alongside the absolute score, not a replacement for it.
    totals_by_date: dict[str, float] = defaultdict(float)
    for row in forecast_rows:
        totals_by_date[row["date"]] += row["score"]
    for row in forecast_rows:
        total = totals_by_date[row["date"]]
        row["share"] = round(row["score"] / total, 4) if total > 0 else 0.0

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
