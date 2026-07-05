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

# "Rising on YouTube" badge: a pokemon surges when its share of the day's
# total influence score rose by at least SURGE_MIN_SHARE_DELTA compared to
# SURGE_WINDOW_DAYS earlier; the top SURGE_TOP_N per date are exported.
SURGE_WINDOW_DAYS = 3
SURGE_MIN_SHARE_DELTA = 0.008
SURGE_TOP_N = 3


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
    share_by_date_name: dict[tuple[str, str], float] = {}
    for row in forecast_rows:
        total = totals_by_date[row["date"]]
        row["share"] = round(row["score"] / total, 4) if total > 0 else 0.0
        share_by_date_name[(row["date"], row["pokemon_name"])] = row["share"]

    # Surge picks: pokemon whose YouTube share rose the most vs 3 days ago.
    # Backtested against pokedb daily ranks: the top surge picks hit upcoming
    # >=5-rank risers at ~2x the base rate (docs/influence_model.md section 5),
    # so they're surfaced as a "rising on YouTube" badge, not as a ranking.
    dates_sorted = sorted(totals_by_date)
    date_index = {d: i for i, d in enumerate(dates_sorted)}
    names_by_date: dict[str, set] = defaultdict(set)
    for row in forecast_rows:
        names_by_date[row["date"]].add(row["pokemon_name"])
    surges: dict[str, list[str]] = {}
    for d in dates_sorted:
        i = date_index[d]
        if i < SURGE_WINDOW_DAYS:
            continue
        prev_d = dates_sorted[i - SURGE_WINDOW_DAYS]
        deltas = [
            (name, share_by_date_name.get((d, name), 0.0) - share_by_date_name.get((prev_d, name), 0.0))
            for name in names_by_date[d]
        ]
        top = sorted(
            (x for x in deltas if x[1] >= SURGE_MIN_SHARE_DELTA),
            key=lambda x: x[1],
            reverse=True,
        )[:SURGE_TOP_N]
        if top:
            surges[d] = [name for name, _ in top]

    # Video-type badge for the contribution list (joined from videos here so
    # the public contribution table doesn't need its own column).
    contribution_video_ids = list({row["video_id"] for row in contribution_rows})
    type_by_video: dict[str, str] = {}
    for i in range(0, len(contribution_video_ids), 200):
        for row in select_all(
            client,
            "videos",
            "video_id, video_type",
            lambda q, c=contribution_video_ids[i : i + 200]: q.in_("video_id", c),
        ):
            type_by_video[row["video_id"]] = row["video_type"]
    for row in contribution_rows:
        row["video_type"] = type_by_video.get(row["video_id"])

    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "forecast": forecast_rows,
        "images": {row["pokemon_name"]: row["image_url"] for row in image_rows},
        "contributions": contribution_rows,
        "surges": surges,
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
