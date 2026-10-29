from pathlib import Path

import streamlit as st


STYLE_DIR = Path(__file__).parent / "styles"


def configure_page(title: str, stylesheet: str) -> None:
    st.set_page_config(
        page_title=title,
        page_icon="✦",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    css = (STYLE_DIR / "base.css").read_text(encoding="utf-8")
    css += (STYLE_DIR / stylesheet).read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
