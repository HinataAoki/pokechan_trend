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
from supabase_client import get_client, select_all

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
    rows = select_all(
        client, "video_pokemon", "video_id, pokemon_name",
        lambda q: q.in_("video_id", counter_ids),
    )
    for r in rows:
        pokemon_by_video[r["video_id"]].append(r["pokemon_name"])

    videos = [v for v in counter_ids if v in details]
    gclient = genai.Client(api_key=config.GEMINI_API_KEY)
    result: dict[str, dict] = {}

    for start in range(0, len(videos), BATCH_SIZE):
        batch = videos[start : start + BATCH_SIZE]
        lines = []
        for i, vid in enumerate(batch, 1):
            title = details[vid]["title"]
            cands = "、".join(pokemon_by_video.get(vid, [])) or "(候補なし)"
            lines.append(f"[{i}] タイトル: {title}\n    候補: {cands}")
        response = gclient.models.generate_content(
            model=config.GEMINI_MODEL, contents=PROMPT_HEADER + "\n".join(lines)
        )
        for line in (response.text or "").splitlines():
            m = re.match(r"\s*(\d+)\s*[::]\s*([AB])(?:\s*[::]\s*(.+))?", line.strip())
            if not m:
                continue
            idx = int(m.group(1))
            if not (1 <= idx <= len(batch)):
                continue
            vid = batch[idx - 1]
            if m.group(2) == "A" and m.group(3):
                result[vid] = {"kind": "counter", "target": m.group(3).strip()}
            else:
                result[vid] = {"kind": "showcase"}
        time.sleep(5)

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    n_counter = sum(1 for v in result.values() if v["kind"] == "counter")
    print(f"wrote {len(result)} records ({n_counter} true counters) -> {OUT.name}")


if __name__ == "__main__":
    refine()
