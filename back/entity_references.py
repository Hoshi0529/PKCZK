"""Resolve move, ability and item IDs before chat text reaches the user."""

from functools import lru_cache
import json
from pathlib import Path
import re
from unicodedata import normalize


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
ENTITY_PROMPT = (
    "ユーザーに見せる文章・見出し・表の中の技名・特性名・持ち物名は、"
    "必ずShowdown IDの参照記号で返してください。"
    "技は {{move:shadowsneak}}、特性は {{ability:disguise}}、持ち物は {{item:lifeorb}} の形式です。"
    "日本語名・英語名・英語をカタカナにした名前を自分で書かず、説明文中の名前にも参照記号を使ってください。"
    "IDは英小文字と数字のみで、参照記号の途中に改行を入れないでください。"
    "ID専用のJSONフィールドやツール引数には参照記号を付けず、通常のIDを返してください。"
    "参照記号の種類はmove・ability・itemの3種類です。ポケモン名は通常の日本語で書いてください。"
    "質問に出た名称の対応表がある場合は、そのIDを必ず使い、名前から別のIDを推測しないでください。"
    "名称はアプリが辞書で置き換えます。未確認の効果や採用率、出典を作らないでください。"
)
KINDS = {"move": "技名未登録", "ability": "特性名未登録", "item": "持ち物名未登録"}
REFERENCE = re.compile(r"\{\{([a-z_]+):([^{}]*)\}\}", re.IGNORECASE)
PROTECTED = re.compile(
    r"\x60{3}[\s\S]*?(?:\x60{3}|\Z)|https?://[^\s<>\]\)]+|\x60[^\x60]*\x60",
    re.IGNORECASE,
)


def _key(value: str) -> str:
    return normalize("NFKC", value).strip().casefold()


def _id(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _key(value))


def _read(filename: str) -> dict:
    try:
        with (DATA_DIR / filename).open(encoding="utf-8-sig") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


@lru_cache(maxsize=1)
def _catalogs() -> tuple[dict, dict]:
    catalogs = {kind: {} for kind in KINDS}
    aliases = {kind: {} for kind in KINDS}
    for move_id, row in _read("move_names_ja_en.json").items():
        if isinstance(row, dict) and isinstance(row.get("name_ja"), str) and row["name_ja"]:
            catalogs["move"][move_id] = row["name_ja"]
            for name in (move_id, row["name_ja"], row.get("name_en")):
                if isinstance(name, str) and name:
                    aliases["move"][_key(name)] = move_id
    for english, japanese in _read("pcbd_ability_names_ja.json").items():
        if isinstance(japanese, str) and japanese:
            ability_id = _id(english)
            catalogs["ability"][ability_id] = japanese
            for name in (english, japanese, ability_id):
                aliases["ability"][_key(name)] = ability_id
    for japanese, item_id in _read("item_showdown_ids.json").items():
        if isinstance(item_id, str) and item_id:
            catalogs["item"][item_id] = japanese
            for name in (japanese, item_id):
                aliases["item"][_key(name)] = item_id
    return catalogs, aliases


def entity_id(kind: str, value: str) -> str | None:
    catalogs, aliases = _catalogs()
    known = aliases.get(kind, {}).get(_key(value))
    normalized = _id(value)
    return known or (normalized if normalized in catalogs.get(kind, {}) else None)


def entity_name(kind: str, showdown_id: str) -> str:
    if kind in {"pokemon", "showdown_id"}:
        row = _pokemon_names().get(showdown_id, {})
        return row.get("name_ja") or "ポケモン名未登録"
    if not re.fullmatch(r"[a-z0-9]+", showdown_id):
        return KINDS.get(kind, "名称未登録")
    return _catalogs()[0].get(kind, {}).get(showdown_id) or KINDS.get(kind, "名称未登録")


@lru_cache(maxsize=1)
def _pokemon_names() -> dict:
    return _read("pokemon_champions_names_all_forms.json")


@lru_cache(maxsize=1)
def _mention_pattern() -> re.Pattern:
    names = set().union(*(entries.keys() for entries in _catalogs()[1].values()))
    return re.compile(
        r"(?<![a-z0-9_])(?:" + "|".join(re.escape(name) for name in sorted(names, key=len, reverse=True))
        + r")(?![a-z0-9_])", re.IGNORECASE,
    )


def mentioned_entities(question: str) -> list[dict]:
    from back.move_stats import move_stats

    references = {}
    question = normalize("NFKC", question)
    matches = [
        match for pattern in (_mention_pattern(), _alias_pattern()[0])
        for match in pattern.finditer(question)
    ]
    for match in sorted(matches, key=lambda item: item.start()):
        for kind in KINDS:
            showdown_id = entity_id(kind, match.group())
            if showdown_id is None or (kind, showdown_id) in references:
                continue
            entry = {
                "kind": kind, "id": showdown_id, "name_ja": entity_name(kind, showdown_id),
                "reference": "{{" + kind + ":" + showdown_id + "}}",
            }
            if kind == "move":
                entry["move_stats"] = move_stats(showdown_id)
            references[kind, showdown_id] = entry
            if len(references) == 20:
                return list(references.values())
    return list(references.values())


@lru_cache(maxsize=1)
def _alias_pattern() -> tuple[re.Pattern, dict]:
    catalogs, aliases = _catalogs()
    names = {}
    for kind, entries in aliases.items():
        for name, showdown_id in entries.items():
            if name.isascii() and re.search(r"[a-z]", name):
                names.setdefault(name, entity_name(kind, showdown_id))
    patterns = [re.escape(name) for name in sorted(names, key=len, reverse=True)]
    # The item dictionary contains IDs, so also accept spaced English spellings.
    for item_id in catalogs["item"]:
        patterns.append(r"[\s'’-]*".join(re.escape(char) for char in item_id))
    return re.compile(r"(?<![a-z0-9_])(?:" + "|".join(patterns) + r")(?![a-z0-9_])", re.IGNORECASE), names


def _localize_plain(text: str) -> str:
    pattern, names = _alias_pattern()

    def replace(match):
        value = match.group()
        known = names.get(_key(value))
        if known:
            return known
        item_id = entity_id("item", value)
        return entity_name("item", item_id) if item_id else value

    return pattern.sub(replace, text)


def _resolve_references(text: str) -> str:
    return REFERENCE.sub(lambda match: entity_name(match[1].lower(), match[2].strip()), text)


def localize_entities(text: str) -> str:
    text = _resolve_references(text)
    text = re.sub(r"\{\{[^\n]*$", "名称を確認できませんでした", text)
    parts = []
    start = 0
    for match in PROTECTED.finditer(text):
        parts.extend((_localize_plain(text[start:match.start()]), match.group()))
        start = match.end()
    parts.append(_localize_plain(text[start:]))
    return "".join(parts)


class EntityTextStream:
    """Buffer a line so split reference markers never appear on screen."""

    def __init__(self, emit):
        self.emit = emit
        self.buffer = ""
        self.parts = []
        self.received = False
        self.fenced = False

    def _write(self, text: str) -> None:
        fence = text.lstrip().startswith("\x60\x60\x60")
        rendered = _resolve_references(text) if self.fenced or fence else localize_entities(text)
        if fence and text.count("\x60\x60\x60") % 2:
            self.fenced = not self.fenced
        self.parts.append(rendered)
        self.emit(rendered)

    def feed(self, chunk: str) -> None:
        self.received = True
        self.buffer += chunk
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            self._write(line + "\n")

    def finish(self, fallback: str = "") -> str:
        if not self.received and fallback:
            self.feed(fallback)
        if self.buffer:
            self._write(self.buffer)
            self.buffer = ""
        return "".join(self.parts)
