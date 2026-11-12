import streamlit as st

from ui.chat_session import require_conversation_store
from ui.layout import configure_page
from ui.sidebar import render_sidebar


def render() -> None:
    configure_page("推しポケラボ | 設定", "setting.css")
    store = require_conversation_store()

    render_sidebar(store)
    st.markdown(
        """
        <div class="page-eyebrow">SETTINGS</div>
        <h1 class="page-title">設定</h1>
        <p class="page-description">アカウントの操作はこちらから。</p>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True, key="account_card"):
        st.markdown(
            """
            <div class="account-heading">アカウント</div>
            <div class="account-name">だいき</div>
            <p class="account-description">相談の履歴は、このアカウントで保存されるよ。</p>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="logout-heading">ログアウト</div>
            <p class="logout-description">またログインすれば、保存した相談を続けられるよ。</p>
            """,
            unsafe_allow_html=True,
        )
        if st.button("ログアウト", use_container_width=True):
            st.info("ログアウト機能はまだ接続されていません。")


render()
