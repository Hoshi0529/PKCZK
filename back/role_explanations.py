"""Explain build roles using selected moves and qualitative stat comparisons."""


ROLE_DESCRIPTIONS = {
    "物理アタッカー": "こうげきを活かし、物理技で相手にダメージを与える役割です。",
    "特殊アタッカー": "とくこうを活かし、特殊技で相手にダメージを与える役割です。",
    "両刀アタッカー": "物理技と特殊技を使い分け、相手の守り方に合わせて攻める役割です。",
    "物理受け": "相手の物理攻撃を受け止め、継続して対応する役割です。",
    "特殊受け": "相手の特殊攻撃を受け止め、継続して対応する役割です。",
    "両受け": "相手の物理攻撃と特殊攻撃の両方に対応する役割です。",
    "積みアタッカー": "能力を上げてから攻撃し、相手の突破を狙う役割です。",
    "起点作り": "状態異常や場の準備で、後続が有利に戦える状況を作る役割です。",
    "受け崩し": "相手の回復や守りの仕組みに対処し、耐久型のポケモンの突破を狙う役割です。",
    "スイーパー": "素早さを高めるなどして先手を取り、相手を倒していく役割です。",
}
SETUP_MOVE_IDS = {
    "swordsdance", "dragondance", "nastyplot", "calmmind", "bulkup",
    "quiverdance", "shellsmash", "coil", "workup", "growth", "honeclaws",
}
RECOVERY_MOVE_IDS = {
    "recover", "roost", "softboiled", "slackoff", "synthesis", "moonlight",
    "morningsun", "shoreup", "strengthsap", "wish", "rest", "milkdrink",
}
SUPPORT_MOVE_IDS = {
    "stealthrock", "spikes", "toxicspikes", "stickyweb", "reflect", "lightscreen",
    "auroraveil", "tailwind", "partingshot", "memento",
    "thunderwave", "willowisp", "toxic", "spore", "sleeppowder", "yawn",
}
SPEED_MOVE_IDS = {
    "agility", "rockpolish", "autotomize", "dragondance", "quiverdance",
    "shellsmash", "shiftgear", "flamecharge", "trailblaze", "scaleshot", "tailwind",
}
WALLBREAK_MOVE_IDS = {"taunt", "encore", "trick", "switcheroo", "knockoff"}
ATTACK_KINDS = {"fixed", "variable", "damage_or_heal"}


def _move_names(moves: list[dict]) -> str:
    return "・".join(f"「{move['name_ja']}」" for move in moves)


def role_reason(role: str, primary: dict, moves: list[dict], *, has_attack: bool) -> str:
    """Avoid reproducing numeric stats, item names, or ability names in chat."""
    attacks = [move for move in moves if move.get("power_kind") in ATTACK_KINDS]
    stats = primary.get("actual_stats", {})
    if role in {"物理アタッカー", "特殊アタッカー"} and attacks:
        higher, lower = ("こうげき", "とくこう") if role == "物理アタッカー" else ("とくこう", "こうげき")
        if isinstance(stats.get(higher), (int, float)) and isinstance(stats.get(lower), (int, float)) and stats[higher] > stats[lower]:
            tendency = "物理火力" if role == "物理アタッカー" else "特殊火力"
            return f"{tendency}を活かしやすい能力の傾向があり、{_move_names(attacks)}などの攻撃技を採用しているためです。"
    groups = {
        "積みアタッカー": (SETUP_MOVE_IDS, "能力を高めてから攻める"),
        "起点作り": (SUPPORT_MOVE_IDS, "後続が動きやすい状況を作る"),
        "受け崩し": (WALLBREAK_MOVE_IDS, "相手の守り方に干渉して突破を狙う"),
        "スイーパー": (SPEED_MOVE_IDS, "先手を取れる状況を作って攻める"),
        "物理受け": (RECOVERY_MOVE_IDS, "回復しながら相手に対応する"),
        "特殊受け": (RECOVERY_MOVE_IDS, "回復しながら相手に対応する"),
        "両受け": (RECOVERY_MOVE_IDS, "回復しながら継続して場に残る"),
    }
    ids, purpose = groups.get(role, (set(), ""))
    supporting = [move for move in moves if move.get("move_id") in ids]
    if supporting and (role not in {"積みアタッカー", "スイーパー"} or has_attack):
        return f"{_move_names(supporting)}を採用しているため、{purpose}使い方が考えられます。"
    if role in {"物理受け", "特殊受け"}:
        higher, lower = ("ぼうぎょ", "とくぼう") if role == "物理受け" else ("とくぼう", "ぼうぎょ")
        if isinstance(stats.get(higher), (int, float)) and isinstance(stats.get(lower), (int, float)) and stats[higher] > stats[lower]:
            tendency = "物理側" if role == "物理受け" else "特殊側"
            return f"{tendency}の耐久を活かしやすい能力の傾向を考慮した候補です。継続して受けられるかは、技構成や対戦相手を確認する必要があります。"
    return "入力された型から、この役割の根拠を十分に確認できないため、暫定の候補です。"
