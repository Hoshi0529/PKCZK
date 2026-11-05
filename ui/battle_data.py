"""Cached UI access to Pokemon Champions Battle Data."""

import json
from pathlib import Path

import streamlit as st

from back.champions_battle_data import BattleDataResponse, BattleFormat, fetch_pokemon_battle_data


_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
try:
    with (_DATA_DIR / "pokemon_champions_names_all_forms.json").open(encoding="utf-8") as file:
        _pokemon_names = json.load(file)
    with (_DATA_DIR / "pcbd_forms.json").open(encoding="utf-8") as file:
        _pcbd_forms = json.load(file)
except (OSError, json.JSONDecodeError):
    _pokemon_names, _pcbd_forms = {}, {}

SHOWDOWN_IDS: dict[str, str] = {
    names["name_ja"]: showdown_id
    for showdown_id, names in _pokemon_names.items()
    if isinstance(names, dict)
    and isinstance(names.get("name_ja"), str)
    and isinstance(_pcbd_forms.get(showdown_id), dict)
    and _pcbd_forms[showdown_id].get("metadata_row_available")
}
SHOWDOWN_IDS.update({
    "ピカチュウ": "pikachu",
    "マリル": "marill",
    "イーブイ": "eevee",
})

API_ATTRIBUTION = (
    'Battle data provided by '
    '<a href="https://championsbattledata.com/api_guide" target="_blank" '
    'rel="noopener noreferrer">Pokémon Champions Battle Data</a>. '
    'Fan project; not affiliated with or endorsed by Pokémon, Nintendo, GAME FREAK, or Creatures Inc.'
)


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def get_battle_data(
    pokemon_name: str, battle_format: BattleFormat = "Singles"
) -> BattleDataResponse:
    showdown_id = SHOWDOWN_IDS.get(pokemon_name)
    if showdown_id is None:
        raise ValueError(f"{pokemon_name} の Showdown ID が登録されていません。")
    return fetch_pokemon_battle_data(showdown_id, battle_format)
