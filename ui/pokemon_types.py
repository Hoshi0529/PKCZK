"""Shared type definitions for the PokemonDetail screen and its data."""

from typing import Literal, TypedDict, TypeAlias


StatName: TypeAlias = Literal[
    "HP",
    "こうげき",
    "ぼうぎょ",
    "とくこう",
    "とくぼう",
    "すばやさ",
]

StatPointValues: TypeAlias = dict[StatName, int]
STAT_NAMES: tuple[StatName, ...] = ("HP", "こうげき", "ぼうぎょ", "とくこう", "とくぼう", "すばやさ")
# Compatibility alias for callers that still use the old EV-oriented name.
EffortValues: TypeAlias = StatPointValues


class PokemonProfile(TypedDict):
    number: str
    type: str
    image: str
    description: str
    color: str


class PokemonSpecies(TypedDict):
    """Selectable data for a species; base_stats contains six values in stat order."""

    base_stats: list[int]
    abilities: list[str]
    moves: list[str]


class PokemonBuild(TypedDict, total=False):
    """Saved build values; fields can be absent while a build is being drafted."""

    nature: str
    ability: str
    item: str
    stat_points: StatPointValues
    actual_stats: dict[StatName, int]
    effort: EffortValues  # Legacy EV field, migrated when the build is loaded.
    moves: list[str]


PokemonBuildMap: TypeAlias = dict[str, PokemonBuild]
