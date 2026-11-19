"""Look up Pokémon Champions move data by Showdown ID or localized name."""

from functools import lru_cache
import json
from pathlib import Path
from unicodedata import normalize

from groq.types.chat import ChatCompletionToolParam
from langsmith import traceable


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
MOVE_STATS_TOOL: ChatCompletionToolParam = {
    "type": "function",
    "function": {
        "name": "get_move_stats",
        "description": "技の基準威力・基準命中率を、技名またはShowdown IDから取得する。",
        "parameters": {
            "type": "object",
            "properties": {
                "moves": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 10},
            },
            "required": ["moves"],
            "additionalProperties": False,
        },
    },
}


@lru_cache(maxsize=2)
def _read_table(filename: str) -> dict:
    try:
        with (DATA_DIR / filename).open(encoding="utf-8-sig") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _name_key(name: str) -> str:
    return normalize("NFKC", name).strip().casefold()


@lru_cache(maxsize=1)
def _move_ids() -> dict[str, str]:
    return {
        _name_key(name): move_id
        for move_id, names in _read_table("move_names_ja_en.json").items()
        if isinstance(names, dict)
        for name in (move_id, names.get("name_ja"), names.get("name_en"))
        if isinstance(name, str) and name
    }


def move_showdown_id(name: str) -> str | None:
    return _move_ids().get(_name_key(name))


def move_japanese_name(name: str) -> str | None:
    names = _read_table("move_names_ja_en.json").get(move_showdown_id(name), {})
    return names.get("name_ja") or None


def move_stats(name: str) -> dict | None:
    move_id = move_showdown_id(name)
    row = _read_table("move_power_accuracy.json").get(move_id)
    if not isinstance(row, dict):
        return None

    power, power_kind = row.get("power"), row.get("power_kind")
    accuracy, accuracy_kind = row.get("accuracy"), row.get("accuracy_kind")
    power_label = {
        "fixed": str(power) if power is not None else "未確認",
        "variable": f"{power}（条件で変動）" if power is not None else "条件で変動",
        "status": "—（変化技）",
        "direct_damage": "技固有のダメージ計算",
        "ohko": "一撃必殺",
        "damage_or_heal": f"相手には威力{power}、味方には回復" if power is not None else "攻撃または回復",
    }.get(power_kind, "未確認")
    accuracy_label = {
        "percent": f"{accuracy}%" if type(accuracy) is int and 0 <= accuracy <= 100 else "未確認",
        "always_hit": "必中",
        "no_check": "—（命中判定なし）",
    }.get(accuracy_kind, "未確認")
    return {
        "move_id": move_id,
        "name_ja": move_japanese_name(name) or name,
        "power": power,
        "power_kind": power_kind,
        "power_label": power_label,
        "accuracy": accuracy,
        "accuracy_kind": accuracy_kind,
        "accuracy_label": accuracy_label,
    }


@traceable(name="Get Move Power and Accuracy", run_type="tool")
def run_move_stats_tool(arguments: str) -> dict:
    try:
        request = json.loads(arguments)
        names = request["moves"]
        if (
            not isinstance(names, list)
            or not 1 <= len(names) <= 10
            or any(not isinstance(name, str) or not name.strip() or len(name) > 80 for name in names)
        ):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        return {"error": "照会したい技名を確認してください。"}
    return {"moves": [
        move_stats(name) or {"name": name, "error": "技の威力・命中率は未確認です。技名を確認してください。"}
        for name in dict.fromkeys(names)
    ]}
