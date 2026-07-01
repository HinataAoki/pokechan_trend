"""One-off script to build backend/data/pokemon_names.json from PokeAPI.

Not part of the scheduled pipeline - run manually when the Pokedex needs
refreshing (e.g. after a new generation releases). Output maps a canonical
Japanese name to the list of surface forms (Japanese + English) that
pokemon_matcher.py will search for in video titles/descriptions/tags.
"""

import json
import time
import urllib.request
from pathlib import Path

SPECIES_LIST_URL = "https://pokeapi.co/api/v2/pokemon-species?limit=2000"
OUTPUT_PATH = Path(__file__).parent / "data" / "pokemon_names.json"


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "pokechan-trend/1.0"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    species_list = fetch_json(SPECIES_LIST_URL)["results"]
    entries = []

    for i, species in enumerate(species_list):
        detail = fetch_json(species["url"])
        ja_name = None
        en_name = None
        for name_entry in detail["names"]:
            lang = name_entry["language"]["name"]
            if lang == "ja-hrkt" and ja_name is None:
                ja_name = name_entry["name"]
            elif lang == "en" and en_name is None:
                en_name = name_entry["name"]

        canonical = ja_name or en_name or species["name"]
        surface_forms = sorted({f for f in (ja_name, en_name) if f})
        entries.append({"canonical": canonical, "surface_forms": surface_forms})

        if (i + 1) % 50 == 0:
            print(f"fetched {i + 1}/{len(species_list)}")
        time.sleep(0.05)  # be polite to PokeAPI

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"wrote {len(entries)} entries to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
