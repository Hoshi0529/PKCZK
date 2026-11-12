"""Bind conversation access to the authenticated Streamlit session."""

from copy import deepcopy

import streamlit as st

from back.auth import AuthenticationError, get_verified_account
from back.conversations import ConversationStore
from ui.pokemon_types import PokemonBuildMap


def require_conversation_store() -> ConversationStore:
    client = st.session_state.get("auth_client")
    try:
        user = get_verified_account(client) if client is not None else None
    except AuthenticationError as error:
        st.error(str(error))
        st.stop()
    if user is None:
        st.session_state.pop("auth_client", None)
        st.session_state.pop("current_account", None)
        st.session_state.pop("chat_reply_request", None)
        st.session_state.pop("chat_question_drafts", None)
        st.session_state.pop("chat_openings", None)
        st.switch_page("app_pages/login.py")
    st.session_state.current_account = user
    return ConversationStore(client, str(user.id))


def open_conversation(conversation_id: str, *, opening_for: str | None = None) -> None:
    st.session_state.active_conversation_id = conversation_id
    params = {"conversation_id": conversation_id}
    if opening_for is not None:
        st.session_state.setdefault("chat_openings", {})[(opening_for, conversation_id)] = "queued"
        params["opening"] = "1"
    st.switch_page("app_pages/chat.py", query_params=params)


def remember_selected_pokemon(conversation_id: str, first: str, second: str) -> None:
    selected = st.session_state.setdefault("conversation_pokemon", {})
    selected[conversation_id] = [name for name in (first, second) if name]


def remember_conversation_builds(
    user_id: str, conversation_id: str, builds: PokemonBuildMap
) -> None:
    conversations = st.session_state.setdefault("conversation_pokemon_builds", {})
    conversations[(user_id, conversation_id)] = deepcopy(builds)


def conversation_builds(user_id: str, conversation_id: str | None) -> PokemonBuildMap:
    return st.session_state.get("conversation_pokemon_builds", {}).get(
        (user_id, conversation_id), {}
    )
