import json
import re
from html import escape
from pathlib import Path
from typing import cast
from urllib.error import URLError
from urllib.request import Request, urlopen

import streamlit as st

from back.champions_battle_data import BattleDataResponse, BattleRow, rows_for_category
from back.conversations import ConversationError, ConversationStore
from ui.chat_session import open_conversation, remember_selected_pokemon, require_conversation_store
from ui.battle_data import API_ATTRIBUTION, SHOWDOWN_IDS, get_battle_data
from ui.layout import configure_page
from ui.sidebar import render_sidebar
from ui.pokemon_types import (
    PokemonBuild,
    PokemonBuildMap,
    PokemonProfile,
    PokemonSpecies,
    StatName,
    StatPointValues,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _read_json(filename: str) -> dict:
    try:
        with (DATA_DIR / filename).open(encoding="utf-8") as file:
            result = json.load(file)
        return result if isinstance(result, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


POKEMON_NAMES = _read_json("pokemon_champions_names_all_forms.json")
PCBD_FORMS = _read_json("pcbd_forms.json")
POKEMON_MOVES = _read_json("pokemon_moves.json")
MOVE_NAMES = _read_json("move_names_ja_en.json")
ABILITY_NAMES_JA = _read_json("pcbd_ability_names_ja.json")
POKEMON_ID_BY_NAME = {
    names.get("name_ja"): pokemon_id
    for pokemon_id, names in POKEMON_NAMES.items()
    if isinstance(names, dict)
    and isinstance(names.get("name_ja"), str)
    and isinstance(PCBD_FORMS.get(pokemon_id), dict)
    and PCBD_FORMS[pokemon_id].get("metadata_row_available")
}


SPECIES: dict[str, PokemonSpecies] = {
    "ピカチュウ": {
        "base_stats": [35, 55, 40, 50, 50, 90],
        "abilities": ["せいでんき", "ひらいしん"],
        "moves": ["10まんボルト", "かみなり", "でんこうせっか", "くさむすび", "なみのり", "アンコール", "でんじは"],
    },
    "ガブリアス": {
        "base_stats": [108, 130, 95, 80, 85, 102],
        "abilities": ["すながくれ", "さめはだ"],
        "moves": ["じしん", "げきりん", "ドラゴンクロー", "ストーンエッジ", "どくづき", "つるぎのまい", "ステルスロック", "ほのおのキバ"],
    },
    "マリル": {
        "base_stats": [70, 20, 50, 20, 50, 40],
        "abilities": ["あついしぼう", "ちからもち", "そうしょく"],
        "moves": ["アクアブレイク", "じゃれつく", "アクアジェット", "ばかぢから", "はたきおとす", "れいとうパンチ", "はらだいこ", "アンコール"],
    },
    "ルカリオ": {
        "base_stats": [70, 110, 70, 115, 70, 90],
        "abilities": ["ふくつのこころ", "せいしんりょく", "せいぎのこころ"],
        "moves": ["インファイト", "はどうだん", "しんそく", "ラスターカノン", "バレットパンチ", "つるぎのまい", "れいとうパンチ", "じしん"],
    },
    "イーブイ": {
        "base_stats": [55, 55, 50, 45, 65, 55],
        "abilities": ["にげあし", "てきおうりょく", "きけんよち"],
        "moves": ["すてみタックル", "でんこうせっか", "あくび", "まもる", "バトンタッチ", "ねがいごと", "とっておき", "のしかかり"],
    },
}

STAT_NAMES: list[StatName] = ["HP", "こうげき", "ぼうぎょ", "とくこう", "とくぼう", "すばやさ"]
NATURES = [
    "指定なし", "さみしがり", "いじっぱり", "やんちゃ", "ゆうかん",
    "ずぶとい", "わんぱく", "のうてんき", "のんき",
    "ひかえめ", "おっとり", "うっかりや", "れいせい",
    "おだやか", "おとなしい", "しんちょう", "なまいき",
    "おくびょう", "せっかち", "ようき", "むじゃき",
    "がんばりや", "きまぐれ", "すなお", "てれや", "まじめ",
]
ITEMS = ["指定しない", "きあいのタスキ", "いのちのたま", "こだわりハチマキ", "こだわりスカーフ", "こだわりメガネ", "たべのこし", "オボンのみ", "とつげきチョッキ"]
NATURE_MODIFIERS: dict[str, tuple[StatName, StatName]] = {
    "さみしがり": ("こうげき", "ぼうぎょ"),
    "いじっぱり": ("こうげき", "とくこう"),
    "やんちゃ": ("こうげき", "とくぼう"),
    "ゆうかん": ("こうげき", "すばやさ"),
    "のうてんき": ("ぼうぎょ", "とくぼう"),
    "のんき": ("ぼうぎょ", "すばやさ"),
    "ようき": ("すばやさ", "とくこう"),
    "ひかえめ": ("とくこう", "こうげき"),
    "おっとり": ("とくこう", "ぼうぎょ"),
    "うっかりや": ("とくこう", "とくぼう"),
    "れいせい": ("とくこう", "すばやさ"),
    "おくびょう": ("すばやさ", "こうげき"),
    "ずぶとい": ("ぼうぎょ", "こうげき"),
    "しんちょう": ("とくぼう", "とくこう"),
    "わんぱく": ("ぼうぎょ", "とくこう"),
    "おだやか": ("とくぼう", "こうげき"),
    "おとなしい": ("とくぼう", "ぼうぎょ"),
    "なまいき": ("とくぼう", "すばやさ"),
    "むじゃき": ("すばやさ", "とくぼう"),
    "せっかち": ("すばやさ", "ぼうぎょ"),
}


def _category_rows(
    battle_data: BattleDataResponse | None, category: str
) -> list[BattleRow]:
    return rows_for_category(battle_data, category) if battle_data else []


def _options_from_api(rows: list[BattleRow]) -> list[str]:
    return list(dict.fromkeys(row["name"] for row in rows if row.get("name")))


def _load_local_options(filename: str, key: str) -> list[str]:
    try:
        with (DATA_DIR / filename).open(encoding="utf-8") as file:
            return cast(list[str], json.load(file)[key])
    except (OSError, KeyError, json.JSONDecodeError, TypeError):
        return []


def _showdown_id_for_name(pokemon_name: str) -> str | None:
    return POKEMON_ID_BY_NAME.get(pokemon_name)


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def _fetch_species_metadata(pokemon_name: str) -> dict[str, object] | None:
    showdown_id = _showdown_id_for_name(pokemon_name)
    form = PCBD_FORMS.get(showdown_id) if showdown_id else None
    if not isinstance(form, dict) or not form.get("metadata_row_available"):
        return None
    metadata_name = form.get("metadata_id")
    if not isinstance(metadata_name, str) or not metadata_name:
        return None
    request = Request(
        f"https://championsbattledata.com/api/metadata/{metadata_name}",
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
    row = next(
        (
            item
            for item in rows
            if isinstance(item, dict)
            and item.get("saved_name") == form.get("saved_name")
        ),
        None,
    )
    return row if isinstance(row, dict) else None


def _metadata_abilities(metadata: dict[str, object] | None, fallback: list[str]) -> list[str]:
    raw = metadata.get("abilities") if metadata else None
    if isinstance(raw, str) and raw:
        return [
            ABILITY_NAMES_JA.get(name.strip(), name.strip())
            for name in raw.split("|")
            if name.strip()
        ]
    return fallback


def _metadata_stats(metadata: dict[str, object] | None, fallback: list[int]) -> list[int]:
    if not metadata:
        return fallback
    keys = ("hp", "atk", "def", "spa", "spd", "spe")
    values = [metadata.get(key) for key in keys]
    if not all(isinstance(value, (int, float)) for value in values):
        return fallback

    # PCBD metadata stores level-50 stats with max-equivalent IVs and zero SP,
    # while this screen displays species base stats and calculates actual stats
    # separately. Undo the level-50 offsets before using metadata as base stats.
    level_50_offsets = (75, 20, 20, 20, 20, 20)
    return [int(value) - offset for value, offset in zip(values, level_50_offsets)]


def _local_moves(pokemon_name: str, fallback: list[str]) -> list[str]:
    showdown_id = _showdown_id_for_name(pokemon_name)
    moves = POKEMON_MOVES.get(showdown_id, []) if showdown_id else []
    if not isinstance(moves, list) or not moves:
        return fallback
    localized: list[str] = []
    for move_id in moves:
        move_info = MOVE_NAMES.get(move_id)
        if isinstance(move_info, dict):
            name = move_info.get("name_ja") or move_info.get("name_en")
        else:
            name = None
        if isinstance(name, str) and name and name not in localized:
            localized.append(name)
    return localized or fallback


def _format_options(rows: list[BattleRow]):
    usage = {
        row["name"]: row.get("percentage", "")
        for row in rows
        if row.get("name")
    }
    return lambda name: f"{name}　{usage[name]}" if usage.get(name) else name


def _load_stat_points(saved: PokemonBuild) -> StatPointValues:
    if "stat_points" in saved:
        points = saved.get("stat_points", {})
        return {
            stat: min(32, max(0, int(points.get(stat, 0))))
            for stat in STAT_NAMES
        }

    # Earlier versions stored mainline EVs in multiples of four.
    legacy_evs = saved.get("effort", {})
    return {
        stat: min(
            32,
            1 + max(0, (int(legacy_evs.get(stat, 0)) - 4) // 8)
            if int(legacy_evs.get(stat, 0)) > 0
            else 0,
        )
        for stat in STAT_NAMES
    }


def _calculate_champions_stats(
    base_stats: list[int], stat_points: StatPointValues, nature: str
) -> dict[StatName, int]:
    """Calculate level-50 Champions stats with max-equivalent IVs fixed."""
    modifier = NATURE_MODIFIERS.get(nature)
    raised_stat = modifier[0] if modifier else None
    lowered_stat = modifier[1] if modifier else None
    actual_stats: dict[StatName, int] = {}
    for stat_name, base_value in zip(STAT_NAMES, base_stats):
        points = stat_points.get(stat_name, 0)
        # At level 50, fixed max-equivalent IVs simplify to base + 75 + SP.
        if stat_name == "HP":
            actual_stats[stat_name] = base_value + 75 + points
            continue

        # Other stats simplify to base + 20 + SP before the nature modifier.
        neutral_value = base_value + 20 + points
        if stat_name == raised_stat:
            actual_stats[stat_name] = neutral_value * 11 // 10
        elif stat_name == lowered_stat:
            actual_stats[stat_name] = neutral_value * 9 // 10
        else:
            actual_stats[stat_name] = neutral_value
    return actual_stats


def _key(pokemon_name: str, field: str) -> str:
    slug = re.sub(r"\W+", "_", pokemon_name)
    return f"pokemon_build_{slug}_{field}"


def _adjust_stat_point(key: str, amount: int) -> None:
    current = int(st.session_state.get(key, 0))
    st.session_state[key] = min(32, max(0, current + amount))


@st.fragment
def _render_stat_points_editor(
    pokemon_name: str,
    base_stats: list[int],
    nature: str,
    saved_stats: StatPointValues,
) -> tuple[StatPointValues, int]:
    st.markdown(
        '<div class="build-section-title">能力ポイント '
        '<span class="count-pill">Stat Points (SP)</span></div>',
        unsafe_allow_html=True,
    )
    st.caption("実数値はLv.50基準・個体値は最高相当で固定して計算します。")
    column_widths = [0.17, 0.43, 0.17, 0.23]
    stat_header_cols = st.columns(column_widths, vertical_alignment="center")
    for column, title in zip(stat_header_cols, ("能力", "SP", "種族値", "実数値")):
        with column:
            st.markdown(f'<div class="stat-table-header">{title}</div>', unsafe_allow_html=True)

    for stat_name in STAT_NAMES:
        slider_key = _key(pokemon_name, f"stat_points_{stat_name}")
        st.session_state.setdefault(slider_key, int(saved_stats.get(stat_name, 0)))

    stat_points: StatPointValues = {
        stat_name: int(st.session_state[_key(pokemon_name, f"stat_points_{stat_name}")])
        for stat_name in STAT_NAMES
    }
    actual_stats = _calculate_champions_stats(base_stats, stat_points, nature)
    nature_modifier = NATURE_MODIFIERS.get(nature)

    for stat_name, base_value in zip(STAT_NAMES, base_stats):
        nature_marker = ""
        if nature_modifier and stat_name == nature_modifier[0]:
            nature_marker = '<span class="nature-mark nature-up">↑</span>'
        elif nature_modifier and stat_name == nature_modifier[1]:
            nature_marker = '<span class="nature-mark nature-down">↓</span>'
        stat_col, points_col, base_col, actual_col = st.columns(
            column_widths, vertical_alignment="center"
        )
        with stat_col:
            st.markdown(
                f'<div class="stat-name">{stat_name}{nature_marker}</div>',
                unsafe_allow_html=True,
            )
        with points_col:
            slider_key = _key(pokemon_name, f"stat_points_{stat_name}")
            minus_col, slider_col, plus_col = st.columns(
                [0.22, 0.56, 0.22], vertical_alignment="center", gap="small"
            )
            with minus_col:
                st.button(
                    "−",
                    key=_key(pokemon_name, f"stat_points_minus_{stat_name}"),
                    on_click=_adjust_stat_point,
                    args=(slider_key, -1),
                    disabled=stat_points[stat_name] <= 0,
                    use_container_width=True,
                )
            with slider_col:
                stat_points[stat_name] = st.slider(
                    f"{stat_name}能力ポイント",
                    min_value=0,
                    max_value=32,
                    step=1,
                    key=slider_key,
                    label_visibility="collapsed",
                )
            with plus_col:
                st.button(
                    "+",
                    key=_key(pokemon_name, f"stat_points_plus_{stat_name}"),
                    on_click=_adjust_stat_point,
                    args=(slider_key, 1),
                    disabled=stat_points[stat_name] >= 32,
                    use_container_width=True,
                )
        with base_col:
            st.markdown(f'<div class="base-stat">{base_value}</div>', unsafe_allow_html=True)
        with actual_col:
            st.markdown(
                f'<div class="actual-stat">{actual_stats[stat_name]}</div>',
                unsafe_allow_html=True,
            )

    total_stat_points = sum(stat_points.values())
    progress_percent = min(100, round(total_stat_points / 66 * 100))
    st.markdown(
        '<div class="stat-points-total">'
        f'<div><span>ポイント合計</span><b>{total_stat_points} <small>/ 66</small></b></div>'
        f'<div class="stat-points-meter"><span style="width:{progress_percent}%"></span></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.caption("各能力は最大32ポイント")
    if total_stat_points > 66:
        st.error("能力ポイントの合計は66以下にしてください。")
    return stat_points, total_stat_points


def render() -> None:
    configure_page("推しポケラボ | 個体の詳細設定", "pokemon.css")
    store = require_conversation_store()
    render_sidebar(store, back_to_selection=True)
    pokemon_name = cast(str | None, st.session_state.get("pokemon_detail_target"))
    raw_pokemon = st.session_state.get("pokemon_detail_profile")
    if not pokemon_name or not raw_pokemon:
        st.warning("ポケモン選択画面から設定する相棒を選んでください。")
        if st.button("ポケモン選択へ戻る", type="primary"):
            st.switch_page("app_pages/pokemon_selection.py")
        return
    pokemon = cast(PokemonProfile, raw_pokemon)

    species: PokemonSpecies = SPECIES.get(
        pokemon_name,
        {"base_stats": [0, 0, 0, 0, 0, 0], "abilities": [], "moves": []},
    )
    metadata = _fetch_species_metadata(pokemon_name)
    species = {
        **species,
        "base_stats": _metadata_stats(metadata, species["base_stats"]),
        "abilities": _metadata_abilities(metadata, species["abilities"]),
        "moves": _local_moves(pokemon_name, species["moves"]),
    }
    builds = cast(PokemonBuildMap, st.session_state.setdefault("pokemon_builds", {}))
    saved: PokemonBuild = builds.get(pokemon_name, {})
    saved_moves: list[str] = (saved.get("moves") or []) + [""] * 4
    saved_stats = _load_stat_points(saved)

    battle_data: BattleDataResponse | None = None
    if pokemon_name in SHOWDOWN_IDS:
        try:
            battle_data = get_battle_data(pokemon_name, "Singles")
        except (RuntimeError, ValueError) as error:
            st.warning(f"対戦データ API を取得できませんでした。{error}")

    move_rows = _category_rows(battle_data, "move")
    abilities = species["abilities"]
    if not abilities:
        abilities = ["特性データを取得できません"]
    move_names = species["moves"]
    item_names = _load_local_options("items.json", "items") or ITEMS
    nature_names = _load_local_options("natures.json", "natures") or NATURES

    st.markdown(
        '<div class="advice-progress">'
        '<span class="advice-progress-step advice-progress-complete"><b>01</b> ポケモンを選ぶ</span>'
        '<span class="advice-progress-line advice-progress-line-complete"></span>'
        '<span class="advice-progress-step advice-progress-active"><b>02</b> 個体の型を決める</span>'
        '</div>'
        '<div class="page-eyebrow">POKEMON CHAMPIONS　 ·　 BUILD</div>'
        '<h1 class="page-title">相棒の型を組み立てよう。</h1>'
        '<p class="page-description">能力ポイントを調整し、性格や技を選んで相談内容を整えます。</p>',
        unsafe_allow_html=True,
    )

    with st.container(key="build_editor_card"):
        with st.container(key="build_identity_card"):
            header_image, header_text = st.columns([0.14, 0.86], vertical_alignment="center")
            with header_image:
                st.image(pokemon["image"], width=72)
            with header_text:
                st.markdown(
                    '<div class="build-identity-eyebrow">設定するポケモン</div>'
                    f'<div class="detail-number">{pokemon["number"]}　 ·　{pokemon["type"]}</div>'
                    f'<div class="build-pokemon-name">{pokemon_name}</div>',
                    unsafe_allow_html=True,
                )

        st.markdown('<div class="build-section-title build-options-title">基本設定</div>', unsafe_allow_html=True)
        nature_col, ability_col, item_col = st.columns(3, gap="medium")
        with nature_col:
            saved_nature = saved.get("nature", "指定なし")
            nature = st.selectbox(
                "性格",
                nature_names,
                key=_key(pokemon_name, "nature"),
                index=nature_names.index(saved_nature) if saved_nature in nature_names else 0,
            )
            nature_modifier = NATURE_MODIFIERS.get(nature)
            if nature_modifier:
                st.markdown(
                    '<div class="nature-effect">'
                    f'<span class="nature-up">↑ {nature_modifier[0]} ×1.1</span>'
                    '<span class="nature-down">↓ '
                    f'{nature_modifier[1]} ×0.9</span>'
                    '</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="nature-effect nature-neutral">この性格は能力値を補正しません</div>',
                    unsafe_allow_html=True,
                )
        with ability_col:
            saved_ability = saved.get("ability", abilities[0])
            ability = st.selectbox(
                "特性",
                abilities,
                key=_key(pokemon_name, "ability"),
                index=abilities.index(saved_ability) if saved_ability in abilities else 0,
            )
        with item_col:
            saved_item = saved.get("item", "指定しない")
            item = st.selectbox(
                "持ち物",
                item_names,
                key=_key(pokemon_name, "item"),
                index=item_names.index(saved_item) if saved_item in item_names else 0,
            )

        build_left, build_right = st.columns([1.2, 0.8], gap="medium")
        with build_left:
            with st.container(key="stat_editor_panel"):
                stat_points, total_stat_points = _render_stat_points_editor(
                    pokemon_name, species["base_stats"], nature, saved_stats
                )

        with build_right:
            with st.container(key="build_move_panel"):
                st.markdown(
                    '<div class="build-section-title move-section-title">技を選ぶ</div>',
                    unsafe_allow_html=True,
                )
                if battle_data:
                    st.caption(
                        f"使用率データ · {battle_data.get('format', 'Singles')} / "
                        f"{battle_data.get('season', 'Current')}"
                    )
                else:
                    st.caption("使用率データは現在利用できません。")
                move_options = ["指定しない", *move_names]
                move_keys = [
                    _key(pokemon_name, f"move_{index}") for index in range(4)
                ]
                # Repair duplicate values from saved builds or stale widget state.
                seen_moves: set[str] = set()
                for index, move_key in enumerate(move_keys):
                    selected = st.session_state.get(move_key, saved_moves[index])
                    if selected not in move_options or selected in seen_moves:
                        selected = "指定しない"
                    st.session_state[move_key] = selected
                    if selected != "指定しない":
                        seen_moves.add(selected)

                moves = []
                for index in range(4):
                    move_key = move_keys[index]
                    selected_elsewhere = {
                        st.session_state[key]
                        for other_index, key in enumerate(move_keys)
                        if other_index != index
                        and st.session_state[key] != "指定しない"
                    }
                    available_moves = [
                        move
                        for move in move_options
                        if move == "指定しない" or move not in selected_elsewhere
                    ]
                    moves.append(
                        st.selectbox(
                            f"技{index + 1}",
                            available_moves,
                            key=move_key,
                            format_func=_format_options(move_rows),
                        )
                    )

                selected_moves = [move for move in moves if move != "指定しない"]
                move_summary = "、".join(selected_moves) if selected_moves else "技はまだ選択されていません。"
                popular_move_rows = _category_rows(battle_data, "move")[:4]
                if popular_move_rows:
                    popular_moves = "　/　".join(
                        f"{escape(row['name'])} {escape(str(row.get('percentage') or ''))}".strip()
                        for row in popular_move_rows
                    )
                else:
                    popular_moves = "この形式の技データはまだありません。"
                st.caption(
                    f"設定中: 性格 {nature}　/　特性 {ability}　/　持ち物 {item}"
                )
                st.markdown(
                    f'<div class="build-summary"><b>よく使われる技</b><br>'
                    f'<span>{popular_moves}</span><br><br>'
                    f'<span>選択した技: {escape(move_summary)}</span></div>',
                    unsafe_allow_html=True,
                )

    with st.container(key="build_actions"):
        back_col, save_col = st.columns([0.42, 0.58], gap="small")
        with back_col:
            if st.button("← ポケモン選択に戻る", use_container_width=True):
                st.switch_page("app_pages/pokemon_selection.py")
        with save_col:
            if st.button(
                "この内容で相談する　→",
                type="primary",
                use_container_width=True,
            ):
                if total_stat_points > 66:
                    st.error("能力ポイントの合計を66以下にしてください。")
                else:
                    builds[pokemon_name] = {
                        "nature": nature,
                        "ability": ability,
                        "item": item,
                        "stat_points": stat_points,
                        "moves": moves,
                    }
                    st.session_state.pokemon_builds = builds
                    first_selected = st.session_state.get(
                        "new_advice_first_pokemon",
                        st.session_state.get("first_pokemon_select", ""),
                    )
                    second_selected = st.session_state.get(
                        "new_advice_second_pokemon",
                        st.session_state.get("second_pokemon_select", ""),
                    )
                    placeholder = "選択してください"
                    if (
                        st.session_state.get("pokemon_detail_slot") == "second"
                        and first_selected
                        and first_selected != placeholder
                    ):
                        first_pokemon = first_selected
                        second_pokemon = pokemon_name
                    else:
                        first_pokemon = pokemon_name
                        second_pokemon = (
                            second_selected
                            if second_selected not in ("", placeholder, pokemon_name)
                            else ""
                        )
                    st.session_state.chosen_pokemon = first_pokemon
                    st.session_state.partner_pokemon = second_pokemon
                    try:
                        conversation = store.create(f"{first_pokemon}との相談")
                    except ConversationError as error:
                        st.error(str(error))
                    else:
                        remember_selected_pokemon(
                            conversation["id"], first_pokemon, second_pokemon
                        )
                        open_conversation(conversation["id"])

    st.markdown(
        f'<div class="api-attribution">{API_ATTRIBUTION}</div>',
        unsafe_allow_html=True,
    )


render()
