"""Adrastea visual identity for Streamlit — palette, mark, and page styling.

Kept in sync with .streamlit/config.toml and the Adrastea brand kit.
"""
from __future__ import annotations

import streamlit as st

PAPER, INK, CLAY, NAVY, STONE = "#FBFAF7", "#23211C", "#9E6B4B", "#17263A", "#E7E3D8"


def mark(size: int = 34, color: str = INK) -> str:
    """Inline Adrastea mark: an 'A' whose crossbar is an orbit, moon on it."""
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 100 100" '
        f'style="display:block;flex:none">'
        f'<path d="M18 86 L50 15 L82 86" fill="none" stroke="{color}" '
        f'stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<ellipse cx="50" cy="56" rx="40" ry="13" fill="none" stroke="{CLAY}" '
        f'stroke-width="3.6" transform="rotate(-18 50 56)"/>'
        f'<circle cx="88" cy="44" r="5.4" fill="{CLAY}"/></svg>'
    )


_STYLE = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Inter:wght@400;500;600&display=swap');

html, body, [class*="st-"], input, textarea, select, button {{
    font-family: 'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif;
}}
h1, h2, h3 {{ font-family: 'Fraunces', Georgia, serif; letter-spacing: -0.01em; }}
h1 {{ font-weight: 600; }} h2, h3 {{ font-weight: 500; }}

.block-container {{ max-width: 1080px; padding-top: 2.2rem; padding-bottom: 4rem; }}

#MainMenu, [data-testid="stToolbar"], [data-testid="stDecoration"],
.stDeployButton, footer {{ display: none !important; }}
[data-testid="stHeader"] {{ background: transparent; }}

.overline {{ font-size: .72rem; letter-spacing: .2em; text-transform: uppercase;
    color: {CLAY}; font-weight: 600; margin: 0 0 .1rem 2px; }}
.brandbar {{ display:flex; align-items:center; gap:.6rem; padding:.1rem 0 .3rem; }}
.brandbar .name {{ font-family:'Fraunces',Georgia,serif; font-size:1.6rem;
    font-weight:600; color:{INK}; letter-spacing:-.01em; }}
.tagline {{ color: rgba(35,33,28,.62); font-size:.95rem; margin:.15rem 0 .2rem 2px; }}

/* Paper cards */
[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius:14px; }}
.badge {{ display:inline-block; font-size:.68rem; font-weight:600; letter-spacing:.04em;
    padding:.12rem .5rem; border-radius:999px; border:1px solid rgba(0,0,0,.12);
    color:{NAVY}; background:rgba(23,38,58,.05); }}
.meta {{ color: rgba(35,33,28,.6); font-size:.86rem; }}

.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {{
    border-radius:8px; box-shadow:none; font-weight:500; }}
[data-testid="stSidebar"] {{ border-right:1px solid rgba(0,0,0,.06); }}
[data-testid="stExpander"] {{ border-radius:10px; }}
hr {{ margin:1.1rem 0; opacity:.5; }}
.stTabs [data-baseweb="tab-list"] {{ gap:1.6rem; }}
</style>
"""


def apply_style() -> None:
    st.markdown(_STYLE, unsafe_allow_html=True)


def header() -> None:
    apply_style()
    st.markdown(
        f'<div class="brandbar">{mark(38)}'
        f'<span class="name">Adrastea Research Library</span></div>',
        unsafe_allow_html=True)
    st.markdown('<div class="overline">Bridging the gender gap in space</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="tagline">Search the science of women\'s health, bioengineering, '
        'and equity in spaceflight — and build a collection worth keeping.</div>',
        unsafe_allow_html=True)
