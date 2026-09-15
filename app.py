"""Adrastea Research Library — search space-science literature and build a collection.

Run:  py -m streamlit run app.py
"""
from __future__ import annotations

import html

import streamlit as st

import brand
import db
import export
import sources

st.set_page_config(page_title="Adrastea Research Library",
                   page_icon="🛰️", layout="wide")

# Mission-aligned starting points. With the space scope on, these stay topic-focused —
# the scope supplies the "in space" context, so results narrow to the mission.
PRESETS = [
    "bone density loss",
    "reproductive health",
    "immune function",
    "cardiovascular changes",
    "radiation exposure",
    "muscle atrophy",
    "tissue engineering",
    "mental health cognition",
]
_SORT_LABELS = {"relevance": "Relevance", "cited": "Most cited", "newest": "Newest"}

st.session_state.setdefault("results", [])
st.session_state.setdefault("errors", {})
st.session_state.setdefault("totals", {})
st.session_state.setdefault("query", "")


def run_search(query: str) -> None:
    # No caching: results live in session_state (so Save/Remove reruns don't refetch),
    # and caching would pin a transient upstream failure for everyone who re-searches.
    query = (query or "").strip()
    if not query:
        return
    srcs = tuple(st.session_state.get("src_sel") or sources.SOURCES)
    limit = int(st.session_state.get("limit_sel", 20))
    space_only = bool(st.session_state.get("space_only", True))
    women_lens = bool(st.session_state.get("women_lens", False))
    sort = st.session_state.get("sort_sel", "relevance")
    with st.spinner(f"Searching {', '.join(srcs)}…"):
        res, err, tot = sources.search(query, srcs, limit, space_only, women_lens, sort)
    st.session_state.update(results=res, errors=err, totals=tot, query=query)


def _note_cb(uid: str, key: str) -> None:
    db.set_note(uid, st.session_state[key])


# --------------------------------------------------------------------------- #
# Sidebar — search scope + about
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.markdown(f'<div class="brandbar">{brand.mark(28)}'
                f'<span class="name" style="font-size:1.15rem">Adrastea</span></div>',
                unsafe_allow_html=True)
    st.toggle("🛰️ Space research only", value=True, key="space_only",
              help="Keep only papers about spaceflight, microgravity, astronauts, etc. "
                   "Cuts out the ~99% of biomedical results with no space context.")
    st.toggle("♀ Women's-health focus", value=False, key="women_lens",
              help="Further narrow to sex differences, female physiology, reproductive "
                   "and maternal health. Off by default so male-subject studies — the "
                   "disparity itself — stay visible.")
    st.selectbox("Sort by", list(_SORT_LABELS), key="sort_sel",
                 format_func=_SORT_LABELS.get)
    st.divider()
    st.multiselect("Sources", sources.SOURCES, default=list(sources.SOURCES),
                   key="src_sel",
                   help="Europe PMC covers biomedical & women's-health literature; "
                        "arXiv covers bioengineering, physics and space science.")
    st.slider("Results per source", 10, 50, 20, 5, key="limit_sel")
    st.divider()
    st.caption("Adrastea is a non-profit working to bridge the gender gap in space. "
               "This tool searches open scholarly databases — no account, no tracking. "
               "Saved papers stay in a local file on your machine.")

brand.header()
search_tab, coll_tab = st.tabs(
    ["Search", f"My Collection ({len(db.saved_uids())})"])

# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #
with search_tab:
    st.write("")
    st.markdown('<span class="meta">Start here</span>', unsafe_allow_html=True)
    cols = st.columns(4)
    for i, preset in enumerate(PRESETS):
        if cols[i % 4].button(preset, key=f"preset_{i}", use_container_width=True):
            run_search(preset)

    with st.form("search", clear_on_submit=False):
        c1, c2 = st.columns([5, 1])
        q = c1.text_input("Search", value=st.session_state.query,
                          placeholder="e.g. immune function female astronauts",
                          label_visibility="collapsed")
        if c2.form_submit_button("Search", use_container_width=True, type="primary"):
            run_search(q)

    for src, msg in st.session_state.errors.items():
        st.warning(f"{src} couldn't be reached: {msg}")

    results = st.session_state.results
    if st.session_state.query and not results:
        st.info(f"No results for “{st.session_state.query}”. Try broader terms, "
                "turn off “Space research only”, or widen the sources in the sidebar.")
    elif results:
        totals = st.session_state.totals
        total = sum(totals.values())
        breakdown = " + ".join(f"{n} {v:,}" for n, v in totals.items())
        scope = [s for s, on in (("space-scoped", st.session_state.get("space_only")),
                                 ("women's-health", st.session_state.get("women_lens")))
                 if on]
        scope_txt = (" · " + " · ".join(scope)) if scope else ""
        sort_txt = _SORT_LABELS[st.session_state.get("sort_sel", "relevance")].lower()
        st.caption(f"{total:,} papers match ({breakdown}) · showing top "
                   f"{len(results)} · sorted by {sort_txt}{scope_txt}")
        saved = db.saved_uids()
        for p in results:
            with st.container(border=True):
                st.markdown(f"#### {html.escape(p['title'])}")
                meta = " · ".join(x for x in (
                    html.escape(p["authors"][:140] +
                                ("…" if len(p["authors"]) > 140 else "")),
                    p["year"], html.escape(p["venue"])) if x)
                cite = f" · cited {p['cited_by']}" if p["cited_by"] else ""
                st.markdown(f'<span class="badge">{p["source"]}</span> '
                            f'<span class="meta">{meta}{cite}</span>',
                            unsafe_allow_html=True)
                ab = p["abstract"]
                if ab:
                    st.caption(ab[:360] + ("…" if len(ab) > 360 else ""))
                    if len(ab) > 360:
                        with st.expander("Read full abstract"):
                            st.write(ab)
                else:
                    st.caption("No abstract available.")
                b1, b2, _ = st.columns([1, 1, 4])
                if p["uid"] in saved:
                    b1.button("✓ In collection", key=f"s_{p['uid']}", disabled=True,
                              use_container_width=True)
                elif b1.button("＋ Save", key=f"s_{p['uid']}",
                               use_container_width=True):
                    db.save(p)
                    st.rerun()
                if p["url"]:
                    b2.link_button("Open ↗", p["url"], use_container_width=True)
    else:
        st.caption("Pick a topic above or type your own search to begin.")

# --------------------------------------------------------------------------- #
# Collection
# --------------------------------------------------------------------------- #
with coll_tab:
    st.write("")
    saved = db.list_saved()
    if not saved:
        st.info("Your collection is empty. Save papers from the Search tab and they'll "
                "appear here — stored locally, exportable to CSV or BibTeX.")
    else:
        d1, d2, _ = st.columns([1, 1, 3])
        d1.download_button("⬇ CSV", export.to_csv(saved),
                           "adrastea_collection.csv", "text/csv",
                           use_container_width=True)
        d2.download_button("⬇ BibTeX", export.to_bibtex(saved),
                           "adrastea_collection.bib", "text/plain",
                           use_container_width=True)
        for p in saved:
            with st.container(border=True):
                st.markdown(f"#### {html.escape(p['title'])}")
                meta = " · ".join(x for x in (
                    html.escape(p["authors"][:140]), p["year"],
                    html.escape(p["venue"])) if x)
                st.markdown(f'<span class="badge">{p["source"]}</span> '
                            f'<span class="meta">{meta}</span>', unsafe_allow_html=True)
                key = f"note_{p['uid']}"
                st.text_input("Note", value=p["note"], key=key,
                              placeholder="Why this matters, where you cited it…",
                              on_change=_note_cb, args=(p["uid"], key))
                b1, b2, _ = st.columns([1, 1, 4])
                if p["url"]:
                    b1.link_button("Open ↗", p["url"], use_container_width=True)
                if b2.button("Remove", key=f"rm_{p['uid']}", use_container_width=True):
                    db.remove(p["uid"])
                    st.rerun()
