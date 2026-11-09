"""Bind conversation access to the authenticated Streamlit session."""

import streamlit as st

from back.auth import AuthenticationError, get_verified_account
from back.conversations import ConversationStore


def require_conversation_store(return_to: str | None = None) -> ConversationStore:
    client = st.session_state.get("auth_client")
    try:
        user = get_verified_account(client) if client is not None else None
    except AuthenticationError as error:
        st.error(str(error))
        st.stop()
    if user is None:
        st.session_state.pop("auth_client", None)
        st.session_state.pop("chat_reply_request", None)
        st.session_state.pop("chat_question_submission", None)
        params = {"conversation_id": return_to} if return_to else None
        st.switch_page("app_pages/login.py", query_params=params)
    return ConversationStore(client, str(user.id))


def open_conversation(conversation_id: str) -> None:
    st.session_state.active_conversation_id = conversation_id
    st.switch_page("app_pages/chat.py", query_params={"conversation_id": conversation_id})


def remember_selected_pokemon(conversation_id: str, first: str, second: str) -> None:
    selected = st.session_state.setdefault("conversation_pokemon", {})
    selected[conversation_id] = [name for name in (first, second) if name]
