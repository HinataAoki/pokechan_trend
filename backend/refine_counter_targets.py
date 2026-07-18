"""Refine the 'counter' video-type labels and identify each counter video's
target pokemon.

classify_video_types.py's counter bucket mixes true counter guides ("how to
beat X") with showcase/analysis videos praising a strong pokemon ("X is
BONKERS"). The influence model needs them separated: a true counter video
exerts *negative* pressure on its target's usage, while a showcase is
effectively a build video (positive). This asks Gemini to re-judge only the
counter-labeled videos and, for true counters, to name the target from the
video's matched pokemon candidates.

Output: data/counter_targets.json
    {video_id: {"kind": "counter", "target": "<pokemon>"} | {"kind": "showcase"}}

Run standalone: `python refine_counter_targets.py`
(after classify_video_types.py; needs data/video_types.json)
"""

import json
import re
import time
from collections import defaultdict
from pathlib import Path

from google import genai

import config
from supabase_client import get_client, select_all_in

DATA = Path(__file__).parent / "data"
OUT = DATA / "counter_targets.json"
BATCH_SIZE = 12

PROMPT_HEADER = """\
以下はポケモン対戦ゲーム「Pokémon Champions」のYouTube動画です。いずれも
「特定ポケモンの対策」に見える動画ですが、実際には2種類が混ざっています:

A = 対策動画: 特定のポケモンを「倒す・止める・対策する」方法の解説が主目的
B = 紹介動画: 特定のポケモンの強さ・構築・使い方を肯定的に紹介(「強すぎる」「ヤバい」等)

各動画について、Aなら対策対象のポケモン名を候補から1つ選び、Bなら B とだけ答えてください。

出力形式: 各行「動画番号:A:ポケモン名」または「動画番号:B」のみ。例:
1:A:ガブリアス
2:B

"""


def refine_counters(items: list[dict]) -> dict[str, dict]:
    """items: [{id, title, candidates: [pokemon_name, ...]}, ...]
    Returns {id: {"kind": "counter", "target": name} | {"kind": "showcase"}}.
    Used by the bulk CLI below and by video_registrar.py at registration
    time. On a Gemini failure, missing ids are simply absent (callers treat
    them as showcase, i.e. no zeroing)."""
    gclient = genai.Client(api_key=config.GEMINI_API_KEY)
    result: dict[str, dict] = {}

    for start in range(0, len(items), BATCH_SIZE):
        batch = items[start : start + BATCH_SIZE]
        lines = []
        for i, item in enumerate(batch, 1):
            cands = "、".join(item.get("candidates", [])) or "(候補なし)"
            lines.append(f"[{i}] タイトル: {item['title']}\n    候補: {cands}")
        try:
            response = gclient.models.generate_content(
                model=config.GEMINI_MODEL, contents=PROMPT_HEADER + "\n".join(lines)
            )
        except Exception as e:
            print(f"counter-refinement batch failed ({e}) - continuing with partial results")
            break
        for line in (response.text or "").splitlines():
            m = re.match(r"\s*(\d+)\s*[::]\s*([AB])(?:\s*[::]\s*(.+))?", line.strip())
            if not m:
                continue
            idx = int(m.group(1))
            if not (1 <= idx <= len(batch)):
                continue
            vid = batch[idx - 1]["id"]
            if m.group(2) == "A" and m.group(3):
                result[vid] = {"kind": "counter", "target": m.group(3).strip()}
            else:
                result[vid] = {"kind": "showcase"}
        if start + BATCH_SIZE < len(items):
            time.sleep(5)
    return result


def refine() -> None:
    types = json.loads((DATA / "video_types.json").read_text(encoding="utf-8"))
    counter_ids = [vid for vid, label in types.items() if label == "counter"]
    print(f"{len(counter_ids)} counter-labeled videos")

    details = {}
    with (DATA / "api_video_details.jsonl").open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            details[d["id"]] = d

    client = get_client()
    pokemon_by_video = defaultdict(list)
    rows = select_all_in(client, "video_pokemon", "video_id, pokemon_name", "video_id", counter_ids)
    for r in rows:
        pokemon_by_video[r["video_id"]].append(r["pokemon_name"])

    items = [
        {"id": vid, "title": details[vid]["title"], "candidates": pokemon_by_video.get(vid, [])}
        for vid in counter_ids
        if vid in details
    ]
    result = refine_counters(items)

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    n_counter = sum(1 for v in result.values() if v["kind"] == "counter")
    print(f"wrote {len(result)} records ({n_counter} true counters) -> {OUT.name}")


if __name__ == "__main__":
    refine()
