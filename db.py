"""Local SQLite collection of saved papers. Single file, zero config, dedup by uid.

Every function takes an optional `path` so tests can point at a temp DB (or ":memory:"
won't persist across connections, so tests use a temp file).
"""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).with_name("collection.db")
_COLS = ("uid", "title", "authors", "year", "venue",
         "abstract", "doi", "url", "source", "note")


@contextmanager
def _conn(path=None):
    """Open a connection, ensure the schema, commit on success, and always close.

    `with sqlite3.connect(...)` only manages the transaction — it leaves the handle
    open, which locks the file on Windows. This closes it.
    """
    c = sqlite3.connect(str(path or DB_PATH))
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS papers(
        uid TEXT PRIMARY KEY, title TEXT, authors TEXT, year TEXT, venue TEXT,
        abstract TEXT, doi TEXT, url TEXT, source TEXT, note TEXT DEFAULT '',
        saved_at REAL)""")
    try:
        yield c
        c.commit()
    finally:
        c.close()


def save(paper: dict, path=None) -> bool:
    """Insert if new. Returns False (and changes nothing) if the uid is already saved."""
    with _conn(path) as c:
        if c.execute("SELECT 1 FROM papers WHERE uid=?", (paper["uid"],)).fetchone():
            return False
        c.execute(
            f"INSERT INTO papers({','.join(_COLS)},saved_at) "
            f"VALUES({','.join('?' * len(_COLS))},?)",
            tuple(str(paper.get(k, "")) for k in _COLS) + (time.time(),))
    return True


def remove(uid: str, path=None) -> None:
    with _conn(path) as c:
        c.execute("DELETE FROM papers WHERE uid=?", (uid,))


def set_note(uid: str, note: str, path=None) -> None:
    with _conn(path) as c:
        c.execute("UPDATE papers SET note=? WHERE uid=?", (note, uid))


def list_saved(path=None) -> list[dict]:
    with _conn(path) as c:
        return [dict(r) for r in
                c.execute("SELECT * FROM papers ORDER BY saved_at DESC")]


def saved_uids(path=None) -> set[str]:
    with _conn(path) as c:
        return {r["uid"] for r in c.execute("SELECT uid FROM papers")}
