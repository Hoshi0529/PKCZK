from html import escape

import streamlit as st

from back.conversations import ConversationError, ConversationStore
from ui.chat_session import (
    create_pokemon_conversation,
    open_conversation,
    remember_selected_pokemon,
    require_conversation_store,
)
from ui.layout import configure_page
from ui.pokemon_catalog import POKEMON, pokemon_image_url, pokemon_selection_conflicts
from ui.sidebar import render_sidebar

PLACEHOLDER = "選択してください"


def _saved_selection(slot: str) -> str:
    name = st.session_state.get(
        f"{slot}_pokemon_select", st.session_state.get(f"new_advice_{slot}_pokemon")
    )
    return name if name in POKEMON else PLACEHOLDER


def _render_slot(slot: str, saved: str, other: str) -> str:
    label = "1匹目（必須）" if slot == "first" else "2匹目（任意）"
    options = [PLACEHOLDER] + [
        name for name in POKEMON
        if name != other and not pokemon_selection_conflicts(name, other)
    ]
    with st.container(key=f"selection_{slot}_panel"):
        selected = st.selectbox(
            label, options, index=options.index(saved), key=f"{slot}_pokemon_select"
        )
        st.session_state[f"new_advice_{slot}_pokemon"] = selected
        profile = POKEMON.get(selected)
        if profile:
            image_url = pokemon_image_url(selected, profile["image"])
            artwork = (
                f'<img src="{escape(image_url, quote=True)}" alt="{escape(selected)}">'
                if image_url else "画像未登録"
            )
            preview = (
                f'<h2>{escape(selected)}</h2>'
                f'<span class="type-pill" style="--type-color:{escape(profile["color"])}">'
                f'{escape(profile["type"])}</span><div class="selection-art">{artwork}</div>'
            )
        else:
            preview = '<p>ポケモンを選ぶとここに表示されます。</p>'
        st.markdown(
            f'<div class="selection-preview">{preview}</div>', unsafe_allow_html=True
        )
        if st.button(
            "個体の型を設定する", key=f"configure_{slot}_build",
            use_container_width=True, disabled=profile is None,
        ):
            st.session_state.pokemon_detail_target = selected
            st.session_state.pokemon_detail_profile = {**profile, "image": image_url}
            st.session_state.pokemon_detail_slot = slot
            st.switch_page("app_pages/pokemon_detail.py")
    return selected


@st.fragment
def _render_selection_workspace(store: ConversationStore) -> None:
    st.markdown(
        '<h1 class="page-title">相談する相棒を選ぼう。</h1>'
        '<p class="page-description">名前を入力して検索できます。まず1匹、必要なら2匹目も選べます。</p>',
        unsafe_allow_html=True,
    )
    first = _saved_selection("first")
    second = _saved_selection("second")
    if first != PLACEHOLDER and (first == second or pokemon_selection_conflicts(first, second)):
        second = PLACEHOLDER
        st.session_state["second_pokemon_select"] = second

    with st.container(key="selection_workspace"):
        left, right = st.columns(2)
        with left:
            first = _render_slot("first", first, second)
        with right:
            second = _render_slot("second", second, first)
        if st.button(
            "チャットへ進む", type="primary", use_container_width=True,
            key="continue_button", disabled=first == PLACEHOLDER,
        ):
            partner = "" if second == PLACEHOLDER else second
            try:
                conversation = create_pokemon_conversation(store, (first, partner))
            except ConversationError as error:
                st.error(str(error))
                return
            remember_selected_pokemon(conversation["id"], first, partner)
            open_conversation(conversation["id"], opening_for=store.user_id)


def render() -> None:
    configure_page("推しポケラボ | ポケモン選択", "pokemon.css")
    store = require_conversation_store()
    render_sidebar(store)
    _render_selection_workspace(store)


render()
