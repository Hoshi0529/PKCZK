"""Build the local move-option JSON from PCBD's current Singles CSV files."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "learnable_moves.json"
BASE_URL = "https://championsbattledata.com/pokemon_champions_assets/battle_data/Singles"
POKEMON = {
    "ピカチュウ": "Pikachu",
    "ガブリアス": "Garchomp",
    "マリル": "Marill",
    "ルカリオ": "Lucario",
    "イーブイ": "Eevee",
}


def fetch_moves(csv_name: str) -> list[str]:
    request = Request(f"{BASE_URL}/{csv_name}.csv", headers={"User-Agent": "pokecham/1.0"})
    with urlopen(request, timeout=20) as response:
        text = response.read().decode("utf-8-sig")
    moves: list[str] = []
    for row in csv.DictReader(text.splitlines()):
        if row.get("category", "").casefold() == "move" and row.get("name"):
            name = row["name"].strip()
            if name and name not in moves:
                moves.append(name)
    return moves


def main() -> None:
    data = {name: fetch_moves(csv_name) for name, csv_name in POKEMON.items()}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps({"source": "PCBD Singles CSV", "pokemon": data}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Saved Singles move options for {len(data)} Pokémon to {OUTPUT}")


if __name__ == "__main__":
    main()
