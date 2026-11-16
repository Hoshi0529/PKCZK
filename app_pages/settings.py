import re

import streamlit as st

from back.auth import (
    AuthenticationError,
    ReauthenticationRequired,
    request_password_reauthentication,
    sign_out_account,
    update_account_user,
)
from ui.chat_session import require_conversation_store
from ui.layout import configure_page
from ui.sidebar import render_sidebar


def _logout() -> None:
    client = st.session_state.get("auth_client")
    server_logout_succeeded = sign_out_account(client) if client is not None else True

    # Keep widgets already rendered on this page and discard account/chat state.
    active_widget_keys = {
        "shared_sidebar_settings",
        "shared_sidebar_new_advice",
        "settings_logout",
        "settings_new_email",
        "settings_new_username",
        "settings_current_password",
        "settings_new_password",
        "settings_confirm_password",
        "settings_password_reauth_nonce",
    }
    for key in list(st.session_state.keys()):
        if key not in active_widget_keys:
            st.session_state.pop(key, None)

    st.query_params.clear()
    st.session_state["clear_account_passwords"] = True
    st.session_state["clear_setting_fields_on_login"] = True
    if not server_logout_succeeded:
        st.session_state["account_notice"] = (
            "\u7aef\u672b\u306e\u30ed\u30b0\u30a4\u30f3\u72b6\u614b\u3092\u7d42\u4e86\u3057\u307e\u3057\u305f\u3002"
            "\u30b5\u30fc\u30d0\u30fc\u3068\u306e\u901a\u4fe1\u306b\u5931\u6557\u3057\u305f\u305f\u3081\u3001"
            "\u5fc5\u8981\u306a\u5834\u5408\u306f\u5f8c\u307b\u3069\u518d\u5ea6\u30ed\u30b0\u30a4\u30f3\u3057\u3066\u304f\u3060\u3055\u3044\u3002"
        )
    st.switch_page("app_pages/login.py")


def _set_notice(level: str, message: str) -> None:
    st.session_state.settings_notice = (level, message)
    st.rerun()


def render() -> None:
    configure_page("\u63a8\u3057\u30dd\u30b1\u30e9\u30dc | \u8a2d\u5b9a", "setting.css")
    store = require_conversation_store()

    if st.session_state.pop("clear_setting_password_fields", False):
        for key in (
            "settings_current_password",
            "settings_new_password",
            "settings_confirm_password",
            "settings_password_reauth_nonce",
        ):
            st.session_state.pop(key, None)

    render_sidebar(store)
    st.markdown(
        '<div class="page-eyebrow">SETTINGS</div>'
        '<h1 class="page-title">\u8a2d\u5b9a</h1>'
        '<p class="page-description">\u30a2\u30ab\u30a6\u30f3\u30c8\u60c5\u5831\u3092\u5909\u66f4\u3067\u304d\u307e\u3059\u3002</p>',
        unsafe_allow_html=True,
    )
    notice = st.session_state.pop("settings_notice", None)
    if notice:
        level, message = notice
        getattr(st, level)(message)

    user = st.session_state.current_account
    current_email = getattr(user, "email", "") or ""
    metadata = getattr(user, "user_metadata", None) or {}
    current_username = metadata.get("username", "") if isinstance(metadata, dict) else ""
    if not isinstance(current_username, str):
        current_username = ""
    if not current_username and current_email:
        current_username = current_email.split("@", 1)[0]

    with st.container(border=True, key="account_changes_card"):
        st.markdown('<div class="account-heading">\u30a2\u30ab\u30a6\u30f3\u30c8\u540d\u5909\u66f4</div>', unsafe_allow_html=True)
        with st.form("username_change_form"):
            new_username = st.text_input(
                "\u65b0\u3057\u3044\u30a2\u30ab\u30a6\u30f3\u30c8\u540d",
                value=current_username,
                max_chars=50,
                key="settings_new_username",
            )
            username_submitted = st.form_submit_button(
                "\u30a2\u30ab\u30a6\u30f3\u30c8\u540d\u3092\u5909\u66f4",
                use_container_width=True,
            )
        if username_submitted:
            normalized_username = new_username.strip()
            if not normalized_username:
                st.error("\u30a2\u30ab\u30a6\u30f3\u30c8\u540d\u3092\u5165\u529b\u3057\u3066\u304f\u3060\u3055\u3044\u3002")
            elif normalized_username == current_username:
                st.info("\u73fe\u5728\u3068\u540c\u3058\u30a2\u30ab\u30a6\u30f3\u30c8\u540d\u3067\u3059\u3002")
            else:
                merged_metadata = dict(metadata) if isinstance(metadata, dict) else {}
                merged_metadata["username"] = normalized_username
                try:
                    updated_user = update_account_user(
                        st.session_state.auth_client,
                        {"data": merged_metadata},
                    )
                except AuthenticationError as error:
                    st.error(str(error))
                else:
                    st.session_state.current_account = updated_user
                    _set_notice("success", "\u30a2\u30ab\u30a6\u30f3\u30c8\u540d\u3092\u5909\u66f4\u3057\u307e\u3057\u305f\u3002")

        st.markdown('<div class="account-heading settings-section-divider">\u30e1\u30fc\u30eb\u30a2\u30c9\u30ec\u30b9\u5909\u66f4</div>', unsafe_allow_html=True)
        with st.form("email_change_form"):
            new_email = st.text_input(
                "\u65b0\u3057\u3044\u30e1\u30fc\u30eb\u30a2\u30c9\u30ec\u30b9",
                value=current_email,
                key="settings_new_email",
            )
            email_submitted = st.form_submit_button(
                "\u30e1\u30fc\u30eb\u30a2\u30c9\u30ec\u30b9\u3092\u5909\u66f4",
                use_container_width=True,
            )
        if email_submitted:
            normalized_email = new_email.strip()
            if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized_email):
                st.error("\u6709\u52b9\u306a\u30e1\u30fc\u30eb\u30a2\u30c9\u30ec\u30b9\u3092\u5165\u529b\u3057\u3066\u304f\u3060\u3055\u3044\u3002")
            elif normalized_email.casefold() == current_email.casefold():
                st.info("\u73fe\u5728\u3068\u540c\u3058\u30e1\u30fc\u30eb\u30a2\u30c9\u30ec\u30b9\u3067\u3059\u3002")
            else:
                try:
                    updated_user = update_account_user(
                        st.session_state.auth_client,
                        {"email": normalized_email},
                    )
                except AuthenticationError as error:
                    st.error(str(error))
                else:
                    st.session_state.current_account = updated_user
                    if getattr(updated_user, "email", None) == normalized_email:
                        message = "\u30e1\u30fc\u30eb\u30a2\u30c9\u30ec\u30b9\u3092\u5909\u66f4\u3057\u307e\u3057\u305f\u3002"
                    else:
                        message = (
                            "\u78ba\u8a8d\u30e1\u30fc\u30eb\u3092\u9001\u4fe1\u3057\u307e\u3057\u305f\u3002"
                            "\u73fe\u5728\u3068\u65b0\u3057\u3044\u30e1\u30fc\u30eb\u30a2\u30c9\u30ec\u30b9\u306e\u4e21\u65b9\u3067\u78ba\u8a8d\u30ea\u30f3\u30af\u3092\u958b\u304f\u3068\u5909\u66f4\u304c\u5b8c\u4e86\u3057\u307e\u3059\u3002"
                        )
                    _set_notice("success", message)

        st.markdown('<div class="account-heading settings-section-divider">\u30d1\u30b9\u30ef\u30fc\u30c9\u5909\u66f4</div>', unsafe_allow_html=True)
        reauth_required = st.session_state.get("password_reauth_required", False)
        with st.form("password_change_form"):
            current_password = st.text_input(
                "\u73fe\u5728\u306e\u30d1\u30b9\u30ef\u30fc\u30c9",
                type="password",
                key="settings_current_password",
            )
            new_password = st.text_input(
                "\u65b0\u3057\u3044\u30d1\u30b9\u30ef\u30fc\u30c9\uff088\u6587\u5b57\u4ee5\u4e0a\uff09",
                type="password",
                key="settings_new_password",
            )
            confirm_password = st.text_input(
                "\u65b0\u3057\u3044\u30d1\u30b9\u30ef\u30fc\u30c9\uff08\u78ba\u8a8d\uff09",
                type="password",
                key="settings_confirm_password",
            )
            reauth_nonce = ""
            if reauth_required:
                reauth_nonce = st.text_input(
                    "\u30e1\u30fc\u30eb\u306b\u5c4a\u3044\u305f\u78ba\u8a8d\u30b3\u30fc\u30c9",
                    key="settings_password_reauth_nonce",
                )
            password_submitted = st.form_submit_button(
                "\u30d1\u30b9\u30ef\u30fc\u30c9\u3092\u5909\u66f4",
                use_container_width=True,
            )
        if password_submitted:
            if not current_password:
                st.error("\u73fe\u5728\u306e\u30d1\u30b9\u30ef\u30fc\u30c9\u3092\u5165\u529b\u3057\u3066\u304f\u3060\u3055\u3044\u3002")
            elif len(new_password) < 8:
                st.error("\u65b0\u3057\u3044\u30d1\u30b9\u30ef\u30fc\u30c9\u306f8\u6587\u5b57\u4ee5\u4e0a\u3067\u5165\u529b\u3057\u3066\u304f\u3060\u3055\u3044\u3002")
            elif new_password != confirm_password:
                st.error("\u78ba\u8a8d\u7528\u306e\u30d1\u30b9\u30ef\u30fc\u30c9\u304c\u4e00\u81f4\u3057\u307e\u305b\u3093\u3002")
            elif new_password == current_password:
                st.error("\u73fe\u5728\u3068\u306f\u7570\u306a\u308b\u30d1\u30b9\u30ef\u30fc\u30c9\u3092\u6307\u5b9a\u3057\u3066\u304f\u3060\u3055\u3044\u3002")
            elif reauth_required and not reauth_nonce.strip():
                st.error("\u30e1\u30fc\u30eb\u306b\u5c4a\u3044\u305f\u78ba\u8a8d\u30b3\u30fc\u30c9\u3092\u5165\u529b\u3057\u3066\u304f\u3060\u3055\u3044\u3002")
            else:
                password_attributes = {
                    "password": new_password,
                    "current_password": current_password,
                }
                if reauth_required:
                    password_attributes["nonce"] = reauth_nonce.strip()
                try:
                    updated_user = update_account_user(
                        st.session_state.auth_client,
                        password_attributes,
                    )
                except ReauthenticationRequired:
                    try:
                        request_password_reauthentication(st.session_state.auth_client)
                    except AuthenticationError as error:
                        st.error(str(error))
                    else:
                        st.session_state.password_reauth_required = True
                        _set_notice(
                            "info",
                            "\u30bb\u30ad\u30e5\u30ea\u30c6\u30a3\u78ba\u8a8d\u306e\u305f\u3081\u78ba\u8a8d\u30b3\u30fc\u30c9\u3092\u9001\u4fe1\u3057\u307e\u3057\u305f\u3002\u30e1\u30fc\u30eb\u3092\u78ba\u8a8d\u3057\u3066\u5165\u529b\u3057\u3066\u304f\u3060\u3055\u3044\u3002",
                        )
                except AuthenticationError as error:
                    st.error(str(error))
                else:
                    st.session_state.current_account = updated_user
                    st.session_state.clear_setting_password_fields = True
                    st.session_state.pop("password_reauth_required", None)
                    _set_notice("success", "\u30d1\u30b9\u30ef\u30fc\u30c9\u3092\u5909\u66f4\u3057\u307e\u3057\u305f\u3002")

    with st.container(border=True, key="account_card"):
        st.markdown('<div class="account-heading">\u30ed\u30b0\u30a2\u30a6\u30c8</div>', unsafe_allow_html=True)
        st.markdown(
            '<p class="logout-description">\u30ed\u30b0\u30a2\u30a6\u30c8\u3059\u308b\u3068\u3001\u3053\u306e\u7aef\u672b\u306e\u30ed\u30b0\u30a4\u30f3\u72b6\u614b\u304c\u7d42\u4e86\u3057\u307e\u3059\u3002</p>',
            unsafe_allow_html=True,
        )
        if st.button("\u30ed\u30b0\u30a2\u30a6\u30c8", use_container_width=True, key="settings_logout"):
            _logout()


render()
