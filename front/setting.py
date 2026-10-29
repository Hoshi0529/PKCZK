import streamlit as st

from front.layout import configure_page


def render() -> None:
    configure_page("pokecham | 設定", "setting.css")

    sidebar, content = st.columns([0.17, 0.83], gap=None)

    with sidebar:
        st.markdown(
            '<div class="brand"><span class="brand-mark">✦</span><span>pokecham</span></div>',
            unsafe_allow_html=True,
        )
        st.button("＋ アドバイスをもらう", use_container_width=True)
        st.markdown(
            """
            <div class="history-heading">これまでの相談</div>
            <div class="history-item">
                <span class="history-icon"></span>
                <span>ピカチュウ<span class="history-time">今日 14:32</span></span>
            </div>
            <div class="history-item">
                <span class="history-icon"></span>
                <span>ガブリアス<span class="history-time">昨日 18:30</span></span>
            </div>
            <div class="sidebar-bottom">
                <div class="sidebar-quote">好きな一匹と、<br>勝ち筋を見つけよう。</div>
                <div class="sidebar-settings"><span>⚙</span><span>設定</span></div>
                <div class="sidebar-user"><span class="avatar">D</span><span>だいき</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with content:
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
