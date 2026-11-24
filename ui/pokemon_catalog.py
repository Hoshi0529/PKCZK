"""Local Pokémon profiles and the artwork used by selection and chat."""

import json
from pathlib import Path
import re
from urllib.parse import quote

from ui.pokemon_types import PokemonProfile


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _load_json(filename: str) -> dict:
    try:
        with (DATA_DIR / filename).open(encoding="utf-8") as file:
            value = json.load(file)
            return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


_NAMES = _load_json("pokemon_champions_names_all_forms.json")
_FORMS = _load_json("pcbd_forms.json")
_LEGACY_POKEMON = _load_json("legacy_pokemon.json")
ABILITY_SHOWDOWN_IDS: dict[str, str] = {}
# PCBD's translation table is keyed by English name. Use Showdown's toID rule.
for english_name, japanese_name in _load_json("pcbd_ability_names_ja.json").items():
    if isinstance(japanese_name, str):
        ability_id = re.sub(r"[^a-z0-9]", "", english_name.lower())
        ABILITY_SHOWDOWN_IDS[english_name] = ability_id
        ABILITY_SHOWDOWN_IDS[japanese_name] = ability_id

ITEM_SHOWDOWN_IDS = _load_json("item_showdown_ids.json")
_ARTWORK_NAMES: dict[str, str] = {}
POKEMON: dict[str, PokemonProfile] = {}

for pokemon_id, names in _NAMES.items():
    form = _FORMS.get(pokemon_id)
    if not isinstance(names, dict) or not isinstance(form, dict):
        continue
    pokemon_name = names.get("name_ja")
    if not isinstance(pokemon_name, str) or not form.get("metadata_row_available"):
        continue
    saved_name = form.get("saved_name")
    _ARTWORK_NAMES[pokemon_name] = saved_name if isinstance(saved_name, str) else ""
    type_names = names.get("type_ja", [])
    localized_type = " / ".join(
        item for item in type_names if isinstance(item, str)
    ) if isinstance(type_names, list) else ""
    POKEMON[pokemon_name] = _LEGACY_POKEMON.get(
        pokemon_name,
        {
            "number": "",
            "type": localized_type,
            "image": "",
            "description": "",
            "color": "#6c8f82",
        },
    )

for pokemon_name, profile in _LEGACY_POKEMON.items():
    POKEMON.setdefault(pokemon_name, profile)


# Mega forms share the species metadata ID with their unevolved form.
_evolution_conflicts: dict[str, set[str]] = {}
_mega_pokemon_names: set[str] = set()
for form_id, form in _FORMS.items():
    showdown_name = form.get("showdown_name") if isinstance(form, dict) else None
    base_id = form.get("metadata_id") if isinstance(form, dict) else None
    mega_names = _NAMES.get(form_id, {})
    base_names = _NAMES.get(base_id, {}) if isinstance(base_id, str) else {}
    mega_name = mega_names.get("name_ja") if isinstance(mega_names, dict) else None
    base_name = base_names.get("name_ja") if isinstance(base_names, dict) else None
    if (
        isinstance(showdown_name, str)
        and "-mega" in showdown_name.lower()
        and isinstance(mega_name, str)
        and mega_name in POKEMON
    ):
        _mega_pokemon_names.add(mega_name)
        if isinstance(base_name, str) and base_name in POKEMON:
            _evolution_conflicts.setdefault(mega_name, set()).add(base_name)
            _evolution_conflicts.setdefault(base_name, set()).add(mega_name)

# Only one Mega form can be selected across the two companion slots.
for mega_name in _mega_pokemon_names:
    _evolution_conflicts.setdefault(mega_name, set()).update(
        _mega_pokemon_names - {mega_name}
    )

EVOLUTION_CONFLICTS = {
    pokemon_name: frozenset(conflicts)
    for pokemon_name, conflicts in _evolution_conflicts.items()
}
MEGA_POKEMON = frozenset(_mega_pokemon_names)


def is_mega_pokemon(pokemon_name: str) -> bool:
    return pokemon_name in MEGA_POKEMON


def pokemon_selection_conflicts(first: str, second: str) -> bool:
    return (
        first != second
        and (
            first in MEGA_POKEMON and second in MEGA_POKEMON
            or second in EVOLUTION_CONFLICTS.get(first, ())
        )
    )


def pokemon_image_url(pokemon_name: str, fallback: str = "") -> str:
    saved_name = _ARTWORK_NAMES.get(pokemon_name)
    if not saved_name:
        return fallback
    return (
        "https://championsbattledata.com/pokemon_champions_assets/pokemon/"
        f"{quote(saved_name, safe='')}.png"
    )
