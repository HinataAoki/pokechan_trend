"""One-off script to build backend/data/pokemon_names.json from pokewiki.de.

Not part of the scheduled pipeline - run manually when the Pokedex needs
refreshing (e.g. after a new generation releases). Output maps a canonical
Japanese name to the list of surface forms (Japanese + English) that
pokemon_matcher.py will search for in video titles.
"""

import json
from pathlib import Path

from pokewiki import scrape_pokemon_table

OUTPUT_PATH = Path(__file__).parent / "data" / "pokemon_names.json"


def main() -> None:
    entries = scrape_pokemon_table()

    output = [
        {
            "canonical": entry["japanese_name"],
            "surface_forms": sorted({entry["japanese_name"], entry["english_name"]}),
        }
        for entry in entries
    ]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"wrote {len(output)} entries to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
