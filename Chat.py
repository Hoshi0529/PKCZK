from html import escape

import streamlit as st

from back.conversations import append_message, create_conversation, get_conversation
from front.history import render_history
from front.layout import configure_page


def _active_conversation() -> dict:
    conversation_id = st.session_state.get("active_conversation_id")
    conversation = get_conversation(conversation_id) if conversation_id else None
    if conversation is None:
        first_pokemon = st.session_state.get("chosen_pokemon", "ピカチュウ")
        second_pokemon = st.session_state.get("partner_pokemon", "")
        conversation = create_conversation(first_pokemon, second_pokemon)
        st.session_state.active_conversation_id = conversation["id"]
    return conversation


def render() -> None:
    configure_page("pokecham | 相談", "pokemon.css")
    conversation = _active_conversation()
    sidebar, content = st.columns([0.19, 0.81], gap="small")

    with sidebar:
        st.markdown(
            '<div class="brand"><span class="brand-mark">✦</span><span>pokecham</span></div>',
            unsafe_allow_html=True,
        )
        if st.button(
            "＋ アドバイスをもらう",
            use_container_width=True,
            key="new_chat_button",
        ):
            for key in ("first_pokemon_select", "second_pokemon_select"):
                st.session_state.pop(key, None)
            st.switch_page("pages/NewAdvice.py")
        render_history()
        st.markdown(
            '<div class="sidebar-bottom"><div class="sidebar-quote">好きな一匹と、<br>勝ち筋を見つけよう。</div></div>',
            unsafe_allow_html=True,
        )
        if st.button("⚙　設定", use_container_width=True, key="settings_button"):
            st.switch_page("pages/Setting.py")

    with content:
        pokemon = "・".join(conversation.get("pokemon", [])) or "ポケモン"
        safe_pokemon = escape(pokemon)
        safe_title = escape(conversation.get("title", "相談"))
        st.markdown(
            f'<div class="page-eyebrow">POKEMON CHAMPIONS　 ·　{safe_pokemon}</div>'
            f'<h1 class="page-title">{safe_title}</h1>'
            '<p class="page-description">相談内容はこの端末に保存され、履歴からいつでも開けます。</p>',
            unsafe_allow_html=True,
        )

        messages = conversation.get("messages", [])
        if not messages:
            st.info("相談したい内容を入力してください。送信した内容は会話履歴に保存されます。")
        for message in messages:
            with st.chat_message(message.get("role", "user")):
                st.write(message.get("content", ""))

        if prompt := st.chat_input("ポケモンについて相談する"):
            saved = append_message(conversation["id"], "user", prompt)
            if saved:
                st.rerun()


if __name__ == "__main__":
    render()
