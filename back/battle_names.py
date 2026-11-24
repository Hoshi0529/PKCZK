"""Resolve PCBD battle statistic names using the application's dictionaries."""

from functools import lru_cache
import json
from pathlib import Path
import re
from unicodedata import normalize

from back.entity_references import entity_id, entity_name


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _name_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", normalize("NFKC", name).casefold())


@lru_cache(maxsize=1)
def _name_tables() -> dict[str, dict[str, str]]:
    tables = {}
    for category, filename in (
        ("held_item", "item_showdown_ids.json"),
        ("ability", "pcbd_ability_names_ja.json"),
        ("stat_alignment", "natures.json"),
    ):
        try:
            with (DATA_DIR / filename).open(encoding="utf-8-sig") as file:
                data = json.load(file)
        except (OSError, ValueError):
            data = {}
        pairs = data.items()
        if category == "held_item":
            pairs = ((item_id, name) for name, item_id in data.items())
        elif category == "stat_alignment":
            pairs = data.get("names_ja", {}).items()
        tables[category] = {_name_key(english): japanese for english, japanese in pairs}
    return tables


def battle_japanese_name(category: str, name: str) -> str:
    kind = {"move": "move", "ability": "ability", "held_item": "item"}.get(category)
    if kind:
        showdown_id = entity_id(kind, name)
        return entity_name(kind, showdown_id) if showdown_id else name
    return _name_tables().get(category, {}).get(_name_key(name)) or name
