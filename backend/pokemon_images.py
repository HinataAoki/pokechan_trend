"""Cache Pokemon icon images from pokewiki.de into Supabase Storage.

Run standalone: `python pokemon_images.py`
Only downloads icons for Pokemon that are actually referenced in
video_pokemon but don't have a cached image yet, so a run with nothing
new to fetch skips scraping entirely.
"""

from datetime import datetime, timezone

from pokewiki import fetch_bytes, scrape_pokemon_table
from supabase_client import get_client

STORAGE_BUCKET = "pokemon-icons"


def fetch_missing_images() -> None:
    client = get_client()

    used_resp = client.table("video_pokemon").select("pokemon_name").execute()
    used_names = {row["pokemon_name"] for row in used_resp.data}
    if not used_names:
        print("no pokemon referenced yet, nothing to fetch")
        return

    cached_resp = client.table("pokemon_images").select("pokemon_name").execute()
    cached_names = {row["pokemon_name"] for row in cached_resp.data}

    missing_names = used_names - cached_names
    if not missing_names:
        print("no missing icons")
        return

    print(f"scraping pokewiki.de for {len(missing_names)} missing icon(s)")
    image_map = {entry["japanese_name"]: entry for entry in scrape_pokemon_table()}

    rows_to_insert = []
    for name in missing_names:
        entry = image_map.get(name)
        if entry is None:
            print(f"no icon found on pokewiki for: {name}")
            continue

        storage_path = f"{entry['dex_number']:04d}.png"
        image_bytes = fetch_bytes(entry["image_url"])

        client.storage.from_(STORAGE_BUCKET).upload(
            storage_path,
            image_bytes,
            {"content-type": "image/png", "upsert": "true"},
        )
        public_url = client.storage.from_(STORAGE_BUCKET).get_public_url(storage_path)

        rows_to_insert.append(
            {
                "pokemon_name": name,
                "image_url": public_url,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    if rows_to_insert:
        client.table("pokemon_images").upsert(rows_to_insert).execute()
    print(f"cached {len(rows_to_insert)} icon(s)")


if __name__ == "__main__":
    fetch_missing_images()
