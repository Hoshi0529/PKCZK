"""Local Pokémon profiles and the artwork used by selection and chat."""

import json
from pathlib import Path
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


def pokemon_image_url(pokemon_name: str, fallback: str = "") -> str:
    saved_name = _ARTWORK_NAMES.get(pokemon_name)
    if not saved_name:
        return fallback
    return (
        "https://championsbattledata.com/pokemon_champions_assets/pokemon/"
        f"{quote(saved_name, safe='')}.png"
    )
