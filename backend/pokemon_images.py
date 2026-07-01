"""Cache Pokemon icon images from pokewiki.de into Supabase Storage.

Run standalone: `python pokemon_images.py`
Only downloads icons for Pokemon that are actually referenced in
video_pokemon but don't have a cached image yet, so a run with nothing
new to fetch skips scraping entirely.
"""

import html
import re
import urllib.request
from datetime import datetime, timezone

from supabase_client import get_client

LIST_URL = "https://www.pokewiki.de/index.php?title=Pok%C3%A9mon-Liste"
BASE_URL = "https://www.pokewiki.de"
STORAGE_BUCKET = "pokemon-icons"

USER_AGENT = "pokechan-trend/1.0 (+https://github.com/HinataAoki/pokechan_trend)"

ROW_NUMBER_RE = re.compile(r"^\s*<td>(\d{4})</td>")
ICON_SRC_RE = re.compile(r'class="pokemon_icon[^"]*".*?<img src="([^"]+)"', re.S)
FIRST_RUBY_RE = re.compile(r"<ruby><rb>([^<]+)</rb>")


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def scrape_image_map() -> dict[str, tuple[int, str]]:
    """Return {japanese_name: (dex_number, absolute_icon_url)} scraped once."""
    page = _fetch(LIST_URL).decode("utf-8")
    mapping: dict[str, tuple[int, str]] = {}

    for row in page.split("<tr>"):
        number_match = ROW_NUMBER_RE.match(row)
        icon_match = ICON_SRC_RE.search(row)
        name_match = FIRST_RUBY_RE.search(row)
        if not (number_match and icon_match and name_match):
            continue

        dex_number = int(number_match.group(1))
        image_url = BASE_URL + html.unescape(icon_match.group(1))
        name = html.unescape(name_match.group(1))
        mapping[name] = (dex_number, image_url)

    return mapping


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
    image_map = scrape_image_map()

    rows_to_insert = []
    for name in missing_names:
        entry = image_map.get(name)
        if entry is None:
            print(f"no icon found on pokewiki for: {name}")
            continue

        dex_number, image_url = entry
        storage_path = f"{dex_number:04d}.png"
        image_bytes = _fetch(image_url)

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
