"""Free scholarly search across several open databases. Standard library only.

Sources:
  * Europe PMC       — published biomedical & clinical literature.
  * bioRxiv/medRxiv  — preprints, via Europe PMC's preprint index (SRC:PPR filtered
                       to those two servers). Catches new work before journal publication.
  * arXiv            — bioengineering / physics / space-science preprints.
  * NASA ADS         — astrophysics & space index (needs a free API token; only offered
                       when one is configured).

Two precision levers keep the research team out of hundreds of unrelated papers:
  * space_only  — AND a spaceflight/microgravity clause onto every query (default on).
                  Keeps ~0.3–13% of a bare biomedical term's hits, all on-mission.
  * women_lens  — AND a women's-health clause (women / sex differences / reproductive …).
                  Off by default: most historical spaceflight studies used male subjects,
                  and hiding them would hide the very disparity Adrastea studies.

Parsing and query-building are split from fetching so they stay unit-testable offline
(see tests/test_all.py).
"""
from __future__ import annotations

import html
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

_UA = "AdrasteaResearchLibrary/0.3 (Adrastea non-profit; research discovery)"
_ATOM = {"a": "http://www.w3.org/2005/Atom"}
_ARXIV_NS = "{http://arxiv.org/schemas/atom}"
_OPENSEARCH_TOTAL = "{http://a9.com/-/spec/opensearch/1.1/}totalResults"

# Keyless sources, always available. NASA ADS is appended by the app when a token exists.
SOURCES = ("Europe PMC", "bioRxiv/medRxiv", "arXiv")
SORTS = ("relevance", "cited", "newest")

# Domain-scoping clauses. Europe PMC and NASA ADS share boolean+phrase syntax; arXiv fields
# are per-term.
_SPACE_EPMC = ('(spaceflight OR "space flight" OR microgravity OR astronaut OR cosmonaut'
               ' OR "space medicine" OR weightlessness OR "outer space"'
               ' OR "International Space Station" OR "spaceflight environment")')
_WOMEN_EPMC = ('(women OR woman OR female OR "sex differences" OR "sex-based" OR gender'
               ' OR maternal OR reproductive OR menstrual OR pregnancy)')
_SPACE_ARXIV = ("spaceflight", "microgravity", "astronaut", "weightlessness", "cosmonaut")
_WOMEN_ARXIV = ("women", "female", "gender", "sex")
_PREPRINT_FILTER = '(SRC:PPR) AND (PUBLISHER:"bioRxiv" OR PUBLISHER:"medRxiv")'

_EPMC_SORT = {"relevance": "", "cited": "CITED desc", "newest": "P_PDATE_D desc"}
_ARXIV_SORT = {"relevance": "relevance", "cited": "relevance", "newest": "submittedDate"}
_ADS_SORT = {"relevance": "", "cited": "citation_count desc", "newest": "date desc"}


def _clean(text: str) -> str:
    """Strip entity-encoded / JATS markup (Europe PMC titles, Crossref abstracts) and
    collapse whitespace so the UI shows plain text instead of literal <b>/<jats:p> tags."""
    text = re.sub(r"<[^>]+>", "", html.unescape(text or ""))
    return " ".join(text.split())


def _get(url: str, timeout: int = 15, retries: int = 1, headers: dict | None = None) -> str:
    """GET with one retry — the providers occasionally 429, 503, or drop the connection."""
    last = None
    hdrs = {"User-Agent": _UA, **(headers or {})}
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=hdrs), timeout=timeout) as r:
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
# Europe PMC (+ bioRxiv/medRxiv preprints) — https://europepmc.org/RestfulWebService
# --------------------------------------------------------------------------- #
def _parse_epmc(data: dict) -> list[dict]:
    out = []
    for r in (data.get("resultList") or {}).get("result", []):
        src, pid = r.get("source"), r.get("id")
        if not (src and pid):
            continue
        journal = ((r.get("journalInfo") or {}).get("journal") or {}).get("title")
        doi = r.get("doi") or ""
        # Preprints (SRC:PPR) carry the server name (bioRxiv/medRxiv) in the publisher
        # field — which lives under bookOrReportDetails, not top-level. Badge with it.
        publisher = (r.get("publisher")
                     or (r.get("bookOrReportDetails") or {}).get("publisher"))
        label = (publisher or "Preprint") if src == "PPR" else "Europe PMC"
        out.append({
            "uid": f"epmc:{src}:{pid}",
            "title": _clean(r.get("title") or "Untitled").rstrip("."),
            "authors": r.get("authorString") or "",
            "year": str(r.get("pubYear") or ""),
            "venue": journal or (label if src == "PPR" else ""),
            "abstract": _clean(r.get("abstractText") or ""),
            "doi": doi,
            "url": f"https://doi.org/{doi}" if doi
                   else f"https://europepmc.org/article/{src}/{pid}",
            "source": label,
            "cited_by": int(r.get("citedByCount") or 0),
        })
    return out


def _epmc_fetch(qstr: str, limit: int, sort: str):
    url = ("https://www.ebi.ac.uk/europepmc/webservices/rest/search"
           f"?query={urllib.parse.quote(qstr)}&format=json&resultType=core&pageSize={limit}")
    if _EPMC_SORT.get(sort):
        url += "&sort=" + urllib.parse.quote(_EPMC_SORT[sort])
    data = json.loads(_get(url))
    return _parse_epmc(data), int(data.get("hitCount") or 0)


def _europepmc(query, limit, space_only, women_lens, sort, token=None):
    return _epmc_fetch(_epmc_query(query, space_only, women_lens), limit, sort)


def _preprints(query, limit, space_only, women_lens, sort, token=None):
    q = f"{_epmc_query(query, space_only, women_lens)} AND {_PREPRINT_FILTER}"
    return _epmc_fetch(q, limit, sort)


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


def _arxiv(query, limit, space_only, women_lens, sort, token=None):
    q = urllib.parse.quote(_arxiv_query(query, space_only, women_lens))
    url = ("http://export.arxiv.org/api/query"
           f"?search_query={q}&start=0&max_results={limit}"
           f"&sortBy={_ARXIV_SORT.get(sort, 'relevance')}&sortOrder=descending")
    xml_text = _get(url, timeout=10)  # secondary source — fail fast, don't stall the UI
    total = int(ET.fromstring(xml_text).findtext(_OPENSEARCH_TOTAL) or 0)
    return _parse_arxiv(xml_text), total


# --------------------------------------------------------------------------- #
# NASA ADS — https://ui.adsabs.harvard.edu/help/api/ (needs a free bearer token)
# --------------------------------------------------------------------------- #
def _parse_ads(data: dict) -> list[dict]:
    out = []
    for d in (data.get("response") or {}).get("docs", []):
        bib = d.get("bibcode")
        if not bib:
            continue
        doi = (d.get("doi") or [""])[0]
        out.append({
            "uid": f"ads:{bib}",
            "title": _clean(" ".join(d.get("title") or ["Untitled"])).rstrip("."),
            "authors": ", ".join(d.get("author") or []),
            "year": str(d.get("year") or ""),
            "venue": d.get("pub") or "",
            "abstract": _clean(d.get("abstract") or ""),
            "doi": doi,
            "url": f"https://ui.adsabs.harvard.edu/abs/{urllib.parse.quote(bib)}",
            "source": "NASA ADS",
            "cited_by": int(d.get("citation_count") or 0),
        })
    return out


def _ads(query, limit, space_only, women_lens, sort, token=None):
    if not token:
        raise RuntimeError("NASA ADS token not configured")
    q = _epmc_query(query, space_only, women_lens)  # same boolean+phrase syntax as EPMC
    fl = "bibcode,title,author,year,pub,doi,abstract,citation_count"
    url = ("https://api.adsabs.harvard.edu/v1/search/query"
           f"?q={urllib.parse.quote(q)}&rows={limit}&fl={fl}")
    if _ADS_SORT.get(sort):
        url += "&sort=" + urllib.parse.quote(_ADS_SORT[sort])
    data = json.loads(_get(url, headers={"Authorization": f"Bearer {token}"}))
    return _parse_ads(data), int((data.get("response") or {}).get("numFound") or 0)


_FETCHERS = {"Europe PMC": _europepmc, "bioRxiv/medRxiv": _preprints,
             "arXiv": _arxiv, "NASA ADS": _ads}


def search(query: str, sources=SOURCES, limit: int = 25, space_only: bool = True,
           women_lens: bool = False, sort: str = "relevance", ads_token: str | None = None):
    """Search the given sources. Returns (results, errors, totals).

    `totals` maps each reached source to its full match count. A failure in one source
    lands in `errors` and never kills the others. Results are de-duplicated by uid across
    sources (the same paper can appear in both Europe PMC and the preprint index).
    """
    query = (query or "").strip()
    if not query:
        return [], {}, {}
    results, errors, totals = [], {}, {}
    for name in sources:
        try:
            rows, total = _FETCHERS[name](query, limit, space_only, women_lens,
                                          sort, ads_token)
            results.extend(rows)
            totals[name] = total
        except Exception as exc:  # noqa: BLE001 — one source down != whole search down
            errors[name] = str(exc)

    seen, deduped = set(), []
    for p in results:
        if p["uid"] not in seen:
            seen.add(p["uid"])
            deduped.append(p)
    results = deduped

    if sort == "cited":
        results.sort(key=lambda p: p["cited_by"], reverse=True)
    elif sort == "newest":
        results.sort(key=lambda p: p["year"], reverse=True)
    return results, errors, totals


if __name__ == "__main__":  # live smoke: `py sources.py "bone density loss"`
    import sys
    res, err, tot = search(sys.argv[1] if len(sys.argv) > 1 else "bone density loss",
                           limit=3)
    print(f"totals={tot} errors={err}")
    for p in res[:8]:
        print(f"  [{p['source']}] {p['year']}  {p['title'][:60]}  (cited {p['cited_by']})")
