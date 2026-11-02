import streamlit as st

from back.conversations import create_conversation, get_conversation
from front.layout import configure_page
from front.history import render_history


POKEMON = {
    "ピカチュウ": {
        "number": "#025",
        "type": "でんき",
        "image": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/25.png",
        "description": "ほっぺの電気袋に電気をためる。仲間を見つけると電気を鳴らして合図する。",
        "color": "#f2bd35",
    },
    "ガブリアス": {
        "number": "#445",
        "type": "ドラゴン / じめん",
        "image": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/445.png",
        "description": "音速で空を飛び、獲物を探す。大きな翼で風を切って進む。",
        "color": "#6c5b9b",
    },
    "マリル": {
        "number": "#183",
        "type": "みず / フェアリー",
        "image": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/183.png",
        "description": "水に浮くしっぽを浮き輪のように使って、楽しく泳ぐ。",
        "color": "#5299d1",
    },
    "ルカリオ": {
        "number": "#448",
        "type": "かくとう / はがね",
        "image": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/448.png",
        "description": "波導を感じ取り、相手の気持ちや動きを読み取る。",
        "color": "#6488ad",
    },
    "イーブイ": {
        "number": "#133",
        "type": "ノーマル",
        "image": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/133.png",
        "description": "環境に合わせて姿を変える、不思議な可能性を秘めたポケモン。",
        "color": "#af8057",
    },
}

PLACEHOLDER = "選択してください"


def _start_new_advice() -> None:
    first_pokemon = st.session_state.get("first_pokemon_select", PLACEHOLDER)
    second_pokemon = st.session_state.get("second_pokemon_select", PLACEHOLDER)
    selected_pokemon = [
        name
        for name in (first_pokemon, second_pokemon)
        if name and name != PLACEHOLDER
    ]

    active_id = st.session_state.get("active_conversation_id")
    active_conversation = get_conversation(active_id) if active_id else None
    if selected_pokemon and (
        active_conversation is None
        or active_conversation.get("pokemon", []) != selected_pokemon
    ):
        conversation = create_conversation(
            selected_pokemon[0],
            selected_pokemon[1] if len(selected_pokemon) > 1 else "",
        )
        st.session_state.active_conversation_id = conversation["id"]

    for key in ("first_pokemon_select", "second_pokemon_select"):
        st.session_state.pop(key, None)


def _render_pokemon_detail(pokemon_name: str, card_key: str) -> None:
    pokemon = POKEMON[pokemon_name]
    with st.container(key=card_key):
        art_col, text_col = st.columns([0.42, 0.58], vertical_alignment="center")
        with art_col:
            st.image(pokemon["image"], width=112)
        with text_col:
            st.markdown(
                f'<div class="detail-number">{pokemon["number"]}　 ·　{pokemon["type"]}</div>'
                f'<h2 class="detail-name">{pokemon_name}</h2>'
                f'<span class="type-pill" style="--type-color:{pokemon["color"]}">{pokemon["type"]}</span>',
                unsafe_allow_html=True,
            )
        st.markdown(
            f'<p class="pokemon-description">{pokemon["description"]}</p>',
            unsafe_allow_html=True,
        )
        if st.button(
            "個体の型を設定する",
            key=f"configure_build_{pokemon_name}",
            use_container_width=True,
        ):
            st.session_state.pokemon_detail_target = pokemon_name
            st.session_state.pokemon_detail_profile = pokemon
            st.session_state.pokemon_detail_slot = (
                "second" if card_key == "partner_detail_card" else "first"
            )
            st.switch_page("pages/PokemonDetail.py")


def render() -> None:
    configure_page("pokecham | ポケモン選択", "pokemon.css")

    sidebar, content = st.columns([0.19, 0.81], gap="small")

    with sidebar:
        st.markdown(
            '<div class="brand"><span class="brand-mark">✦</span><span>pokecham</span></div>',
            unsafe_allow_html=True,
        )
        st.button(
            "＋ アドバイスをもらう",
            use_container_width=True,
            key="advice_button",
            on_click=_start_new_advice,
        )
        render_history()
        st.markdown(
            '<div class="sidebar-bottom"><div class="sidebar-quote">好きな一匹と、<br>勝ち筋を見つけよう。</div></div>',
            unsafe_allow_html=True,
        )
        if st.button("⚙　設定", use_container_width=True, key="settings_button"):
            st.switch_page("pages/Setting.py")
        st.markdown('<div class="sidebar-user">◉　だいき</div>', unsafe_allow_html=True)

    with content:
        st.markdown(
            '<div class="step-label">03　ポケモン選択 / かんたんに始める</div>'
            '<div class="page-eyebrow">POKEMON CHAMPIONS　 ·　 はじめの一歩</div>'
            '<h1 class="page-title">まずは、推しポケモンを選ぼう。</h1>'
            '<p class="page-description">画像とタイプを見ながら選ぼう。迷ったら、あとから変えることもできます。</p>',
            unsafe_allow_html=True,
        )

        roster, details = st.columns([1.04, 0.96], gap="large")
        with roster:
            st.markdown(
                '<div class="section-title">1匹目のポケモン <span class="count-pill">必須</span></div>',
                unsafe_allow_html=True,
            )
            first_options = [PLACEHOLDER, *POKEMON.keys()]
            first_pokemon = st.selectbox(
                "1匹目のポケモン",
                first_options,
                index=0,
                label_visibility="collapsed",
                key="first_pokemon_select",
            )

            st.markdown(
                '<div class="section-title partner-heading">2匹目のポケモン <span class="count-pill">任意</span></div>',
                unsafe_allow_html=True,
            )
            second_options = [
                PLACEHOLDER,
                *[name for name in POKEMON if name != first_pokemon],
            ]
            second_pokemon = st.selectbox(
                "2匹目のポケモン",
                second_options,
                index=0,
                label_visibility="collapsed",
                key="second_pokemon_select",
            )
            st.caption("2匹目は任意です。あとから変更できます。")

        with details:
            st.markdown('<div class="section-title">選んだ相棒</div>', unsafe_allow_html=True)
            if first_pokemon != PLACEHOLDER:
                _render_pokemon_detail(first_pokemon, "pokemon_detail_card")
            if second_pokemon != PLACEHOLDER:
                _render_pokemon_detail(second_pokemon, "partner_detail_card")
            if first_pokemon == PLACEHOLDER and second_pokemon == PLACEHOLDER:
                st.markdown(
                    '<div class="empty-selection">プルダウンからポケモンを選ぶと、ここに表示されます。</div>',
                    unsafe_allow_html=True,
                )

        if first_pokemon != PLACEHOLDER:
            summary = f"選択中: {first_pokemon}"
            if second_pokemon != PLACEHOLDER:
                summary += f" と {second_pokemon}"
            st.markdown(f'<div class="selection-summary">{summary}</div>', unsafe_allow_html=True)

        _, action_col = st.columns([0.57, 0.43])
        with action_col:
            if st.button(
                "この相棒で相談する　→",
                type="primary",
                use_container_width=True,
                key="continue_button",
                disabled=first_pokemon == PLACEHOLDER,
            ):
                st.session_state.chosen_pokemon = first_pokemon
                st.session_state.partner_pokemon = "" if second_pokemon == PLACEHOLDER else second_pokemon
                conversation = create_conversation(
                    first_pokemon, st.session_state.partner_pokemon
                )
                st.session_state.active_conversation_id = conversation["id"]
                st.session_state.page = "Chat"
                st.switch_page("pages/Chat.py")


def run_app() -> None:
    pages = [
        st.Page(
            "pages/NewAdvice.py",
            title="ポケモン選択",
            url_path="new-advice",
            default=True,
        ),
        st.Page("pages/Chat.py", title="相談"),
        st.Page("pages/Setting.py", title="設定"),
        st.Page("pages/Login.py", title="ログイン"),
        st.Page("pages/PokemonDetail.py", title="個体の型を設定"),
    ]
    st.navigation(pages, position="hidden").run()


if __name__ == "__main__":
    run_app()
