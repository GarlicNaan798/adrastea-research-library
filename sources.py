"""Free scholarly search over Europe PMC (biomedical) and arXiv (engineering / physics).

No API keys, no third-party deps — just the standard library.

Two precision levers keep the research team out of hundreds of unrelated papers:
  * space_only  — AND a spaceflight/microgravity clause onto every query (default on).
                  In testing this keeps ~0.3–13% of a bare biomedical term's hits, all
                  on-mission. This is the single biggest relevance win.
  * women_lens  — AND a women's-health clause (women / sex differences / reproductive …).
                  Off by default: most historical spaceflight studies used male subjects,
                  and hiding them would hide the very disparity Adrastea studies.

Parsing is split from fetching so the parsers and query-builders stay unit-testable
offline (see tests/test_all.py).
"""
from __future__ import annotations

import html
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

_UA = "AdrasteaResearchLibrary/0.2 (Adrastea non-profit; research discovery)"
_ATOM = {"a": "http://www.w3.org/2005/Atom"}
_ARXIV_NS = "{http://arxiv.org/schemas/atom}"
_OPENSEARCH_TOTAL = "{http://a9.com/-/spec/opensearch/1.1/}totalResults"

SOURCES = ("Europe PMC", "arXiv")
SORTS = ("relevance", "cited", "newest")

# Domain-scoping clauses. Europe PMC accepts quoted phrases; arXiv fields are per-term.
_SPACE_EPMC = ('(spaceflight OR "space flight" OR microgravity OR astronaut OR cosmonaut'
               ' OR "space medicine" OR weightlessness OR "outer space"'
               ' OR "International Space Station" OR "spaceflight environment")')
_WOMEN_EPMC = ('(women OR woman OR female OR "sex differences" OR "sex-based" OR gender'
               ' OR maternal OR reproductive OR menstrual OR pregnancy)')
_SPACE_ARXIV = ("spaceflight", "microgravity", "astronaut", "weightlessness", "cosmonaut")
_WOMEN_ARXIV = ("women", "female", "gender", "sex")

_EPMC_SORT = {"relevance": "", "cited": "CITED desc", "newest": "P_PDATE_D desc"}
_ARXIV_SORT = {"relevance": "relevance", "cited": "relevance", "newest": "submittedDate"}


def _clean(text: str) -> str:
    """Europe PMC embeds entity-encoded markup (&lt;b&gt;…) in titles/abstracts.

    Unescape once, strip the resulting tags, and collapse whitespace so the UI shows
    plain text instead of literal <b> tags.
    """
    text = re.sub(r"<[^>]+>", "", html.unescape(text or ""))
    return " ".join(text.split())


def _get(url: str, timeout: int = 15, retries: int = 1) -> str:
    """GET with one retry — the providers occasionally 429 or drop the connection."""
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt < retries:
                time.sleep(2.5)
    raise last


# --------------------------------------------------------------------------- #
# Query builders (pure — no network)
# --------------------------------------------------------------------------- #
def _epmc_query(query: str, space_only: bool, women_lens: bool) -> str:
    q = f"({query})"
    if space_only:
        q += f" AND {_SPACE_EPMC}"
    if women_lens:
        q += f" AND {_WOMEN_EPMC}"
    return q


def _arxiv_query(query: str, space_only: bool, women_lens: bool) -> str:
    # AND the user's own words so a multi-word query isn't OR'd into noise by arXiv.
    words = [w for w in re.findall(r"[A-Za-z0-9']+", query) if len(w) > 2]
    parts = [" AND ".join(f"all:{w}" for w in words)] if words else ["all:*"]
    if space_only:
        parts.append("(" + " OR ".join(f"all:{t}" for t in _SPACE_ARXIV) + ")")
    if women_lens:
        parts.append("(" + " OR ".join(f"all:{t}" for t in _WOMEN_ARXIV) + ")")
    return " AND ".join(parts)


# --------------------------------------------------------------------------- #
# Europe PMC — https://europepmc.org/RestfulWebService
# --------------------------------------------------------------------------- #
def _parse_epmc(data: dict) -> list[dict]:
    out = []
    for r in (data.get("resultList") or {}).get("result", []):
        src, pid = r.get("source"), r.get("id")
        if not (src and pid):
            continue
        journal = ((r.get("journalInfo") or {}).get("journal") or {}).get("title")
        doi = r.get("doi") or ""
        out.append({
            "uid": f"epmc:{src}:{pid}",
            "title": _clean(r.get("title") or "Untitled").rstrip("."),
            "authors": r.get("authorString") or "",
            "year": str(r.get("pubYear") or ""),
            "venue": journal or "",
            "abstract": _clean(r.get("abstractText") or ""),
            "doi": doi,
            "url": f"https://doi.org/{doi}" if doi
                   else f"https://europepmc.org/article/{src}/{pid}",
            "source": "Europe PMC",
            "cited_by": int(r.get("citedByCount") or 0),
        })
    return out


def _europepmc(query, limit, space_only, women_lens, sort):
    q = urllib.parse.quote(_epmc_query(query, space_only, women_lens))
    url = ("https://www.ebi.ac.uk/europepmc/webservices/rest/search"
           f"?query={q}&format=json&resultType=core&pageSize={limit}")
    if _EPMC_SORT.get(sort):
        url += "&sort=" + urllib.parse.quote(_EPMC_SORT[sort])
    data = json.loads(_get(url))
    return _parse_epmc(data), int(data.get("hitCount") or 0)


# --------------------------------------------------------------------------- #
# arXiv — https://info.arxiv.org/help/api/
# --------------------------------------------------------------------------- #
def _parse_arxiv(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    out = []
    for e in root.findall("a:entry", _ATOM):
        abs_url = (e.findtext("a:id", "", _ATOM) or "").strip()
        if not abs_url:
            continue
        arxiv_id = abs_url.rsplit("/", 1)[-1]
        published = e.findtext("a:published", "", _ATOM) or ""
        authors = ", ".join(
            (a.findtext("a:name", "", _ATOM) or "").strip()
            for a in e.findall("a:author", _ATOM))
        out.append({
            "uid": f"arxiv:{arxiv_id}",
            "title": " ".join((e.findtext("a:title", "", _ATOM) or "").split()),
            "authors": authors,
            "year": published[:4],
            "venue": "arXiv preprint",
            "abstract": " ".join((e.findtext("a:summary", "", _ATOM) or "").split()),
            "doi": e.findtext(f"{_ARXIV_NS}doi", "") or "",
            "url": abs_url,
            "source": "arXiv",
            "cited_by": 0,
        })
    return out


def _arxiv(query, limit, space_only, women_lens, sort):
    q = urllib.parse.quote(_arxiv_query(query, space_only, women_lens))
    url = ("http://export.arxiv.org/api/query"
           f"?search_query={q}&start=0&max_results={limit}"
           f"&sortBy={_ARXIV_SORT.get(sort, 'relevance')}&sortOrder=descending")
    xml_text = _get(url, timeout=10)  # secondary source — fail fast, don't stall the UI
    total = int(ET.fromstring(xml_text).findtext(_OPENSEARCH_TOTAL) or 0)
    return _parse_arxiv(xml_text), total


_FETCHERS = {"Europe PMC": _europepmc, "arXiv": _arxiv}


def search(query: str, sources=SOURCES, limit: int = 25,
           space_only: bool = True, women_lens: bool = False, sort: str = "relevance"):
    """Search the given sources. Returns (results, errors, totals).

    `totals` maps each reached source to its full match count (how many papers exist,
    vs the `limit` we actually pull). A failure in one source lands in `errors` and
    never kills the others.
    """
    query = (query or "").strip()
    if not query:
        return [], {}, {}
    results, errors, totals = [], {}, {}
    for name in sources:
        try:
            rows, total = _FETCHERS[name](query, limit, space_only, women_lens, sort)
            results.extend(rows)
            totals[name] = total
        except Exception as exc:  # noqa: BLE001 — one source down != whole search down
            errors[name] = str(exc)
    if sort == "cited":
        results.sort(key=lambda p: p["cited_by"], reverse=True)
    elif sort == "newest":
        results.sort(key=lambda p: p["year"], reverse=True)
    # relevance: keep each source's own ranking, concatenated
    return results, errors, totals


if __name__ == "__main__":  # live smoke: `py sources.py "bone density loss"`
    import sys
    res, err, tot = search(sys.argv[1] if len(sys.argv) > 1 else "bone density loss",
                           limit=3)
    print(f"totals={tot} errors={err}")
    for p in res[:6]:
        print(f"  [{p['source']}] {p['year']}  {p['title'][:66]}  (cited {p['cited_by']})")
