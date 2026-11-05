"""Cached UI access to Pokemon Champions Battle Data."""

import streamlit as st

from back.champions_battle_data import BattleDataResponse, BattleFormat, fetch_pokemon_battle_data


SHOWDOWN_IDS: dict[str, str] = {
    "ピカチュウ": "pikachu",
    "ガブリアス": "garchomp",
    "マリル": "marill",
    "ルカリオ": "lucario",
    "イーブイ": "eevee",
}

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
