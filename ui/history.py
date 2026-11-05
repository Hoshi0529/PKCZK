import streamlit as st
from datetime import datetime

from back.conversations import list_conversations


def render_history() -> None:
    st.markdown('<div class="history-heading">これまでの会話</div>', unsafe_allow_html=True)
    conversations = list_conversations()
    if not conversations:
        st.caption("会話履歴はまだありません")
        return

    for conversation in conversations:
        pokemon = "・".join(conversation.get("pokemon", [])) or "ポケモン相談"
        title = conversation.get("title") or pokemon
        updated = conversation.get("updated_at", "")
        try:
            updated_label = datetime.fromisoformat(updated).astimezone().strftime("%m/%d %H:%M")
        except (ValueError, TypeError):
            updated_label = ""
        label = f"{title[:24]}\n{pokemon}　{updated_label}"
        if st.button(label, key=f"open_conversation_{conversation['id']}", use_container_width=True):
            st.session_state.active_conversation_id = conversation["id"]
            st.switch_page("app_pages/chat.py")
