"""Standard type effectiveness for form-specific defensive comparisons."""


# Each attacking type lists defending types receiving double, half, or no damage.
TYPE_MATCHUPS = {
    "normal": ("", "rock steel", "ghost"),
    "fire": ("grass ice bug steel", "fire water rock dragon", ""),
    "water": ("fire ground rock", "water grass dragon", ""),
    "electric": ("water flying", "electric grass dragon", "ground"),
    "grass": ("water ground rock", "fire grass poison flying bug dragon steel", ""),
    "ice": ("grass ground flying dragon", "fire water ice steel", ""),
    "fighting": ("normal ice rock dark steel", "poison flying psychic bug fairy", "ghost"),
    "poison": ("grass fairy", "poison ground rock ghost", "steel"),
    "ground": ("fire electric poison rock steel", "grass bug", "flying"),
    "flying": ("grass fighting bug", "electric rock steel", ""),
    "psychic": ("fighting poison", "psychic steel", "dark"),
    "bug": ("grass psychic dark", "fire fighting poison flying ghost steel fairy", ""),
    "rock": ("fire ice flying bug", "fighting ground steel", ""),
    "ghost": ("psychic ghost", "dark", "normal"),
    "dragon": ("dragon", "steel", "fairy"),
    "dark": ("psychic ghost", "fighting dark fairy", ""),
    "steel": ("ice rock fairy", "fire water electric steel", ""),
    "fairy": ("fighting dragon dark", "fire poison steel", ""),
}
TYPE_NAMES = dict(zip(
    TYPE_MATCHUPS,
    ("ノーマル", "ほのお", "みず", "でんき", "くさ", "こおり", "かくとう", "どく", "じめん",
     "ひこう", "エスパー", "むし", "いわ", "ゴースト", "ドラゴン", "あく", "はがね", "フェアリー"),
))


def defensive_matchups(types: list[str]) -> dict:
    if not types or any(pokemon_type not in TYPE_MATCHUPS for pokemon_type in types):
        return {"error": "タイプ相性を確認できません。"}
    result = {}
    for attacking, (double, half, immune) in TYPE_MATCHUPS.items():
        multiplier = 1
        for defending in types:
            if defending in immune.split():
                multiplier = 0
            elif defending in double.split():
                multiplier *= 2
            elif defending in half.split():
                multiplier *= 0.5
        if multiplier != 1:
            result[TYPE_NAMES[attacking]] = multiplier
    return {"multipliers": result, "basis": "タイプのみ。未記載は等倍。特性・技・持ち物の効果は含まない。"}
