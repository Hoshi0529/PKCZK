import streamlit as st

from back.auth import validate_account_input
from back.pokemon import fetch_pokemon_artwork
from front.layout import configure_page


FALLBACK_ARTWORK = {
    "pikachu": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/25.png",
    "garchomp": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/445.png",
}


@st.cache_data(ttl=86400, show_spinner=False)
def get_pokemon_artwork() -> tuple[dict[str, str], list[str]]:
    return fetch_pokemon_artwork()


def render() -> None:
    configure_page("pokecham | ログイン", "login.css")

    left, right = st.columns([0.88, 1.12], gap=None)

    with left:
        try:
            with st.spinner("ポケモンの画像を読み込んでいます..."):
                api_artwork, errors = get_pokemon_artwork()
        except RuntimeError as error:
            api_artwork = {}
            errors = [str(error)]

        pokemon_artwork = FALLBACK_ARTWORK | api_artwork
        if errors:
            st.warning(
                f"PokeAPIで取得できない画像には予備画像を使用します。{' / '.join(errors)}"
            )
        artwork_html = "".join(
            f'<img src="{pokemon_artwork[name]}" alt="{label}">'
            for name, label in (("pikachu", "ピカチュウ"), ("garchomp", "ガブリアス"))
            if name in pokemon_artwork
        )

        st.markdown(
            f"""
            <div class="brand"><span class="brand-mark">✦</span><span>pokecham</span></div>
            <div class="eyebrow">YOUR FAVORITE, YOUR TEAM</div>
            <h1 class="hero-title">好きなポケモンと、<br>勝つ方法を見つけよう。</h1>
            <div class="team-art">
                {artwork_html}
            </div>
            <div class="left-copy">
                相棒の育て方も、仲間選びも。<br>
                AIと話しながら、あなただけの作戦を。
            </div>
            <div class="left-note">今日も、相棒と一歩ずつ。</div>
            <div class="left-footer">pokecham / 好きな一匹からはじまる作戦会議</div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        mode = st.session_state.get("account_mode", "ログイン")
        is_registering = mode == "新規登録"
        st.markdown(
            (
                '<h2 class="form-heading">はじめまして</h2>'
                '<p class="form-subtitle">相棒との作戦会議を、ここから始めましょう。</p>'
                if is_registering
                else '<h2 class="form-heading">おかえりなさい</h2>'
                '<p class="form-subtitle">相棒との作戦会議を、続けましょう。</p>'
            ),
            unsafe_allow_html=True,
        )

        mode = st.segmented_control(
            "アカウント",
            options=["新規登録", "ログイン"],
            default="ログイン",
            width="stretch",
            label_visibility="collapsed",
            key="account_mode",
        )
        is_registering = mode == "新規登録"

        with st.form("account_form", border=False):
            email = st.text_input("メールアドレス", placeholder="you@example.com")
            password = st.text_input("パスワード", type="password", placeholder="8文字以上")
            confirm_password = ""
            if is_registering:
                confirm_password = st.text_input(
                    "パスワード（確認）",
                    type="password",
                    placeholder="もう一度入力してください",
                )
            submitted = st.form_submit_button(
                "新規登録" if is_registering else "ログイン",
                use_container_width=True,
            )

        if submitted:
            error = validate_account_input(
                email, password, is_registering, confirm_password
            )
            if error:
                st.error(error)
            else:
                st.info("ログイン機能はまだ接続されていません。")

        st.markdown(
            '<p class="form-footnote">好きなポケモンで勝ちたい。その気持ちを応援するよ。</p>',
            unsafe_allow_html=True,
        )
