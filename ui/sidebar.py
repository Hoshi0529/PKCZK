from html import escape

import streamlit as st

from back.conversations import ConversationStore
from ui.history import render_history


def account_display_name(user) -> str:
    metadata = getattr(user, "user_metadata", None) or {}
    username = metadata.get("username") if isinstance(metadata, dict) else None
    if isinstance(username, str) and username.strip():
        return username.strip()
    email = getattr(user, "email", None)
    if isinstance(email, str) and email.strip():
        return email.split("@", 1)[0]
    return "\u30e6\u30fc\u30b6\u30fc"


def render_sidebar(store: ConversationStore, *, back_to_selection: bool = False) -> None:
    with st.sidebar:
        with st.container(key="shared_sidebar_top"):
            st.markdown("## \u63a8\u3057\u30dd\u30b1\u30e9\u30dc")

            label = (
                "\u2190 \u30dd\u30b1\u30e2\u30f3\u9078\u629e\u306b\u623b\u308b"
                if back_to_selection
                else "\uff0b \u65b0\u3057\u3044\u76f8\u8ac7\u3092\u59cb\u3081\u308b"
            )
            if st.button(label, use_container_width=True, key="shared_sidebar_new_advice"):
                for key in (
                    "first_pokemon_select",
                    "second_pokemon_select",
                    "new_advice_first_pokemon",
                    "new_advice_second_pokemon",
                ):
                    st.session_state.pop(key, None)
                st.switch_page("app_pages/pokemon_selection.py")

        with st.container(key="shared_sidebar_history"):
            render_history(store)

        user = st.session_state.get("current_account")
        display_name = escape(account_display_name(user) if user else "\u30e6\u30fc\u30b6\u30fc")
        with st.container(key="shared_sidebar_account_actions"):
            st.markdown(
                f'<div class="shared-sidebar-user">\u25c9　{display_name}</div>',
                unsafe_allow_html=True,
            )
            if st.button(
                "\u2699 \u8a2d\u5b9a",
                use_container_width=True,
                key="shared_sidebar_settings",
            ):
                st.switch_page("app_pages/settings.py")
