from html import escape

import streamlit as st

from back.champions_battle_data import BattleDataResponse, BattleRow, rows_for_category
from back.conversations import append_message, create_conversation, get_conversation
from ui.battle_data import API_ATTRIBUTION, SHOWDOWN_IDS, get_battle_data
from ui.history import render_history
from ui.layout import configure_page


POKEMON_ART = {
    "ピカチュウ": ("でんき", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/25.png"),
    "ガブリアス": ("ドラゴン / じめん", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/445.png"),
    "マリル": ("みず / フェアリー", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/183.png"),
    "ルカリオ": ("かくとう / はがね", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/448.png"),
    "イーブイ": ("ノーマル", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/133.png"),
}


def _active_conversation() -> dict:
    conversation_id = st.session_state.get("active_conversation_id")
    conversation = get_conversation(conversation_id) if conversation_id else None
    if conversation is None:
        pokemon = st.session_state.get("chosen_pokemon", "ピカチュウ")
        partner = st.session_state.get("partner_pokemon", "")
        conversation = create_conversation(pokemon, partner)
        st.session_state.active_conversation_id = conversation["id"]
    return conversation


def _render_pokemon_banner(pokemon_name: str, partner_name: str) -> None:
    pokemon_type, image_url = POKEMON_ART.get(pokemon_name, ("", ""))
    image = f'<img src="{image_url}" alt="">' if image_url else ""
    safe_name = escape(pokemon_name)
    safe_type = escape(pokemon_type)
    partner_text = f'<span class="chat-partner-tag">相棒: {escape(partner_name)}</span>' if partner_name else ""
    st.markdown(
        f'<div class="chat-pokemon-banner"><div class="chat-banner-art">{image}</div>'
        f'<div><div class="chat-pokemon-name">{safe_name}</div>'
        f'<span class="type-pill">{safe_type}</span> {partner_text}</div>'
        '<span class="chat-banner-step">相談中　›</span></div>',
        unsafe_allow_html=True,
    )


def _render_build_card(pokemon_name: str) -> None:
    build = st.session_state.get("pokemon_builds", {}).get(pokemon_name, {})
    info = POKEMON_ART.get(pokemon_name, ("", ""))
    _, image_url = info
    moves = [move for move in build.get("moves", []) if move and move != "指定しない"]
    build_summary = "　・　".join(
        value for value in (build.get("nature"), build.get("ability"), build.get("item"))
        if value and value not in ("指定なし", "指定しない")
    )
    move_summary = "　/　".join(moves) if moves else "技はまだ設定されていません"
    image = f'<img src="{image_url}" alt="">' if image_url else ""
    escaped_name = escape(pokemon_name)
    st.markdown(
        '<div class="chat-build-card">'
        f'<div class="chat-build-art">{image}</div>'
        '<div class="chat-build-content">'
        f'<div><b>{escaped_name}の育成メモ</b><span class="count-pill">自分の設定</span></div>'
        f'<p>{escape(build_summary) if build_summary else "個体の型を設定すると、ここに表示されます。"}</p>'
        f'<div class="chat-build-moves">{escape(move_summary)}</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    if st.button("個体の型を編集する", key="edit_build_from_chat"):
        st.session_state.pokemon_detail_target = pokemon_name
        st.session_state.pokemon_detail_profile = {
            "number": "", "type": info[0], "image": image_url, "description": "", "color": "#237b61"
        }
        st.session_state.pokemon_detail_slot = "first"
        st.switch_page("app_pages/pokemon_detail.py")


def _render_team_cards(pokemon_names: list[str]) -> None:
    st.markdown('<div class="chat-section-heading">今回のチーム</div>', unsafe_allow_html=True)
    if len(pokemon_names) < 2:
        st.markdown(
            '<div class="chat-team-empty">2匹目の相棒を選ぶと、チーム構成も一緒に相談できます。</div>',
            unsafe_allow_html=True,
        )
        return

    team_cols = st.columns(len(pokemon_names[:2]), gap="medium")
    for column, pokemon_name in zip(team_cols, pokemon_names[:2]):
        pokemon_type, image_url = POKEMON_ART.get(pokemon_name, ("", ""))
        with column:
            st.markdown(
                '<div class="chat-team-card">'
                f'<img src="{image_url}" alt="">'
                f'<div><b>{escape(pokemon_name)}</b><span class="type-pill">{escape(pokemon_type)}</span></div>'
                '</div>',
                unsafe_allow_html=True,
            )


def _render_battle_data(pokemon_name: str) -> None:
    if pokemon_name not in SHOWDOWN_IDS:
        return
    try:
        data: BattleDataResponse = get_battle_data(pokemon_name, "Singles")
    except (RuntimeError, ValueError) as error:
        st.warning(f"対戦データ API を取得できませんでした。{error}")
        return

    categories = [
        ("move", "よく使われる技"),
        ("item", "持ち物"),
        ("teammate", "よく組まれる相棒"),
    ]
    category_cols = st.columns(len(categories), gap="medium")
    for column, (category, title) in zip(category_cols, categories):
        rows = rows_for_category(data, category)[:4]
        with column:
            if rows:
                content = "<br>".join(
                    f'{escape(row["name"])}'
                    f'<span class="battle-percentage">{escape(str(row.get("percentage") or ""))}</span>'
                    for row in rows
                )
            else:
                content = "データなし"
            st.markdown(
                f'<div class="api-battle-stat"><b>{title}</b><div>{content}</div></div>',
                unsafe_allow_html=True,
            )
    st.markdown(
        f'<div class="api-attribution">{API_ATTRIBUTION}</div>',
        unsafe_allow_html=True,
    )


def render() -> None:
    configure_page("pokecham | 相談", "pokemon.css")
    conversation = _active_conversation()
    pokemon_names = conversation.get("pokemon", [])
    pokemon_name = pokemon_names[0] if pokemon_names else st.session_state.get("chosen_pokemon", "ポケモン")
    partner_name = pokemon_names[1] if len(pokemon_names) > 1 else ""

    sidebar, content = st.columns([0.19, 0.81], gap="small")
    with sidebar:
        st.markdown(
            '<div class="brand"><span class="brand-mark">✦</span><span>pokecham</span></div>',
            unsafe_allow_html=True,
        )
        if st.button("＋ アドバイスをもらう", use_container_width=True, key="new_chat_button"):
            for key in ("first_pokemon_select", "second_pokemon_select"):
                st.session_state.pop(key, None)
            st.switch_page("app_pages/pokemon_selection.py")
        render_history()
        st.markdown(
            '<div class="sidebar-bottom"><div class="sidebar-quote">好きな一匹と、<br>勝ち筋を見つけよう。</div></div>',
            unsafe_allow_html=True,
        )
        if st.button("⚙　設定", use_container_width=True, key="settings_button"):
            st.switch_page("app_pages/settings.py")
        st.markdown('<div class="sidebar-user">◉　だいき</div>', unsafe_allow_html=True)

    with content:
        st.markdown(
            '<div class="step-label">05　チャット / 相棒の勝ち筋を探す</div>'
            '<div class="page-eyebrow">POKEMON CHAMPIONS　 ·　 相談</div>',
            unsafe_allow_html=True,
        )
        _render_pokemon_banner(pokemon_name, partner_name)

        st.markdown(
            '<div class="chat-intro"><span class="chat-intro-mark">✦</span>'
            '<div><b>pokecham</b><p>選んだ相棒と育成メモを確認できます。<br>'
            '送信したメッセージはこの会話の履歴に保存されます。</p></div></div>',
            unsafe_allow_html=True,
        )

        _render_build_card(pokemon_name)
        _render_team_cards(pokemon_names)
        _render_battle_data(pokemon_name)

        messages = conversation.get("messages", [])
        if messages:
            st.markdown('<div class="chat-section-heading">会話</div>', unsafe_allow_html=True)
            for message in messages:
                with st.chat_message(message.get("role", "user")):
                    st.write(message.get("content", ""))
        else:
            st.markdown(
                '<div class="chat-empty-note">相談したいことを入力してください。過去の発言がある場合は、この下に表示されます。</div>',
                unsafe_allow_html=True,
            )

        if prompt := st.chat_input("相棒のこと、気になることを聞いてみよう"):
            saved = append_message(conversation["id"], "user", prompt)
            if saved:
                st.rerun()


render()
