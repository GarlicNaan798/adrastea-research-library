"""Adrastea visual identity for Streamlit — palette, mark, badges, and page styling.

Kept in sync with .streamlit/config.toml and the Adrastea brand kit.
"""
from __future__ import annotations

import html

import streamlit as st

PAPER, INK, CLAY, NAVY, STONE = "#FBFAF7", "#23211C", "#9E6B4B", "#17263A", "#E7E3D8"

# Each source gets a low-saturation badge colour so results are scannable by provenance.
_BADGE = {
    "Europe PMC": "navy",
    "arXiv": "olive",
    "OpenAlex": "plum",
    "NASA OSDR": "teal",
    "bioRxiv": "clay",
    "medRxiv": "clay",
}


def source_badge(source: str) -> str:
    cls = _BADGE.get(source, "gray")
    return f'<span class="badge badge-{cls}">{html.escape(source)}</span>'


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
/* Keep Streamlit's Material icons on their icon font — otherwise the broad rule above
   turns ligatures into raw text (e.g. the sidebar collapse control rendering
   "keyboard_double_arrow_left"), which also makes the collapsed sidebar impossible to
   reopen. */
[data-testid="stIconMaterial"] {{ font-family: 'Material Symbols Rounded' !important; }}
h1, h2, h3 {{ font-family: 'Fraunces', Georgia, serif; letter-spacing: -0.01em; }}
h1 {{ font-weight: 600; }} h2, h3 {{ font-weight: 500; }}
/* Result-card titles stay sans for a dense, scannable list */
h4 {{ font-family: 'Inter', sans-serif; font-weight: 600; font-size: 1.05rem;
    line-height: 1.35; letter-spacing: -.01em; margin: .1rem 0 .4rem; color: {INK}; }}

.block-container {{ max-width: 1040px; padding-top: 2rem; padding-bottom: 4rem; }}

/* Hide the menu/deploy chrome — but NOT the whole toolbar, which contains the sidebar
   expand button (hiding it made a collapsed sidebar impossible to reopen). */
#MainMenu, [data-testid="stMainMenu"], [data-testid="stDecoration"],
[data-testid="stDeployButton"], .stDeployButton, footer {{ display: none !important; }}
[data-testid="stHeader"] {{ background: transparent; }}

/* Header */
.overline {{ font-size: .7rem; letter-spacing: .22em; text-transform: uppercase;
    color: {CLAY}; font-weight: 600; margin: 0 0 .35rem 2px; }}
.brandbar {{ display:flex; align-items:center; gap:.6rem; padding:0 0 .2rem; }}
.brandbar .name {{ font-family:'Fraunces',Georgia,serif; font-size:1.65rem;
    font-weight:600; color:{INK}; letter-spacing:-.015em; }}
.tagline {{ color: rgba(35,33,28,.6); font-size:.95rem; margin:.25rem 0 .1rem 2px;
    max-width: 60ch; }}

/* Cards */
[data-testid="stVerticalBlockBorderWrapper"] {{
    border-radius:14px; border-color:rgba(35,33,28,.10);
    transition: border-color .15s ease, box-shadow .15s ease; }}
[data-testid="stVerticalBlockBorderWrapper"]:hover {{
    border-color:rgba(158,107,75,.4); box-shadow:0 3px 16px rgba(35,33,28,.05); }}

/* Source badges */
.badge {{ display:inline-block; font-size:.64rem; font-weight:700; letter-spacing:.06em;
    text-transform:uppercase; padding:.16rem .55rem; border-radius:999px;
    vertical-align:middle; }}
.badge-navy  {{ color:#17263A; background:rgba(23,38,58,.10); }}
.badge-clay  {{ color:#8a5636; background:rgba(158,107,75,.14); }}
.badge-olive {{ color:#555f38; background:rgba(88,104,66,.16); }}
.badge-plum  {{ color:#6b4a6b; background:rgba(107,74,107,.13); }}
.badge-teal  {{ color:#2f6a6a; background:rgba(47,106,106,.13); }}
.badge-gray  {{ color:#5b574e; background:rgba(35,33,28,.08); }}
.meta {{ color: rgba(35,33,28,.58); font-size:.85rem; }}

/* Buttons — only the primary Search keeps the accent; the rest are quiet */
.stButton > button, .stDownloadButton > button, [data-testid="stLinkButton"] a {{
    border-radius:8px; box-shadow:none; font-weight:500; font-size:.85rem;
    min-height:0; padding:.32rem .8rem; }}
.stButton > button[kind="secondary"], .stDownloadButton > button,
[data-testid="stLinkButton"] a {{
    border:1px solid rgba(35,33,28,.16); color:{INK}; background:transparent; }}
.stButton > button[kind="secondary"]:hover, .stDownloadButton > button:hover,
[data-testid="stLinkButton"] a:hover {{ border-color:{CLAY}; color:{CLAY}; }}
.stButton > button:disabled {{ opacity:.55; }}

/* Preset pills */
[data-testid="stPills"] button {{ font-size:.85rem; }}

[data-testid="stSidebar"] {{ border-right:1px solid rgba(0,0,0,.06); }}
[data-testid="stExpander"] {{ border:none; }}
[data-testid="stExpander"] summary {{ font-size:.82rem; color:{CLAY}; padding-left:0; }}
hr {{ margin:1rem 0; opacity:.5; }}
.stTabs [data-baseweb="tab-list"] {{ gap:1.6rem; }}
</style>
"""


def apply_style() -> None:
    st.markdown(_STYLE, unsafe_allow_html=True)


def header() -> None:
    apply_style()
    st.markdown('<div class="overline">Bridging the gender gap in space</div>',
                unsafe_allow_html=True)
    st.markdown(
        f'<div class="brandbar">{mark(38)}'
        f'<span class="name">Adrastea Research Library</span></div>',
        unsafe_allow_html=True)
    st.markdown(
        '<div class="tagline">Search the science of women\'s health, bioengineering, '
        'and equity in spaceflight — and build a collection worth keeping.</div>',
        unsafe_allow_html=True)
