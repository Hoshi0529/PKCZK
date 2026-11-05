import streamlit as st


pages = [
    st.Page("app_pages/pokemon_selection.py", title="ポケモン選択", url_path="new-advice"),
    st.Page("app_pages/chat.py", title="相談", url_path="Chat"),
    st.Page("app_pages/settings.py", title="設定", url_path="Setting"),
    st.Page("app_pages/login.py", title="ログイン", url_path="Login", default=True),
    st.Page("app_pages/pokemon_detail.py", title="個体の型を設定", url_path="PokemonDetail"),
]
st.navigation(pages, position="hidden").run()
