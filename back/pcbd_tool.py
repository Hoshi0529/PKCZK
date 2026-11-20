"""Validate and run the chat tool for PCBD's current battle statistics."""

import json
import re
from concurrent.futures import ThreadPoolExecutor

from groq.types.chat import ChatCompletionToolParam
from langsmith import traceable

from back.champions_battle_data import (
    API_BASE,
    BattleFormat,
    fetch_pokemon_battle_data,
    rows_for_category,
)
from back.move_stats import move_japanese_name, move_stats


CATEGORIES = ("move", "held_item", "teammate", "stat_alignment", "stat_points", "ability")
PCBD_TOOL: ChatCompletionToolParam = {
    "type": "function",
    "function": {
        "name": "get_pcbd_battle_data",
        "description": (
            "選出済みポケモンの現在の対戦統計を取得する。"
            "move=技、held_item=持ち物、teammate=相棒、stat_alignment=性格、"
            "stat_points=能力ポイント配分、ability=特性。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "showdown_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 2},
                "battle_format": {"type": "string", "enum": ["Singles", "Doubles"], "default": "Singles"},
                "categories": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(CATEGORIES)},
                    "minItems": 1,
                    "maxItems": len(CATEGORIES),
                },
            },
            "required": ["showdown_ids", "categories"],
            "additionalProperties": False,
        },
    },
}


@traceable(name="PCBD Battle API", run_type="tool")
def _fetch_statistics(showdown_id: str, battle_format: BattleFormat, categories: list[str]) -> dict:
    data = fetch_pokemon_battle_data(showdown_id, battle_format)
    statistics = {}
    for category in categories:
        statistics[category] = []
        for row in rows_for_category(data, category):
            name = row["name"]
            entry = {
                "name": (move_japanese_name(name) or name) if category == "move" else name,
                "rank": row.get("rank"),
                "percentage": row.get("percentage") or None,
                "percentage_value": row.get("percentage_value"),
            }
            if category == "move" and (stats := move_stats(name)) is not None:
                entry["move_stats"] = stats
            statistics[category].append(entry)
    return {
        "showdown_id": showdown_id,
        "format": battle_format,
        "season": data.get("season") or "Current",
        "source_url": f"{API_BASE}/battle/{battle_format}/{showdown_id}",
        "categories": statistics,
    }


def render_move_ranking(result: dict, name: str, count: int, include_stats: bool) -> str | None:
    moves = result.get("categories", {}).get("move")
    if not moves:
        return None

    headers = ["順位", "技名", "採用率"]
    if include_stats:
        headers.extend(("基準威力", "基準命中率"))
    table = [headers, ["---"] * len(headers)]
    for move in moves[:count]:
        display_name = move["name"].replace("|", r"\|").replace("\n", " ").replace("\r", " ")
        row = [str(move["rank"] or "—"), display_name, move["percentage"] or "未確認"]
        if include_stats:
            stats = move.get("move_stats", {})
            row.extend((stats.get("power_label", "未確認"), stats.get("accuracy_label", "未確認")))
        table.append(row)

    battle_format = "ダブル" if result["format"] == "Doubles" else "シングル"
    lines = [f"**{name}の技採用率（{battle_format}・{result['season']}）**", ""]
    lines.extend("| " + " | ".join(row) + " |" for row in table)
    lines.extend(("", f"採用率の出典は [PCBD]({result['source_url']})。"))
    if include_stats:
        lines.append("基準威力・基準命中率の出典は推しポケラボの技データ。")
    return "\n".join(lines)


@traceable(name="Get PCBD Battle Data", run_type="tool")
def run_pcbd_tool(arguments: str, allowed_ids: list[str]) -> dict:
    try:
        args = json.loads(arguments)
    except (TypeError, ValueError):
        return {"error": "PCBDの取得条件を読み取れませんでした。"}
    if not isinstance(args, dict) or args.keys() - {"showdown_ids", "battle_format", "categories"}:
        return {"error": "PCBDの取得条件が無効です。"}

    showdown_ids = args.get("showdown_ids")
    battle_format = args.get("battle_format", "Singles")
    categories = args.get("categories")
    if (
        not isinstance(showdown_ids, list)
        or not 1 <= len(showdown_ids) <= 2
        or any(
            not isinstance(value, str) or value not in allowed_ids or not re.fullmatch(r"[a-z0-9]+", value)
            for value in showdown_ids
        )
        or battle_format not in ("Singles", "Doubles")
        or not isinstance(categories, list)
        or not 1 <= len(categories) <= len(CATEGORIES)
        or any(category not in CATEGORIES for category in categories)
    ):
        return {"error": "会話内のShowdown ID・対戦形式・項目を確認できませんでした。"}

    requested_categories = list(dict.fromkeys(categories))
    unique_ids = list(dict.fromkeys(showdown_ids))

    def fetch_result(showdown_id: str) -> dict:
        try:
            return _fetch_statistics(showdown_id, battle_format, requested_categories)
        except (RuntimeError, ValueError):
            return {
                "showdown_id": showdown_id,
                "format": battle_format,
                "error": "PCBDの対戦データを取得できませんでした。",
            }

    # Each Pokemon is independent. Run both permitted API requests together.
    # executor.map preserves input order, so the response shape stays stable.
    if len(unique_ids) == 1:
        results = [fetch_result(unique_ids[0])]
    else:
        with ThreadPoolExecutor(max_workers=len(unique_ids)) as executor:
            results = list(executor.map(fetch_result, unique_ids))
    return {"results": results}
