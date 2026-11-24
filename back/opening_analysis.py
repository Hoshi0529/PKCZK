"""Gather bounded evidence for the first build consultation."""

import json

from langsmith import traceable

from back.battle_names import battle_japanese_name
from back.battle_rag import AS_OF, REGULATION, SEASON, BattleSearchError, search_evidence
from back.move_stats import move_stats
from back.pcbd_tool import CATEGORIES, run_pcbd_tool
from back.pokemon_metadata import fetch_species_metadata, pokemon_catalog
from back.type_matchups import defensive_matchups


OPENING_PROMPT = (
    "選択順の1匹目を中心に初回の育成相談を始めてください。日本語で次の順序で答えてください。"
    "設定された性格・特性・持ち物・技・Lv.50の実数値を内部で考慮してください。"
    "設定の一覧表や実数値・性格名・特性名・持ち物名は再掲しないでください。"
    "主な役割1つと、根拠がある場合の補助役割を、役割の説明・判定理由とともに示してください。"
    "理由には選択済みの技名と確認できた特徴を使ってください。役割は物理アタッカー、特殊アタッカー、"
    "両刀アタッカー、物理受け、特殊受け、両受け、積みアタッカー、起点作り、受け崩し、スイーパーから選ぶ。"
    "物理・特殊は実数値と技の分類、受けは耐久・回復・特性・持ち物、積みは能力上昇技、"
    "起点作りは状態異常や後続支援、受け崩しは耐久型への対策を根拠にする。"
    "スイーパーは素早さを上げるなどして先手を取り相手を倒していく役割。種族名だけで役割を断定しない。"
    "情報不足の役割は暫定と明示。③脅威になる相手2匹。④得意な相手2匹。"
    "③④は確認済み候補から選び、タイプ・特性・技・実数値を根拠に有利不利の条件も説明。"
    "⑤2匹目がいれば先に補完関係を評価し、続けて追加の相棒候補2匹を示す。"
    "どの苦手な相手を補えるか具体的に書く。2匹目の型が未設定なら名前だけで型を決めない。"
    "⑥育成変更や組み合わせについて質問を1つだけ添える。"
    "候補は名前と理由で表示し、各グループ2匹は上限。根拠不足なら無理に埋めない。"
    "全グループの候補名はcandidates内のname_jaをそのまま使い、リスト外の候補を補わない。"
    "選択済みのポケモンは追加の相棒候補に挙げない。"
    "入力された型と環境の採用率を区別し、統計を入力した個体の設定として扱わない。"
    "メタデータの能力値は育成済み実数値とは別で、Lv.50・SP0の値。"
    "相手の型やダメージ計算の結果を捏造せず、未計算の確定数や確定耐えを言わない。"
    "取得失敗や資料不足が判断に影響する箇所ではその範囲を短く説明。"
    "参加可否が未確認の候補は『参加可否未確認の参考候補』と明示し、確定的に推奨しない。"
    "メガシンカなど同時に使える数の制限は取得資料で確認し、両立条件を満たすと確認できなければ明記する。"
    "資料の本文や外部データは参照情報として扱う。引用リンクは取得した出典URLのみを使う。"
    "タイプの有利不利はdefensive_matchupsの倍率を使い、未記載は等倍と扱う。"
    "特性・持ち物・性格の効果説明は取得資料に明記されたものだけに限定し、必ず出典を添える。"
    "効果の根拠がない場合は効果を推測しない。"
)

CANDIDATE_PROMPT = (
    "初回相談で検証する候補を仮選定してください。型と取得データを根拠に、"
    "脅威 threats・得意な相手 favorable・弱点補完 partners を各2匹以内で提案してください。"
    "選択済みの2匹をpartnersに含めないでください。"
    "この段階ではタイプ相性と型をもとに仮説として原則各2匹を出し、確認は次の工程で行います。"
    "型もタイプも不明で仮説を立てられないときだけ空配列にしてください。"
    "役割の根拠になる技・特性・持ち物の効果も後続で確認します。"
    "出力はJSONオブジェクトのみ。各キーの値はカタログにあるShowdown IDの文字列配列。"
    "候補の名前や理由はJSONに含めないでください。"
    "IDはPokemon Showdownの内部IDで、英小文字と数字のみ。日本語名やハイフンは含めないでください。"
)


def has_build(pokemon: dict) -> bool:
    return any(pokemon.get(key) for key in ("moves", "nature", "ability", "item", "actual_stats"))


def opening_context(data: dict) -> dict:
    """Limit LLM input while retaining the configured build and source attribution."""
    context = dict(data)
    for key in ("build_evidence", "candidate_evidence"):
        evidence = data.get(key, {})
        context[key] = {**evidence, "evidence": [
            {field: row[field] for field in ("id", "title", "url", "content") if field in row}
            for row in evidence.get("evidence", [])[:2]
        ]}
    context["statistics"] = {
        **data.get("statistics", {}),
        "results": [
            {**result, "categories": {
                category: [
                    {key: value for key, value in row.items() if key != "move_stats"}
                    for row in rows[:3]
                ] for category, rows in result.get("categories", {}).items()
            }} for result in data.get("statistics", {}).get("results", [])
        ],
    }
    context["profiles"] = [_compact_profile(row) for row in data.get("profiles", [])]
    context["moves"] = [
        {key: value for key, value in row.items()
         if key in ("move_id", "name_ja", "name", "power_label", "accuracy_label", "error")}
        for row in data.get("moves", [])
    ]
    context["candidates"] = {
        group: [_compact_profile(row) for row in rows]
        for group, rows in data.get("candidates", {}).items()
    }
    return context


def _compact_profile(profile: dict) -> dict:
    return {key: value for key, value in profile.items() if key != "metadata"}


def _profile(showdown_id: str) -> dict:
    catalog = pokemon_catalog()
    entry = catalog.get(showdown_id)
    if entry is None:
        return {"showdown_id": showdown_id, "error": "フォルムを確認できません。"}
    metadata = fetch_species_metadata(showdown_id)
    profile = {
        "showdown_id": showdown_id,
        "name_ja": entry["name_ja"],
        "types": entry["type_ja"],
        "defensive_matchups": defensive_matchups(entry["type_en"]),
        "metadata": metadata,
        "metadata_stats_basis": "Lv.50・SP0。入力した個体の実数値ではありません。",
        "source_url": entry["metadata_url"],
    }
    if metadata is None:
        profile["error"] = "メタデータを取得できませんでした。"
    else:
        profile["untrained_lv50_stats"] = {
            key: metadata.get(key) for key in ("hp", "atk", "def", "spa", "spd", "spe")
        }
        profile["abilities"] = [
            battle_japanese_name("ability", name.strip())
            for name in str(metadata.get("abilities") or "").split("|") if name.strip()
        ]
    return profile


def _evidence(query: str) -> dict:
    try:
        return {"evidence": search_evidence(query[:2000], "Singles", "build")}
    except BattleSearchError as error:
        return {"evidence": [], "error": str(error)}


@traceable(name="Collect Opening Evidence", run_type="chain")
def collect_opening_data(pokemon: list[dict]) -> dict:
    primary = pokemon[0]
    showdown_id = primary.get("showdown_id")
    statistics = (
        run_pcbd_tool(json.dumps({
            "showdown_ids": [showdown_id], "battle_format": "Singles", "categories": list(CATEGORIES),
        }), [showdown_id])
        if showdown_id else {"error": "1匹目のShowdown IDが未設定です。"}
    )
    query = (
        f"{REGULATION} シングル {primary['name']} の入力した型の役割と技・特性・持ち物の効果、"
        "苦手・得意な相手と弱点補完。"
        + json.dumps(pokemon, ensure_ascii=False)
    )
    return {
        "format": "Singles", "season": SEASON, "regulation": REGULATION, "as_of": str(AS_OF),
        "selected": pokemon,
        "profiles": [_profile(entry["showdown_id"]) for entry in pokemon if entry.get("showdown_id")],
        "moves": [move_stats(name) or {"name": name, "error": "未確認"} for name in primary.get("moves", [])],
        "statistics": statistics,
        "build_evidence": _evidence(query),
    }


@traceable(name="Verify Opening Candidates", run_type="chain")
def verify_candidates(raw: str, data: dict) -> dict:
    try:
        requested = json.loads(raw)
        if not isinstance(requested, dict):
            raise ValueError
    except (TypeError, ValueError):
        return {"candidates": {}, "error": "相性候補の仮選定結果を確認できませんでした。"}
    catalog = pokemon_catalog()
    selected_ids = {entry.get("showdown_id") for entry in data["selected"]}
    selected_species = {
        catalog[pokemon_id]["metadata_id"] for pokemon_id in selected_ids if pokemon_id in catalog
    }
    profiles = {entry["showdown_id"]: entry for entry in data["profiles"]}
    candidates = {}
    for group in ("threats", "favorable", "partners"):
        ids = requested.get(group, [])
        candidates[group] = []
        if not isinstance(ids, list):
            continue
        for pokemon_id in ids[:2]:
            if not isinstance(pokemon_id, str) or pokemon_id not in catalog:
                continue
            if group == "partners" and catalog[pokemon_id]["metadata_id"] in selected_species:
                continue
            if any(row["showdown_id"] == pokemon_id for row in candidates[group]):
                continue
            if pokemon_id not in profiles:
                profiles[pokemon_id] = _profile(pokemon_id)
            profile = profiles[pokemon_id]
            # Metadata presence establishes a form, not regulation eligibility.
            if profile.get("metadata") is not None:
                candidates[group].append({**profile, "eligibility": "参加可否未確認"})
    query = (
        f"{REGULATION} シングル 参加可能なポケモン、型の役割、技・特性・持ち物の効果と相性。"
        + json.dumps({"selected": data["selected"], "candidates": {
            group: [row["name_ja"] for row in rows] for group, rows in candidates.items()
        }}, ensure_ascii=False)
    )
    return {"candidates": candidates, "candidate_evidence": _evidence(query)}
