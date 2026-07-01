import json
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "pokemon_names.json"


@lru_cache(maxsize=1)
def _surface_form_index() -> list[tuple[str, str]]:
    """List of (surface_form, canonical_name) sorted by form length descending.

    Longest-first matters because some Pokemon names are literal substrings
    of others (e.g. "ラッキー"/Chansey is contained in "ブラッキー"/Umbreon,
    "ゾロア"/Zorua in "ゾロアーク"/Zoroark) - matching longest-first and then
    marking that text span as consumed (see match_pokemon) stops the shorter
    name from also matching inside the longer one's span.
    """
    entries = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    pairs = [
        (form, entry["canonical"])
        for entry in entries
        for form in entry["surface_forms"]
    ]
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs


def _match_in_text(text: str) -> set[str]:
    consumed = bytearray(len(text))
    matched = set()

    for surface_form, canonical in _surface_form_index():
        form_len = len(surface_form)
        start = 0
        while True:
            idx = text.find(surface_form, start)
            if idx == -1:
                break
            if not any(consumed[idx : idx + form_len]):
                matched.add(canonical)
                for i in range(idx, idx + form_len):
                    consumed[i] = 1
                start = idx + form_len
            else:
                start = idx + 1

    return matched


def match_pokemon(*texts: str) -> set[str]:
    """Return canonical Pokemon names mentioned in any of the given texts."""
    matched = set()
    for text in texts:
        if text:
            matched |= _match_in_text(text)
    return matched
