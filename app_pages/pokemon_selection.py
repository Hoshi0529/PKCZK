import json
from html import escape
from pathlib import Path
from urllib.parse import quote

import streamlit as st

from back.conversations import create_conversation, get_conversation
from ui.layout import configure_page
from ui.history import render_history
from ui.pokemon_types import PokemonProfile

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _load_json(filename: str) -> dict:
    try:
        with (DATA_DIR / filename).open(encoding="utf-8") as file:
            value = json.load(file)
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


LOCAL_POKEMON_NAMES = _load_json("pokemon_champions_names_all_forms.json")
PCBD_FORMS = _load_json("pcbd_forms.json")
LOCAL_NAME_TO_ID = {
    value.get("name_ja"): showdown_id
    for showdown_id, value in LOCAL_POKEMON_NAMES.items()
    if isinstance(value, dict)
    and isinstance(value.get("name_ja"), str)
    and isinstance(PCBD_FORMS.get(showdown_id), dict)
    and PCBD_FORMS[showdown_id].get("metadata_row_available")
}


LEGACY_POKEMON: dict[str, PokemonProfile] = {
    "ピカチュウ": {
        "number": "#025",
        "type": "でんき",
        "image": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/25.png",
        "description": "ほっぺの電気袋に電気をためる。仲間を見つけると電気を鳴らして合図する。",
        "color": "#f2bd35",
    },
    "ガブリアス": {
        "number": "#445",
        "type": "ドラゴン / じめん",
        "image": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/445.png",
        "description": "音速で空を飛び、獲物を探す。大きな翼で風を切って進む。",
        "color": "#6c5b9b",
    },
    "マリル": {
        "number": "#183",
        "type": "みず / フェアリー",
        "image": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/183.png",
        "description": "水に浮くしっぽを浮き輪のように使って、楽しく泳ぐ。",
        "color": "#5299d1",
    },
    "ルカリオ": {
        "number": "#448",
        "type": "かくとう / はがね",
        "image": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/448.png",
        "description": "波導を感じ取り、相手の気持ちや動きを読み取る。",
        "color": "#6488ad",
    },
    "イーブイ": {
        "number": "#133",
        "type": "ノーマル",
        "image": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/133.png",
        "description": "環境に合わせて姿を変える、不思議な可能性を秘めたポケモン。",
        "color": "#af8057",
    },
}

POKEMON: dict[str, PokemonProfile] = {}
for pokemon_id, names in LOCAL_POKEMON_NAMES.items():
    form = PCBD_FORMS.get(pokemon_id)
    if not isinstance(names, dict) or not isinstance(form, dict):
        continue
    pokemon_name = names.get("name_ja")
    if not isinstance(pokemon_name, str) or not form.get("metadata_row_available"):
        continue
    POKEMON[pokemon_name] = LEGACY_POKEMON.get(
        pokemon_name,
        {
            "number": "",
            "type": "",
            "image": "",
            "description": "",
            "color": "#6c8f82",
        },
    )
for pokemon_name, profile in LEGACY_POKEMON.items():
    POKEMON.setdefault(pokemon_name, profile)

PLACEHOLDER = "選択してください"


def _local_pokemon_name(pokemon_name: str) -> str:
    return pokemon_name


def _pokemon_image_url(pokemon_name: str, fallback: str) -> str:
    showdown_id = LOCAL_NAME_TO_ID.get(pokemon_name, "")
    form = PCBD_FORMS.get(showdown_id, {})
    saved_name = form.get("saved_name") if isinstance(form, dict) else None
    if not isinstance(saved_name, str) or not saved_name:
        return fallback
    return (
        "https://championsbattledata.com/pokemon_champions_assets/pokemon/"
        f"{quote(saved_name, safe='')}.png"
    )


def _start_new_advice() -> None:
    first_pokemon = st.session_state.get("first_pokemon_select", PLACEHOLDER)
    second_pokemon = st.session_state.get("second_pokemon_select", PLACEHOLDER)
    selected_pokemon = [
        name
        for name in (first_pokemon, second_pokemon)
        if name and name != PLACEHOLDER
    ]

    active_id = st.session_state.get("active_conversation_id")
    active_conversation = get_conversation(active_id) if active_id else None
    if selected_pokemon and (
        active_conversation is None
        or active_conversation.get("pokemon", []) != selected_pokemon
    ):
        conversation = create_conversation(
            selected_pokemon[0],
            selected_pokemon[1] if len(selected_pokemon) > 1 else "",
        )
        st.session_state.active_conversation_id = conversation["id"]

    for key in ("first_pokemon_select", "second_pokemon_select"):
        st.session_state.pop(key, None)


def _render_pokemon_detail(pokemon_name: str, card_key: str) -> None:
    pokemon: PokemonProfile = POKEMON[pokemon_name]
    display_name = _local_pokemon_name(pokemon_name)
    image_url = _pokemon_image_url(pokemon_name, pokemon["image"])
    pokemon_type = pokemon["type"]
    with st.container(key=card_key):
        art_col, text_col = st.columns([0.42, 0.58], vertical_alignment="center")
        with art_col:
            if image_url:
                st.markdown(
                    f'<img src="{escape(image_url, quote=True)}" '
                    f'alt="{escape(display_name, quote=True)}" '
                    'width="112" loading="lazy" style="object-fit:contain">',
                    unsafe_allow_html=True,
                )
        with text_col:
            number_and_type = "　 ·　".join(
                escape(value) for value in (pokemon["number"], pokemon_type) if value
            )
            st.markdown(
                f'<div class="detail-number">{number_and_type}</div>'
                f'<h2 class="detail-name">{escape(display_name)}</h2>'
                f'<span class="type-pill" style="--type-color:{pokemon["color"]}">{escape(pokemon_type)}</span>'
                if pokemon_type
                else "",
                unsafe_allow_html=True,
            )
        if pokemon["description"]:
            st.markdown(
                f'<p class="pokemon-description">{escape(pokemon["description"])}</p>',
                unsafe_allow_html=True,
            )
        elif not pokemon_type:
            st.caption("タイプ・図鑑説明データは未登録です。")
        if st.button(
            "個体の型を設定する",
            key=f"configure_build_{pokemon_name}",
            use_container_width=True,
        ):
            st.session_state.pokemon_detail_target = pokemon_name
            st.session_state.pokemon_detail_profile = {**pokemon, "image": image_url}
            st.session_state.pokemon_detail_slot = (
                "second" if card_key == "partner_detail_card" else "first"
            )
            st.switch_page("app_pages/pokemon_detail.py")


@st.fragment
def _render_selection_workspace() -> None:
    st.markdown(
        '<div class="step-label">03　ポケモン選択 / かんたんに始める</div>'
        '<div class="page-eyebrow">POKEMON CHAMPIONS　 ·　 はじめの一歩</div>'
        '<h1 class="page-title">まずは、推しポケモンを選ぼう。</h1>'
        '<p class="page-description">画像とタイプを見ながら選ぼう。迷ったら、あとから変えることもできます。</p>',
        unsafe_allow_html=True,
    )

    roster, details = st.columns([1.04, 0.96], gap="large")
    with roster:
        st.markdown(
            '<div class="section-title">1匹目のポケモン <span class="count-pill">必須</span></div>',
            unsafe_allow_html=True,
        )
        first_options = [PLACEHOLDER, *POKEMON.keys()]
        first_pokemon = st.selectbox(
            "1匹目のポケモン",
            first_options,
            index=0,
            label_visibility="collapsed",
            key="first_pokemon_select",
            format_func=_local_pokemon_name,
        )

        st.markdown(
            '<div class="section-title partner-heading">2匹目のポケモン <span class="count-pill">任意</span></div>',
            unsafe_allow_html=True,
        )
        second_options = [
            PLACEHOLDER,
            *[name for name in POKEMON if name != first_pokemon],
        ]
        second_pokemon = st.selectbox(
            "2匹目のポケモン",
            second_options,
            index=0,
            label_visibility="collapsed",
            key="second_pokemon_select",
            format_func=_local_pokemon_name,
        )
        st.caption("2匹目は任意です。あとから変更できます。")

    with details:
        st.markdown('<div class="section-title">選んだ相棒</div>', unsafe_allow_html=True)
        if first_pokemon != PLACEHOLDER:
            _render_pokemon_detail(first_pokemon, "pokemon_detail_card")
        if second_pokemon != PLACEHOLDER:
            _render_pokemon_detail(second_pokemon, "partner_detail_card")
        if first_pokemon == PLACEHOLDER and second_pokemon == PLACEHOLDER:
            st.markdown(
                '<div class="empty-selection">プルダウンからポケモンを選ぶと、ここに表示されます。</div>',
                unsafe_allow_html=True,
            )

    if first_pokemon != PLACEHOLDER:
        summary = f"選択中: {first_pokemon}"
        if second_pokemon != PLACEHOLDER:
            summary += f" と {second_pokemon}"
        st.markdown(f'<div class="selection-summary">{escape(summary)}</div>', unsafe_allow_html=True)

    _, action_col = st.columns([0.57, 0.43])
    with action_col:
        if st.button(
            "この相棒で相談する　→",
            type="primary",
            use_container_width=True,
            key="continue_button",
            disabled=first_pokemon == PLACEHOLDER,
        ):
            st.session_state.chosen_pokemon = first_pokemon
            st.session_state.partner_pokemon = "" if second_pokemon == PLACEHOLDER else second_pokemon
            conversation = create_conversation(
                first_pokemon, st.session_state.partner_pokemon
            )
            st.session_state.active_conversation_id = conversation["id"]
            st.session_state.page = "Chat"
            st.switch_page("app_pages/chat.py")


def render() -> None:
    configure_page("pokecham | ポケモン選択", "pokemon.css")

    sidebar, content = st.columns([0.19, 0.81], gap="small")

    with sidebar:
        st.markdown(
            '<div class="brand"><span class="brand-mark">✦</span><span>pokecham</span></div>',
            unsafe_allow_html=True,
        )
        st.button(
            "＋ アドバイスをもらう",
            use_container_width=True,
            key="advice_button",
            on_click=_start_new_advice,
        )
        render_history()
        st.markdown(
            '<div class="sidebar-bottom"><div class="sidebar-quote">好きな一匹と、<br>勝ち筋を見つけよう。</div></div>',
            unsafe_allow_html=True,
        )
        if st.button("⚙　設定", use_container_width=True, key="settings_button"):
            st.switch_page("app_pages/settings.py")
        st.markdown('<div class="sidebar-user">◉　だいき</div>', unsafe_allow_html=True)

    with content:
        _render_selection_workspace()


render()
