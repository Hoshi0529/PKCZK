"""Client for the Pokemon Champions Battle Data JSON API."""

from __future__ import annotations

import json
import re
from typing import Literal, TypedDict, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BattleFormat = Literal["Doubles", "Singles"]
API_BASE = "https://championsbattledata.com/api"


class BattleRow(TypedDict, total=False):
    position: int
    category: str
    rank: int
    name: str
    percentage: str
    percentage_value: float


class BattleDataResponse(TypedDict, total=False):
    pokemon: str
    showdownId: str
    format: str
    season: str
    source: str
    rows: list[BattleRow]


def fetch_pokemon_battle_data(
    showdown_id: str, battle_format: BattleFormat = "Singles"
) -> BattleDataResponse:
    """Fetch current battle rows for one Pokémon from the public API."""
    if not re.fullmatch(r"[a-z0-9]+", showdown_id):
        raise ValueError("showdown_id must be a Pokemon Showdown internal ID")
    if battle_format not in ("Doubles", "Singles"):
        raise ValueError("battle_format must be 'Doubles' or 'Singles'")

    request = Request(
        f"{API_BASE}/battle/{battle_format}/{showdown_id}",
        headers={
            "Accept": "application/json",
            "User-Agent": "pokecham/1.0 (Pokemon Champions battle data client)",
        },
    )
    try:
        with urlopen(request, timeout=8) as response:
            payload = json.load(response)
    except HTTPError as error:
        if error.code == 404:
            raise RuntimeError(f"API に {showdown_id} の対戦データがありません。") from error
        raise RuntimeError(f"対戦データ API が HTTP {error.code} を返しました。") from error
    except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise RuntimeError("対戦データ API に接続できませんでした。") from error

    if not isinstance(payload, dict) or not isinstance(payload.get("rows"), list):
        raise RuntimeError("対戦データ API のレスポンス形式が想定と異なります。")
    return cast(BattleDataResponse, payload)


def rows_for_category(
    data: BattleDataResponse, category: str
) -> list[BattleRow]:
    """Return rows in API rank order for a category such as move or item."""
    rows: list[BattleRow] = []
    for raw_row in data.get("rows", []):
        if not isinstance(raw_row, dict):
            continue
        row_category = raw_row.get("category")
        name = raw_row.get("name")
        if (
            isinstance(row_category, str)
            and row_category.casefold() == category.casefold()
            and isinstance(name, str)
            and name
        ):
            rows.append(cast(BattleRow, raw_row))
    def rank(row: BattleRow) -> int:
        value = row.get("rank", row.get("position", 10**9))
        return value if isinstance(value, int) else 10**9

    return sorted(rows, key=rank)
