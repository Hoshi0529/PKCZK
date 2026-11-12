from html import escape

import streamlit as st

from back.conversations import ConversationError, ConversationStore
from ui.chat_session import create_pokemon_conversation, remember_selected_pokemon, require_conversation_store
from ui.layout import configure_page
from ui.pokemon_catalog import POKEMON, pokemon_image_url
from ui.sidebar import render_sidebar
from ui.pokemon_types import PokemonProfile

PLACEHOLDER = "選択してください"
FIRST_SELECTION_STATE = "new_advice_first_pokemon"
SECOND_SELECTION_STATE = "new_advice_second_pokemon"


def _local_pokemon_name(pokemon_name: str) -> str:
    return pokemon_name


def _start_new_advice(store: ConversationStore) -> None:
    first_pokemon = st.session_state.get("first_pokemon_select", PLACEHOLDER)
    second_pokemon = st.session_state.get("second_pokemon_select", PLACEHOLDER)
    selected_pokemon = [
        name
        for name in (first_pokemon, second_pokemon)
        if name and name != PLACEHOLDER
    ]

    active_id = st.session_state.get("active_conversation_id")
    active_pokemon = st.session_state.get("conversation_pokemon", {}).get(active_id)
    if selected_pokemon and active_pokemon != selected_pokemon:
        try:
            conversation = create_pokemon_conversation(store, selected_pokemon)
        except ConversationError as error:
            st.error(str(error))
            return
        st.session_state.active_conversation_id = conversation["id"]
        remember_selected_pokemon(conversation["id"], selected_pokemon[0], selected_pokemon[1] if len(selected_pokemon) > 1 else "")

    for key in (
        "first_pokemon_select",
        "second_pokemon_select",
        FIRST_SELECTION_STATE,
        SECOND_SELECTION_STATE,
    ):
        st.session_state.pop(key, None)


def _remember_selection(widget_key: str, saved_key: str) -> None:
    st.session_state[saved_key] = st.session_state.get(widget_key, PLACEHOLDER)


def _render_pokemon_detail(pokemon_name: str, card_key: str) -> None:
    pokemon: PokemonProfile = POKEMON[pokemon_name]
    display_name = _local_pokemon_name(pokemon_name)
    image_url = pokemon_image_url(pokemon_name, pokemon["image"])
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
def _render_selection_workspace(store: ConversationStore) -> None:
    st.markdown(
        '<div class="advice-progress">'
        '<span class="advice-progress-step advice-progress-active"><b>01</b> ポケモンを選ぶ</span>'
        '<span class="advice-progress-line"></span>'
        '<span class="advice-progress-step"><b>02</b> 個体の型を決める</span>'
        '</div>'
        '<div class="page-eyebrow">NEW ADVICE　 ·　 はじめの一歩</div>'
        '<h1 class="page-title">相談する相棒を選ぼう。</h1>'
        '<p class="page-description">名前を入力して検索できます。まず1匹、必要なら2匹目も選べます。</p>',
        unsafe_allow_html=True,
    )

    roster, details = st.columns([1.04, 0.96], gap="large")
    with roster:
        with st.container(key="selection_picker_panel"):
            st.markdown(
                '<div class="section-title">相談するポケモン</div>'
                '<div class="picker-slot-title">'
                '<span class="picker-slot-number">1</span> 1匹目'
                '<span class="count-pill">必須</span></div>',
                unsafe_allow_html=True,
            )
            first_options = [PLACEHOLDER, *POKEMON.keys()]
            first_saved = st.session_state.get(FIRST_SELECTION_STATE, PLACEHOLDER)
            if first_saved not in first_options:
                first_saved = PLACEHOLDER
            first_pokemon = st.selectbox(
                "1匹目のポケモン",
                first_options,
                index=first_options.index(first_saved),
                label_visibility="collapsed",
                key="first_pokemon_select",
                format_func=_local_pokemon_name,
                on_change=_remember_selection,
                args=("first_pokemon_select", FIRST_SELECTION_STATE),
            )
            st.session_state[FIRST_SELECTION_STATE] = first_pokemon

            st.markdown(
                '<div class="picker-slot-title picker-slot-second">'
                '<span class="picker-slot-number picker-slot-number-optional">2</span> 2匹目'
                '<span class="count-pill count-pill-optional">任意</span></div>',
                unsafe_allow_html=True,
            )
            second_saved = st.session_state.get(SECOND_SELECTION_STATE, PLACEHOLDER)
            if second_saved == first_pokemon:
                second_saved = PLACEHOLDER
                st.session_state[SECOND_SELECTION_STATE] = PLACEHOLDER
                st.session_state["second_pokemon_select"] = PLACEHOLDER
            second_options = [
                PLACEHOLDER,
                *[name for name in POKEMON if name != first_pokemon],
            ]
            if second_saved not in second_options:
                second_saved = PLACEHOLDER
            second_pokemon = st.selectbox(
                "2匹目のポケモン",
                second_options,
                index=second_options.index(second_saved),
                label_visibility="collapsed",
                key="second_pokemon_select",
                format_func=_local_pokemon_name,
                on_change=_remember_selection,
                args=("second_pokemon_select", SECOND_SELECTION_STATE),
            )
            st.session_state[SECOND_SELECTION_STATE] = second_pokemon
            st.caption("2匹目は任意です。あとから追加・変更できます。")

    with details:
        with st.container(key="selected_companions_panel"):
            st.markdown(
                '<div class="section-title">選んだ相棒</div>'
                '<div class="selected-panel-hint">選んだポケモンの情報がここに表示されます。</div>',
                unsafe_allow_html=True,
            )
            if first_pokemon != PLACEHOLDER:
                _render_pokemon_detail(first_pokemon, "pokemon_detail_card")
            if second_pokemon != PLACEHOLDER:
                _render_pokemon_detail(second_pokemon, "partner_detail_card")
            if first_pokemon == PLACEHOLDER and second_pokemon == PLACEHOLDER:
                st.markdown(
                    '<div class="empty-selection">'
                    '<span class="empty-selection-mark">✦</span>'
                    '<span>ポケモンを選ぶと、ここに相棒カードが表示されます。</span>'
                    '</div>',
                    unsafe_allow_html=True,
                )

    if first_pokemon != PLACEHOLDER:
        summary = f"選択中: {first_pokemon}"
        if second_pokemon != PLACEHOLDER:
            summary += f" と {second_pokemon}"
        st.markdown(f'<div class="selection-summary">{escape(summary)}</div>', unsafe_allow_html=True)

    _, action_col = st.columns([0.48, 0.52])
    with action_col:
        if st.button(
            "個体の型を決める　→",
            type="primary",
            use_container_width=True,
            key="continue_button",
            disabled=first_pokemon == PLACEHOLDER,
        ):
            st.session_state[FIRST_SELECTION_STATE] = first_pokemon
            st.session_state[SECOND_SELECTION_STATE] = second_pokemon
            selected_profile = POKEMON[first_pokemon]
            st.session_state.pokemon_detail_target = first_pokemon
            st.session_state.pokemon_detail_profile = {
                **selected_profile,
                "image": pokemon_image_url(
                    first_pokemon, selected_profile["image"]
                ),
            }
            st.session_state.pokemon_detail_slot = "first"
            st.switch_page("app_pages/pokemon_detail.py")


def render() -> None:
    configure_page("推しポケラボ | ポケモン選択", "pokemon.css")
    store = require_conversation_store()

    render_sidebar(store)
    _render_selection_workspace(store)


render()
