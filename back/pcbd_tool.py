"""Validate and run the chat tool for PCBD's current battle statistics."""

import json
import re

from groq.types.chat import ChatCompletionToolParam
from langsmith import traceable

from back.champions_battle_data import (
    API_BASE,
    BattleFormat,
    fetch_pokemon_battle_data,
    rows_for_category,
)
from back.move_stats import move_stats


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
            entry = {
                "name": row["name"],
                "rank": row.get("rank"),
                "percentage": row.get("percentage") or None,
                "percentage_value": row.get("percentage_value"),
            }
            if category == "move" and (stats := move_stats(row["name"])) is not None:
                entry["move_stats"] = stats
            statistics[category].append(entry)
    return {
        "showdown_id": showdown_id,
        "format": battle_format,
        "season": data.get("season") or "Current",
        "source_url": f"{API_BASE}/battle/{battle_format}/{showdown_id}",
        "categories": statistics,
    }


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
    results = []
    for showdown_id in dict.fromkeys(showdown_ids):
        try:
            result = _fetch_statistics(showdown_id, battle_format, requested_categories)
        except (RuntimeError, ValueError):
            result = {
                "showdown_id": showdown_id,
                "format": battle_format,
                "error": "PCBDの対戦データを取得できませんでした。",
            }
        results.append(result)
    return {"results": results}
