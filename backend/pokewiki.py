"""Shared scraper for pokewiki.de's master Pokemon list page.

Used both to build the local name-matching dictionary (generate_pokemon_names.py)
and to cache icon images (pokemon_images.py), so the two stay in sync and the
page is only ever parsed with one regex set.
"""

import html
import re
import urllib.request

LIST_URL = "https://www.pokewiki.de/index.php?title=Pok%C3%A9mon-Liste"
BASE_URL = "https://www.pokewiki.de"
USER_AGENT = "pokechan-trend/1.0 (+https://github.com/HinataAoki/pokechan_trend)"

# Row formats seen on the page: most rows are "<td>0025</td>", but a handful
# of early entries wrap the number in a <span id="nrNNNN"> anchor first.
NUMBER_RE = re.compile(r'^\s*<td>(?:<span id="nr\d+"[^>]*></span>\s*)?(\d{4})</td>')
ICON_SRC_RE = re.compile(r'class="pokemon_icon[^"]*".*?<img src="([^"]+)"', re.S)
# German name (linked), then English, then French - all plain <td> cells in
# that order, immediately followed by the Japanese name as a <ruby><rb>.
NAME_COLUMNS_RE = re.compile(
    r"<td><a[^>]*>[^<]+</a></td>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>\s*"
    r"<td><span[^>]*><ruby><rb>([^<]+)</rb>",
    re.S,
)


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def scrape_pokemon_table() -> list[dict]:
    """Return one entry per Pokemon: dex_number, japanese_name, english_name, image_url."""
    page = fetch_bytes(LIST_URL).decode("utf-8")
    entries = []

    for row in page.split("<tr>"):
        number_match = NUMBER_RE.match(row)
        icon_match = ICON_SRC_RE.search(row)
        names_match = NAME_COLUMNS_RE.search(row)
        if not (number_match and icon_match and names_match):
            continue

        english_name, _french_name, japanese_name = (
            html.unescape(g.strip()) for g in names_match.groups()
        )

        entries.append(
            {
                "dex_number": int(number_match.group(1)),
                "japanese_name": japanese_name,
                "english_name": english_name,
                "image_url": BASE_URL + html.unescape(icon_match.group(1)),
            }
        )

    return entries
