import streamlit as st
from datetime import datetime
from time import monotonic

from back.conversations import ConversationStore
from ui.chat_session import open_conversation


def render_history(store: ConversationStore) -> None:
    st.markdown('<div class="history-heading">これまでの会話</div>', unsafe_allow_html=True)
    # Streamlit redraws the sidebar on every interaction. Cache this user's
    # recent history briefly to avoid a database request on each rerun.
    cache_key = f"conversation_history:{store.user_id}"
    cached = st.session_state.get(cache_key)
    now = monotonic()
    if cached is None or now - cached[0] >= 20:
        cached = (now, store.list())
        st.session_state[cache_key] = cached
    conversations = cached[1]
    if not conversations:
        st.caption("会話履歴はまだありません")
        return

    for conversation in conversations:
        title = conversation.get("title") or "ポケモン相談"
        updated = conversation.get("updated_at", "")
        try:
            updated_label = datetime.fromisoformat(updated).astimezone().strftime("%m/%d %H:%M")
        except (ValueError, TypeError):
            updated_label = ""
        label = f"{title}\n{updated_label}"
        if st.button(label, key=f"open_conversation_{conversation['id']}", use_container_width=True):
            open_conversation(conversation["id"])
