import json
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "pokemon_names.json"


@lru_cache(maxsize=1)
def _surface_form_index() -> list[tuple[str, str]]:
    """List of (surface_form, canonical_name) sorted by form length descending.

    Longest-first avoids short names (e.g. "Kyogre" substrings) shadowing
    longer ones when scanning text.
    """
    entries = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    pairs = [
        (form, entry["canonical"])
        for entry in entries
        for form in entry["surface_forms"]
    ]
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs


def match_pokemon(*texts: str) -> set[str]:
    """Return canonical Pokemon names mentioned in any of the given texts."""
    haystack = "\n".join(t for t in texts if t)
    if not haystack:
        return set()

    matched = set()
    for surface_form, canonical in _surface_form_index():
        if surface_form in haystack:
            matched.add(canonical)
    return matched
