"""Push video-type labels from data/video_types.json (+ counter refinements
from data/counter_targets.json) into the videos.video_type / counter_target
columns.

Used for catch-up after batch classification runs (classify_video_types.py /
refine_counter_targets.py). Newly registered videos are classified inline by
video_registrar.py, so this is only needed when labels are (re)generated in
bulk.

Run standalone: `python sync_video_types_to_db.py`
"""

import json
from collections import defaultdict
from pathlib import Path

from supabase_client import get_client

DATA = Path(__file__).parent / "data"


def sync() -> None:
    types = json.loads((DATA / "video_types.json").read_text(encoding="utf-8"))
    counters = json.loads((DATA / "counter_targets.json").read_text(encoding="utf-8"))

    # Counter-labeled videos that were refined into strength showcases are
    # effectively build videos.
    for vid, info in counters.items():
        if info.get("kind") == "showcase" and types.get(vid) == "counter":
            types[vid] = "build"

    client = get_client()
    by_label = defaultdict(list)
    for vid, label in types.items():
        by_label[label].append(vid)

    for label, ids in by_label.items():
        for i in range(0, len(ids), 300):
            client.table("videos").update({"video_type": label}).in_(
                "video_id", ids[i : i + 300]
            ).execute()
        print(f"{label}: {len(ids)} rows")

    n = 0
    for vid, info in counters.items():
        if info.get("kind") == "counter" and info.get("target"):
            client.table("videos").update({"counter_target": info["target"]}).eq(
                "video_id", vid
            ).execute()
            n += 1
    print(f"counter_target set on {n} rows")

    resp = (
        client.table("videos")
        .select("video_id", count="exact")
        .is_("video_type", "null")
        .execute()
    )
    print(f"rows still unlabeled: {resp.count}")


if __name__ == "__main__":
    sync()
