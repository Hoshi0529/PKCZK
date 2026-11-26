from html import escape
from pathlib import Path

import streamlit as st


STYLE_DIR = Path(__file__).parent / "styles"


def _load_stylesheet(stylesheet: str) -> str:
    return (STYLE_DIR / "base.css").read_text(encoding="utf-8") + (
        STYLE_DIR / stylesheet
    ).read_text(encoding="utf-8")


def configure_page(
    title: str,
    stylesheet: str,
    breadcrumbs: list[tuple[str, str | None]] | None = None,
) -> None:
    st.set_page_config(
        page_title=title,
        page_icon="✦",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    css = _load_stylesheet(stylesheet)
    st.html(f"<style>{css}</style>")
    if breadcrumbs:
        trail = []
        for label, url in breadcrumbs:
            safe_label = escape(label)
            trail.append(
                f'<a href="{escape(url, quote=True)}">{safe_label}</a>'
                if url
                else f'<span aria-current="page">{safe_label}</span>'
            )
        st.markdown(
            '<nav class="breadcrumb" aria-label="パンくずリスト">'
            + '<a class="breadcrumb-home" href="/new-advice">推しポケラボ</a>'
            + "<span class=\"breadcrumb-separator\">›</span>"
            + '<span class="breadcrumb-items">'
            + '<span class="breadcrumb-separator">›</span>'.join(trail)
            + "</span></nav>",
            unsafe_allow_html=True,
        )
