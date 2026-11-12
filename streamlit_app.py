import streamlit as st

from back.conversations import ConversationError, conversation_id_from_url


def _open_chat() -> None:
    conversation_id = conversation_id_from_url(st.query_params.get("conversation_id"))
    params = {"conversation_id": conversation_id} if conversation_id else None
    st.switch_page("app_pages/chat.py", query_params=params)


pages = {
    "メニュー": [
        st.Page("app_pages/pokemon_selection.py", title="新しい相談", url_path="new-advice"),
        st.Page("app_pages/chat.py", title="相談", url_path="chat"),
        st.Page(_open_chat, title="相談（旧URL）", url_path="Chat", visibility="hidden"),
        st.Page("app_pages/pokemon_detail.py", title="個体の型を設定", url_path="PokemonDetail"),
        st.Page("app_pages/settings.py", title="設定", url_path="Setting"),
    ],
    "": [
        st.Page("app_pages/login.py", title="ログイン", url_path="Login", default=True, visibility="hidden"),
    ],
}
try:
    st.navigation(pages, position="hidden").run()
except ConversationError as error:
    st.error(str(error))
