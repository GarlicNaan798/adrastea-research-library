"""In-session collection of saved papers — a uid -> paper dict.

Backed by st.session_state (see app.py), so each visitor's collection is private and
needs no server or shared file. That's what makes the app safe to host publicly.
Persistence is by CSV/BibTeX export and CSV re-import (see export.py).

Functions operate on a plain dict so they stay unit-testable without a Streamlit runtime.
"""
from __future__ import annotations

import time


def save(store: dict, paper: dict) -> bool:
    """Add if new. Returns False (changes nothing) if the uid is already saved."""
    if paper["uid"] in store:
        return False
    store[paper["uid"]] = {**paper, "note": paper.get("note", ""), "saved_at": time.time()}
    return True


def remove(store: dict, uid: str) -> None:
    store.pop(uid, None)


def set_note(store: dict, uid: str, note: str) -> None:
    if uid in store:
        store[uid]["note"] = note


def list_saved(store: dict) -> list[dict]:
    return sorted(store.values(), key=lambda p: p.get("saved_at", 0), reverse=True)


def saved_uids(store: dict) -> set[str]:
    return set(store)
