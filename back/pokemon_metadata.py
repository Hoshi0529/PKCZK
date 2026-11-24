"""Shared, form-aware access to PCBD species metadata."""

from functools import lru_cache
import json
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from langsmith import traceable

from back.champions_battle_data import API_BASE


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@lru_cache(maxsize=1)
def pokemon_catalog() -> dict[str, dict]:
    try:
        with (DATA_DIR / "pokemon_champions_names_all_forms.json").open(encoding="utf-8") as file:
            names = json.load(file)
        with (DATA_DIR / "pcbd_forms.json").open(encoding="utf-8") as file:
            forms = json.load(file)
    except (OSError, ValueError):
        return {}
    if not isinstance(names, dict) or not isinstance(forms, dict):
        return {}
    return {
        pokemon_id: {**entry, **forms[pokemon_id]}
        for pokemon_id, entry in names.items()
        if isinstance(entry, dict)
        and isinstance(forms.get(pokemon_id), dict)
        and forms[pokemon_id].get("metadata_row_available")
    }


@traceable(name="PCBD Pokémon Metadata", run_type="tool")
def fetch_species_metadata(showdown_id: str) -> dict | None:
    form = pokemon_catalog().get(showdown_id)
    if not form:
        return None
    request = Request(
        f"{API_BASE}/metadata/{form['metadata_id']}",
        headers={"Accept": "application/json", "User-Agent": "pokecham/1.0"},
    )
    try:
        with urlopen(request, timeout=8) as response:
            payload = json.load(response)
    except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    rows = payload.get("rows", []) if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        return None
    return next(
        (row for row in rows if isinstance(row, dict) and row.get("saved_name") == form["saved_name"]),
        None,
    )
