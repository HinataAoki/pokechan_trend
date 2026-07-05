"""Classify every registered video into a video-type label with Gemini.

Labels (see docs/influence_model.md §2.4 - the F_type factor):
    build   構築紹介・育成論 - party/build explanation, high imitation
    rental  レンタル配布 - rental team code distributed, highest imitation
    counter 対策解説 - how to BEAT a pokemon; its contribution to the
            countered pokemon should be zero (this is what broke the
            Swampert downtrend - counter videos counted as positive signal)
    battle  対戦・実況・その他 - baseline

Input: data/api_video_details.jsonl (fetch_video_details.py).
Output: data/video_types.json {video_id: label}, written incrementally per
batch so an interrupted run resumes without re-classifying.

Rental distribution is also detected by regex on the full description
(rental codes usually sit below the fold that we truncate away from the
LLM prompt) and overrides a non-counter LLM label.

Batches ~20 videos per Gemini call to stay practical inside the free tier
(15 requests/min): ~1,200 videos = ~60 calls = ~5 minutes.
"""

import json
import re
import time
from pathlib import Path

from google import genai

import config

DETAILS = Path(__file__).parent / "data" / "api_video_details.jsonl"
OUT = Path(__file__).parent / "data" / "video_types.json"

BATCH_SIZE = 20
SECONDS_BETWEEN_CALLS = 4.5
DESCRIPTION_SNIPPET_CHARS = 150

LABELS = {1: "build", 2: "rental", 3: "counter", 4: "battle"}

RENTAL_RE = re.compile(r"レンタル(チーム|パーティ|コード)?|貸出|チームID|rental\s*(team|code)", re.IGNORECASE)

PROMPT_HEADER = """\
以下はポケモン対戦ゲーム「Pokémon Champions」のYouTube動画のリストです。
各動画を次の4種類のうち1つに分類してください。

1 = 構築紹介・育成論(投稿者自身のパーティーや型の解説・紹介が主目的)
2 = レンタルチーム配布(レンタルコード・チームIDの配布が明記されている)
3 = 対策解説(特定のポケモンの対策・倒し方・弱点の解説が主目的)
4 = 対戦動画・実況・攻略・その他

出力形式: 各行に「動画番号:分類番号」のみ。説明は不要です。例:
1:4
2:1

"""

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _classify_batch(batch: list[dict]) -> dict[str, int]:
    lines = []
    for i, v in enumerate(batch, 1):
        desc = (v.get("description") or "")[:DESCRIPTION_SNIPPET_CHARS].replace("\n", " ")
        lines.append(f"[{i}] タイトル: {v['title']}\n    概要: {desc}")
    prompt = PROMPT_HEADER + "\n".join(lines)

    for attempt in range(3):
        try:
            response = _get_client().models.generate_content(
                model=config.GEMINI_MODEL, contents=prompt
            )
            break
        except Exception as e:
            if "429" in str(e) and attempt < 2:
                print("  rate limited - sleeping 65s")
                time.sleep(65)
                continue
            raise

    result: dict[str, int] = {}
    for line in (response.text or "").splitlines():
        m = re.match(r"\s*(\d+)\s*[::]\s*([1-4])", line)
        if m:
            idx = int(m.group(1))
            if 1 <= idx <= len(batch):
                result[batch[idx - 1]["id"]] = int(m.group(2))
    return result


def classify_types(items: list[dict], progress_cb=None) -> dict[str, str]:
    """Classify a list of {id, title, description} dicts into type labels.
    Used both by the bulk CLI below and by video_registrar.py at
    registration time. On a permanent Gemini failure, returns whatever was
    classified so far (callers treat missing ids as DEFAULT_VIDEO_TYPE).
    """
    labels: dict[str, str] = {}
    for start in range(0, len(items), BATCH_SIZE):
        batch = items[start : start + BATCH_SIZE]
        try:
            numeric = _classify_batch(batch)
        except Exception as e:
            print(f"type-classification batch failed ({e}) - continuing with partial labels")
            break
        for v in batch:
            label = LABELS.get(numeric.get(v["id"], 4), "battle")
            haystack = f"{v.get('title', '')}\n{v.get('description', '')}"
            if label != "counter" and RENTAL_RE.search(haystack):
                label = "rental"
            labels[v["id"]] = label
        if progress_cb:
            progress_cb(labels)
        if start + BATCH_SIZE < len(items):
            time.sleep(SECONDS_BETWEEN_CALLS)
    return labels


def classify() -> None:
    videos = [
        json.loads(line) for line in DETAILS.read_text(encoding="utf-8").splitlines() if line
    ]
    labels: dict[str, str] = {}
    if OUT.exists():
        labels = json.loads(OUT.read_text(encoding="utf-8"))
        print(f"resuming: {len(labels)} already classified")

    todo = [v for v in videos if v["id"] not in labels]
    print(f"classifying {len(todo)} videos in batches of {BATCH_SIZE}")

    def _save(new_labels: dict[str, str]) -> None:
        labels.update(new_labels)
        OUT.write_text(json.dumps(labels, ensure_ascii=False, indent=0), encoding="utf-8")
        if len(new_labels) % 100 < BATCH_SIZE:
            print(f"  {len(new_labels)}/{len(todo)}")

    classify_types(todo, progress_cb=_save)

    from collections import Counter

    print("label distribution:", dict(Counter(labels.values())))


if __name__ == "__main__":
    classify()
