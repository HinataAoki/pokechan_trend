"""Disambiguate which matched Pokemon a video title is actually "about".

Simple substring matching (pokemon_matcher.py) can't tell "the Pokemon the
author is using" apart from "a Pokemon merely mentioned as an opponent,
counter target, or comparison" - e.g. a title about a Rotom build that
happens to also name the Mega Staraptor it counters. That distinction needs
language understanding, so it's delegated to a small/cheap LLM call - and
only when there's actually more than one candidate to disambiguate, to keep
the per-video cost near zero for the common single-Pokemon case.

Calls are made synchronously, one per ambiguous video, spaced out to stay
under the free-tier rate limit (Gemini's Batch API would avoid this, but it
requires a billing-linked Cloud project - revisit batching once that's
sorted out). Candidates are numbered and the model is asked to answer with
just the matching numbers (e.g. "1,3") rather than repeating Pokemon name
strings, since output tokens are the expensive/limited side, not input.
"""

import re
import time

from google import genai

import config

_client: genai.Client | None = None

# Free-tier Gemini quota is requests-per-minute; space calls out to stay
# under it instead of bursting through it and falling back for every video
# past the first ~15 in a single collector run.
_MIN_SECONDS_BETWEEN_CALLS = 4.5
_last_call_at: float = 0.0

PROMPT_TEMPLATE = """\
以下はポケモン対戦ゲーム「Pokémon Champions」に関するYouTube動画のタイトルです。
このタイトル中には複数のポケモン名が含まれています。

タイトル: {title}
候補:
{numbered_candidates}

候補のうち、この動画の投稿者が実際に「使用しているポケモン」(自分のパーティ・構築・型として
扱っているポケモン)の番号だけを、カンマ区切りの数字で出力してください。対策対象・対戦相手・
比較対象として言及されているだけのポケモンの番号は含めないでください。判断がつかない場合は
その番号も含めてください。

出力は番号のみ。説明・記号・スペースは一切不要です。例: 1,3
"""

_NUMBER_RE = re.compile(r"\d+")


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _wait_for_rate_limit() -> None:
    global _last_call_at
    elapsed = time.monotonic() - _last_call_at
    remaining = _MIN_SECONDS_BETWEEN_CALLS - elapsed
    if remaining > 0:
        time.sleep(remaining)
    _last_call_at = time.monotonic()


def _build_prompt(title: str, ordered_candidates: list[str]) -> str:
    numbered = "\n".join(f"{i}. {name}" for i, name in enumerate(ordered_candidates, start=1))
    return PROMPT_TEMPLATE.format(title=title, numbered_candidates=numbered)


def _parse_selected_indices(text: str, count: int) -> set[int] | None:
    numbers = {int(n) for n in _NUMBER_RE.findall(text)}
    valid = {n for n in numbers if 1 <= n <= count}
    return valid or None


def filter_used_pokemon_batch(
    candidates_by_key: dict[str, tuple[str, set[str]]],
) -> dict[str, set[str]]:
    """Given {key: (title, candidates)}, return {key: filtered_candidates}.

    Keys with 0-1 candidates pass through unchanged (nothing to
    disambiguate). Keys with 2+ candidates each get one rate-limited Gemini
    call. If a call fails or its response can't be parsed, that key falls
    back to keeping all of its candidates - a wrong "used" label beats
    silently dropping Pokemon.
    """
    results: dict[str, set[str]] = {}
    ambiguous_keys = [key for key, (_t, c) in candidates_by_key.items() if len(c) > 1]
    for key, (_title, candidates) in candidates_by_key.items():
        if len(candidates) <= 1:
            results[key] = candidates

    if not ambiguous_keys:
        return results

    print(f"classifying {len(ambiguous_keys)} ambiguous video(s) via gemini")
    client = _get_client()

    for key in ambiguous_keys:
        title, candidates = candidates_by_key[key]
        ordered = sorted(candidates)

        try:
            _wait_for_rate_limit()
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=_build_prompt(title, ordered),
            )
        except Exception as e:
            print(f"gemini classification failed for {key}, keeping all candidates: {e}")
            results[key] = candidates
            continue

        indices = _parse_selected_indices(response.text, len(ordered))
        results[key] = {ordered[i - 1] for i in indices} if indices else candidates

    return results
