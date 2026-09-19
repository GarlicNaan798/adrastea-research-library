"""Export a saved collection to CSV or BibTeX. Pure string builders, no I/O."""
from __future__ import annotations

import csv
import io
import re

_FIELDS = ("title", "authors", "year", "venue", "doi", "url", "source", "note")


def to_csv(papers: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=_FIELDS, extrasaction="ignore")
    w.writeheader()
    for p in papers:
        w.writerow({k: p.get(k, "") for k in _FIELDS})
    return buf.getvalue()


def from_csv(text: str) -> list[dict]:
    """Parse a previously-exported CSV back into paper dicts (for re-importing a
    collection). The uid is rebuilt from the DOI, URL, or title so re-imports dedup."""
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        key = (r.get("doi") or r.get("url") or r.get("title") or "").strip().lower()
        if not key:
            continue
        rows.append({
            "uid": f"import:{key}",
            "title": r.get("title", ""), "authors": r.get("authors", ""),
            "year": r.get("year", ""), "venue": r.get("venue", ""), "abstract": "",
            "doi": r.get("doi", ""), "url": r.get("url", ""),
            "source": r.get("source", "") or "Imported",
            "cited_by": 0, "note": r.get("note", ""),
        })
    return rows


def _cite_key(p: dict, used: set[str]) -> str:
    first = (p.get("authors", "").split(",")[0] or "anon").strip()
    surname = re.sub(r"[^A-Za-z]", "", first.split()[-1] if first.split() else "anon")
    word = re.sub(r"[^A-Za-z]", "", (p.get("title", "").split() or ["ref"])[0])
    key = f"{surname or 'anon'}{p.get('year', '') or 'n.d.'}{word}".lower() or "ref"
    base, n = key, 2
    while key in used:            # keys must be unique within one .bib file
        key, n = f"{base}{n}", n + 1
    used.add(key)
    return key


def _esc(v) -> str:
    return str(v or "").replace("{", "(").replace("}", ")")


def to_bibtex(papers: list[dict]) -> str:
    used, entries = set(), []
    for p in papers:
        fields = {
            "title": _esc(p.get("title")),
            "author": _esc(p.get("authors")).replace(", ", " and "),
            "year": _esc(p.get("year")),
            "journal": _esc(p.get("venue")),
            "doi": _esc(p.get("doi")),
            "url": _esc(p.get("url")),
            "note": f"Source: {_esc(p.get('source'))}",
        }
        body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields.items() if v)
        entries.append(f"@article{{{_cite_key(p, used)},\n{body}\n}}")
    return "\n\n".join(entries) + ("\n" if entries else "")
