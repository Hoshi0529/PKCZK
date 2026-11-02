import re

import streamlit as st

from back.conversations import create_conversation, list_conversations
from front.layout import configure_page


SPECIES = {
    "ピカチュウ": {
        "base_stats": [35, 55, 40, 50, 50, 90],
        "abilities": ["せいでんき", "ひらいしん"],
        "moves": ["10まんボルト", "かみなり", "ボルトチェンジ", "でんこうせっか", "くさむすび", "なみのり", "アンコール", "でんじは"],
    },
    "ガブリアス": {
        "base_stats": [108, 130, 95, 80, 85, 102],
        "abilities": ["すながくれ", "さめはだ"],
        "moves": ["じしん", "げきりん", "ドラゴンクロー", "ストーンエッジ", "どくづき", "つるぎのまい", "ステルスロック", "ほのおのキバ"],
    },
    "マリル": {
        "base_stats": [70, 20, 50, 20, 50, 40],
        "abilities": ["あついしぼう", "ちからもち", "そうしょく"],
        "moves": ["アクアブレイク", "じゃれつく", "アクアジェット", "ばかぢから", "はたきおとす", "れいとうパンチ", "はらだいこ", "アンコール"],
    },
    "ルカリオ": {
        "base_stats": [70, 110, 70, 115, 70, 90],
        "abilities": ["ふくつのこころ", "せいしんりょく", "せいぎのこころ"],
        "moves": ["インファイト", "はどうだん", "しんそく", "ラスターカノン", "バレットパンチ", "つるぎのまい", "れいとうパンチ", "じしん"],
    },
    "イーブイ": {
        "base_stats": [55, 55, 50, 45, 65, 55],
        "abilities": ["にげあし", "てきおうりょく", "きけんよち"],
        "moves": ["すてみタックル", "でんこうせっか", "あくび", "まもる", "バトンタッチ", "ねがいごと", "とっておき", "のしかかり"],
    },
}

STAT_NAMES = ["HP", "こうげき", "ぼうぎょ", "とくこう", "とくぼう", "すばやさ"]
NATURES = ["指定なし", "いじっぱり", "ようき", "ひかえめ", "おくびょう", "ずぶとい", "しんちょう", "わんぱく", "おだやか", "むじゃき", "せっかち"]
ITEMS = ["指定しない", "きあいのタスキ", "いのちのたま", "こだわりハチマキ", "こだわりスカーフ", "こだわりメガネ", "たべのこし", "オボンのみ", "とつげきチョッキ"]


def _key(pokemon_name: str, field: str) -> str:
    slug = re.sub(r"\W+", "_", pokemon_name)
    return f"pokemon_build_{slug}_{field}"


def _render_sidebar() -> None:
    with st.container(key="build_sidebar"):
        st.markdown(
            '<div class="brand"><span class="brand-mark">✦</span><span>pokecham</span></div>',
            unsafe_allow_html=True,
        )
        if st.button("＋ アドバイスをもらう", use_container_width=True, key="build_new_advice"):
            for key in ("first_pokemon_select", "second_pokemon_select"):
                st.session_state.pop(key, None)
            st.switch_page("pages/NewAdvice.py")

        st.markdown('<div class="history-heading">これまでの会話</div>', unsafe_allow_html=True)
        conversations = list_conversations()
        if not conversations:
            st.caption("会話履歴はまだありません")
        for conversation in conversations:
            names = "・".join(conversation.get("pokemon", [])) or "ポケモン相談"
            if st.button(
                f'{conversation.get("title", names)[:22]}\n{names}',
                key=f'build_history_{conversation["id"]}',
                use_container_width=True,
            ):
                st.session_state.active_conversation_id = conversation["id"]
                st.switch_page("pages/Chat.py")

        st.markdown(
            '<div class="sidebar-bottom"><div class="sidebar-quote">好きな一匹と、<br>勝ち筋を見つけよう。</div></div>',
            unsafe_allow_html=True,
        )
        if st.button("⚙　設定", use_container_width=True, key="build_settings"):
            st.switch_page("pages/Setting.py")
        st.markdown('<div class="sidebar-user">◉　だいき</div>', unsafe_allow_html=True)


def render() -> None:
    configure_page("pokecham | 個体の詳細設定", "pokemon.css")
    sidebar, content = st.columns([0.19, 0.81], gap="small")
    with sidebar:
        _render_sidebar()

    with content:
        pokemon_name = st.session_state.get("pokemon_detail_target")
        pokemon = st.session_state.get("pokemon_detail_profile")
        if not pokemon_name or not pokemon:
            st.warning("ポケモン選択画面から設定する相棒を選んでください。")
            if st.button("ポケモン選択へ戻る", type="primary"):
                st.switch_page("pages/NewAdvice.py")
            return

        species = SPECIES.get(pokemon_name, SPECIES["ピカチュウ"])
        builds = st.session_state.setdefault("pokemon_builds", {})
        saved = builds.get(pokemon_name, {})
        saved_moves = (saved.get("moves") or []) + [""] * 4
        saved_stats = saved.get("effort", {})

        st.markdown(
            '<div class="step-label">04　ポケモン選択 / 個体の詳細設定</div>'
            '<div class="page-eyebrow">POKEMON CHAMPIONS　 ·　 BUILD</div>'
            '<h1 class="page-title">相棒の育て方を決めよう。</h1>'
            '<p class="page-description">性格や能力ポイント、技を設定して、自分だけの型を作ろう。</p>',
            unsafe_allow_html=True,
        )

        with st.container(key="build_editor_card"):
            header_image, header_text = st.columns([0.12, 0.88], vertical_alignment="center")
            with header_image:
                st.image(pokemon["image"], width=64)
            with header_text:
                st.markdown(
                    f'<div class="detail-number">{pokemon["number"]}　 ·　{pokemon["type"]}</div>'
                    f'<div class="build-pokemon-name">{pokemon_name}</div>',
                    unsafe_allow_html=True,
                )

            nature_col, ability_col, item_col = st.columns(3, gap="medium")
            with nature_col:
                nature = st.selectbox("性格", NATURES, key=_key(pokemon_name, "nature"), index=NATURES.index(saved.get("nature", "指定なし")) if saved.get("nature", "指定なし") in NATURES else 0)
            with ability_col:
                abilities = species["abilities"]
                saved_ability = saved.get("ability", abilities[0])
                ability = st.selectbox("特性", abilities, key=_key(pokemon_name, "ability"), index=abilities.index(saved_ability) if saved_ability in abilities else 0)
            with item_col:
                item = st.selectbox("持ち物", ITEMS, key=_key(pokemon_name, "item"), index=ITEMS.index(saved.get("item", "指定しない")) if saved.get("item", "指定しない") in ITEMS else 0)

            build_left, build_right = st.columns([1.02, 0.98], gap="large")
            with build_left:
                st.markdown('<div class="build-section-title">能力ポイント <span class="count-pill">努力値</span></div>', unsafe_allow_html=True)
                effort = {}
                for stat_name, base_value in zip(STAT_NAMES, species["base_stats"]):
                    stat_col, base_col = st.columns([0.72, 0.28], vertical_alignment="center")
                    with stat_col:
                        effort[stat_name] = st.number_input(
                            stat_name,
                            min_value=0,
                            max_value=252,
                            step=4,
                            value=int(saved_stats.get(stat_name, 0)),
                            key=_key(pokemon_name, f"effort_{stat_name}"),
                        )
                    with base_col:
                        st.markdown(f'<div class="base-stat">基礎値 <b>{base_value}</b></div>', unsafe_allow_html=True)
                total_effort = sum(effort.values())
                st.caption(f"能力ポイント合計: {total_effort} / 510")
                if total_effort > 510:
                    st.error("能力ポイントの合計は510以下にしてください。")

            with build_right:
                st.markdown('<div class="build-section-title">決めてもらう技</div>', unsafe_allow_html=True)
                move_options = ["指定しない", *species["moves"]]
                moves = []
                for index in range(4):
                    saved_move = saved_moves[index]
                    move_index = move_options.index(saved_move) if saved_move in move_options else 0
                    moves.append(
                        st.selectbox(
                            f"技{index + 1}",
                            move_options,
                            index=move_index,
                            key=_key(pokemon_name, f"move_{index}"),
                        )
                    )

                selected_moves = [move for move in moves if move != "指定しない"]
                move_summary = "、".join(selected_moves) if selected_moves else "技はまだ選択されていません。"
                st.markdown(
                    f'<div class="build-summary"><b>注目の使い方</b><br>{pokemon_name}の設定内容を相談時に参照します。<br><br>'
                    f'<span>性格: {nature}　/　特性: {ability}　/　持ち物: {item}</span><br>'
                    f'<span>技: {move_summary}</span></div>',
                    unsafe_allow_html=True,
                )

        back_col, save_col = st.columns([0.52, 0.48], gap="small")
        with back_col:
            if st.button("← ポケモン選択に戻る", use_container_width=True):
                st.switch_page("pages/NewAdvice.py")
        with save_col:
            if st.button(
                "この内容で相談する　→",
                type="primary",
                use_container_width=True,
                disabled=total_effort > 510,
            ):
                builds[pokemon_name] = {
                    "nature": nature,
                    "ability": ability,
                    "item": item,
                    "effort": effort,
                    "moves": moves,
                }
                st.session_state.pokemon_builds = builds
                first_selected = st.session_state.get("first_pokemon_select", "")
                second_selected = st.session_state.get("second_pokemon_select", "")
                placeholder = "選択してください"
                if (
                    st.session_state.get("pokemon_detail_slot") == "second"
                    and first_selected
                    and first_selected != placeholder
                ):
                    first_pokemon = first_selected
                    second_pokemon = pokemon_name
                else:
                    first_pokemon = pokemon_name
                    second_pokemon = (
                        second_selected
                        if second_selected not in ("", placeholder, pokemon_name)
                        else ""
                    )
                st.session_state.chosen_pokemon = first_pokemon
                st.session_state.partner_pokemon = second_pokemon
                conversation = create_conversation(first_pokemon, second_pokemon)
                st.session_state.active_conversation_id = conversation["id"]
                st.session_state.page = "Chat"
                st.switch_page("pages/Chat.py")
