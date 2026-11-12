from contextlib import closing
from dataclasses import dataclass
from html import escape
from uuid import uuid4

import streamlit as st

from back.conversations import ConversationError, ConversationStore, conversation_id_from_url
from back.groq_chat import ChatError, ReplyPokemon, stream_reply
from ui.chat_session import conversation_builds, require_conversation_store
from ui.layout import configure_page
from ui.pokemon_types import STAT_NAMES, PokemonBuild, PokemonBuildMap
from ui.sidebar import render_sidebar


POKEMON_ART = {
    "ピカチュウ": ("でんき", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/25.png"),
    "ガブリアス": ("ドラゴン / じめん", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/445.png"),
    "マリル": ("みず / フェアリー", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/183.png"),
    "ルカリオ": ("かくとう / はがね", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/448.png"),
    "イーブイ": ("ノーマル", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/133.png"),
}


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


def _render_build_card(pokemon_name: str, build: PokemonBuild | None) -> None:
    info = POKEMON_ART.get(pokemon_name, ("", ""))
    _, image_url = info
    details = "<p>未設定</p>"
    if build is not None:
        build_summary = "　・　".join(
            f"{label} {value}"
            for label, value in (
                ("性格", build.get("nature") or "未設定"),
                ("特性", build.get("ability") or "未設定"),
                ("持ち物", build.get("item") or "未設定"),
            )
        )
        move_summary = " / ".join(build.get("moves", [])) or "未設定"
        actual_stats = build.get("actual_stats", {})
        stat_summary = " / ".join(
            f"{stat} {actual_stats[stat]}" for stat in STAT_NAMES if stat in actual_stats
        ) or "未取得"
        details = (
            f'<p>{escape(build_summary)}</p>'
            f'<div class="chat-build-moves">技 {escape(move_summary)}</div>'
            f'<p>実数値（Lv.50） {escape(stat_summary)}</p>'
        )
    image = f'<img src="{image_url}" alt="">' if image_url else ""
    escaped_name = escape(pokemon_name)
    st.markdown(
        '<div class="chat-build-card">'
        f'<div class="chat-build-art">{image}</div>'
        '<div class="chat-build-content">'
        f'<div><b>{escaped_name}の育成メモ</b><span class="count-pill">自分の設定</span></div>'
        f'{details}'
        '</div></div>',
        unsafe_allow_html=True,
    )


def _render_edit_build_button(pokemon_name: str) -> None:
    if st.button("個体の型を編集する", key="edit_build_from_chat"):
        pokemon_type, image_url = POKEMON_ART.get(pokemon_name, ("", ""))
        st.session_state.pokemon_detail_target = pokemon_name
        st.session_state.pokemon_detail_profile = {
            "number": "", "type": pokemon_type, "image": image_url, "description": "", "color": "#237b61"
        }
        st.session_state.pokemon_detail_slot = "first"
        st.switch_page("app_pages/pokemon_detail.py")


@dataclass
class QuestionDraft:
    id: str
    content: str
    conversation_id: str
    creation_attempted: bool = False
    error: str | None = None


def _queue_question(user_id: str, conversation_id: str | None) -> None:
    prompt = (st.session_state.get("chat_prompt") or "").strip()
    if prompt:
        st.session_state.get("chat_openings", {}).pop((user_id, conversation_id), None)
        drafts = st.session_state.setdefault("chat_question_drafts", {})
        drafts.setdefault(
            (user_id, conversation_id),
            QuestionDraft(str(uuid4()), prompt, conversation_id or str(uuid4())),
        )


def _retry_question(draft: QuestionDraft) -> None:
    draft.error = None


def _render_question_retry(draft: QuestionDraft) -> None:
    st.button("保存を再試行する", key="retry_save_question", on_click=_retry_question, args=(draft,))


def _retry_reply(conversation_id: str, question_id: str) -> None:
    st.session_state.chat_reply_request = (conversation_id, question_id)


def _retry_opening(user_id: str, conversation_id: str) -> None:
    st.session_state["chat_openings"][(user_id, conversation_id)] = "retry"


def _reply_pokemon(names: list[str], builds: PokemonBuildMap) -> list[ReplyPokemon]:
    pokemon: list[ReplyPokemon] = []
    unset = {"", "指定なし", "指定しない", "未設定", "特性データを取得できません"}
    for name in names:
        build = builds.get(name, {})
        info: ReplyPokemon = {"name": name}
        if moves := [move for move in build.get("moves", []) if move not in unset]:
            info["moves"] = moves
        if (nature := build.get("nature", "")) not in unset:
            info["nature"] = nature
        if (ability := build.get("ability", "")) not in unset:
            info["ability"] = ability
        if (item := build.get("item", "")) not in unset:
            info["item"] = item
        if stats := build.get("actual_stats"):
            info["actual_stats"] = dict(stats)
        pokemon.append(info)
    return pokemon


def _render_reply(
    store: ConversationStore,
    conversation_id: str,
    question_id: str | None,
    pokemon: list[ReplyPokemon],
) -> None:
    saved_answer = None

    def chunks():
        nonlocal saved_answer
        saved_answer = yield from stream_reply(store, conversation_id, question_id, pokemon=pokemon)

    reply = st.empty()
    try:
        with reply.container(), st.chat_message("assistant"):
            text = st.empty()
            with text.container(), st.spinner("回答を考えています…"), closing(chunks()) as stream:
                displayed = st.write_stream(stream)
            if displayed != saved_answer:
                text.markdown(saved_answer)
    except (ChatError, ConversationError):
        reply.empty()
        raise


def _show_question(slot, draft: QuestionDraft):
    with slot.container(), st.chat_message("user"):
        st.write(draft.content)
        status = st.empty()
        if draft.error:
            status.error(draft.error)
        else:
            status.caption("保存中…")
        return status


def _save_question(
    store: ConversationStore, conversation_id: str | None, draft: QuestionDraft, drafts: dict,
) -> dict:
    if conversation_id is None:
        conversation_id = draft.conversation_id
        # A retry can recover a conversation whose insert committed before the response was lost.
        existing = store.get(conversation_id) if draft.creation_attempted else None
        if existing is None:
            draft.creation_attempted = True
            store.create(conversation_id=conversation_id)
        drafts[(store.user_id, conversation_id)] = drafts.pop((store.user_id, None))
        st.query_params["conversation_id"] = conversation_id
        st.session_state.active_conversation_id = conversation_id
    return store.save_question(conversation_id, draft.id, draft.content)


def _render_chat_header(pokemon_names: list[str], builds: PokemonBuildMap) -> None:

    st.markdown(
        '<div class="step-label">05　チャット / 相棒の勝ち筋を探す</div>'
        '<div class="page-eyebrow">POKEMON CHAMPIONS　 ·　 相談</div>',
        unsafe_allow_html=True,
    )
    if pokemon_names:
        partner_name = pokemon_names[1] if len(pokemon_names) > 1 else ""
        _render_pokemon_banner(pokemon_names[0], partner_name)

    st.markdown(
        '<div class="chat-intro"><span class="chat-intro-mark">✦</span>'
        '<div><b>推しポケラボ</b><p>ポケモンの育成や対戦について AI と相談できます。<br>'
        'メッセージと AI の回答はこの会話の履歴に保存されます。</p></div></div>',
        unsafe_allow_html=True,
    )

    if pokemon_names:
        for pokemon_name in pokemon_names:
            _render_build_card(pokemon_name, builds.get(pokemon_name))
        _render_edit_build_button(pokemon_names[0])


def render() -> None:
    configure_page("推しポケラボ | 相談", "pokemon.css")
    raw_id = st.query_params.get("conversation_id")
    conversation_id = conversation_id_from_url(raw_id)
    header = st.container()
    history = st.container()
    pending = st.empty()
    controls = st.container()

    drafts = st.session_state.get("chat_question_drafts", {})
    account = st.session_state.get("current_account")
    draft = None
    if account and st.session_state.get("auth_client") is not None:
        draft = drafts.get((str(account.id), conversation_id))
    # Only this session's own draft is shown before checking the account and reading stored messages.
    draft_status = _show_question(pending, draft) if draft else None

    store = require_conversation_store()
    verified_draft = drafts.get((store.user_id, conversation_id))
    if draft is not verified_draft:
        pending.empty()
        draft = verified_draft
        draft_status = _show_question(pending, draft) if draft else None

    try:
        messages = store.find_messages(conversation_id) if conversation_id else []
    except ConversationError as error:
        if draft is None:
            raise
        draft.error = str(error)
        draft_status.error(draft.error)
        with controls:
            _render_question_retry(draft)
        return
    if raw_id and (conversation_id is None or messages is None):
        pending.empty()
        st.warning("この会話は開けません。履歴から選ぶか、新しい相談を始めてください。")
        render_sidebar(store)
        return

    openings = st.session_state.setdefault("chat_openings", {})
    opening_key = (store.user_id, conversation_id)
    if messages or draft:
        openings.pop(opening_key, None)
    opening_status = openings.get(opening_key)
    start_opening = opening_status == "retry" or (
        opening_status == "queued" and st.query_params.get("opening") == "1"
    )
    if start_opening:
        # Keep an explicit retry available if the page reruns before the save.
        openings[opening_key] = "failed"
    st.query_params.pop("opening", None)

    pokemon_names = st.session_state.get("conversation_pokemon", {}).get(conversation_id, [])
    builds = conversation_builds(store.user_id, conversation_id)
    reply_pokemon = _reply_pokemon(pokemon_names, builds)
    with header:
        _render_chat_header(pokemon_names, builds)
    with history:
        if messages or draft or start_opening:
            st.markdown('<div class="chat-section-heading">会話</div>', unsafe_allow_html=True)
            for message in messages:
                with st.chat_message(message["role"]):
                    st.write(message["content"])
        else:
            st.markdown(
                '<div class="chat-empty-note">相談したいことを入力してください。過去の発言がある場合は、この下に表示されます。</div>',
                unsafe_allow_html=True,
            )

    awaiting_reply = bool(messages and messages[-1]["role"] == "user")
    question_id = str(messages[-1]["id"]) if awaiting_reply else None
    reply_request = st.session_state.pop("chat_reply_request", None)
    start_reply = reply_request == (conversation_id, question_id)
    if draft and any(str(message["id"]) == draft.id for message in messages):
        pending.empty()
        drafts.pop((store.user_id, conversation_id))
        start_reply = start_reply or (question_id == draft.id and draft.error is None)
        draft = None
    elif draft and draft.error is None:
        try:
            question = _save_question(store, conversation_id, draft, drafts)
        except ConversationError as error:
            conversation_id = conversation_id_from_url(st.query_params.get("conversation_id"))
            draft.error = str(error)
            draft_status.error(draft.error)
        else:
            conversation_id = draft.conversation_id
            drafts.pop((store.user_id, conversation_id))
            draft_status.empty()
            draft = None
            question_id = str(question["id"])
            awaiting_reply = start_reply = True
            st.session_state.pop(f"conversation_history:{store.user_id}", None)

    with controls:
        if conversation_id and start_opening:
            try:
                _render_reply(store, conversation_id, None, reply_pokemon)
            except (ChatError, ConversationError) as error:
                st.error(str(error))
            else:
                openings.pop(opening_key, None)
                st.session_state.pop(f"conversation_history:{store.user_id}", None)
        if conversation_id and openings.get(opening_key) == "failed":
            st.button(
                "最初のメッセージを再試行する",
                key="retry_chat_opening",
                on_click=_retry_opening,
                args=(store.user_id, conversation_id),
            )
        if awaiting_reply and start_reply:
            try:
                _render_reply(store, conversation_id, question_id, reply_pokemon)
            except (ChatError, ConversationError) as error:
                st.error(str(error))
            else:
                awaiting_reply = False
                st.session_state.pop(f"conversation_history:{store.user_id}", None)
        if awaiting_reply:
            st.button(
                "回答を再試行する", key="retry_chat_reply",
                on_click=_retry_reply, args=(conversation_id, question_id),
            )
        if draft:
            _render_question_retry(draft)

    st.chat_input(
        "相棒のこと、気になることを聞いてみよう",
        key="chat_prompt",
        disabled=awaiting_reply or draft is not None,
        on_submit=_queue_question,
        args=(store.user_id, conversation_id),
    )
    render_sidebar(store)


render()
