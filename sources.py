"""Free scholarly search across several open databases. Standard library only.

Sources (all keyless):
  * Europe PMC       — published biomedical & clinical literature.
  * bioRxiv/medRxiv  — preprints, via Europe PMC's preprint index (SRC:PPR filtered
                       to those two servers). Catches new work before journal publication.
  * arXiv            — bioengineering / physics / space-science preprints.
  * OpenAlex         — ~240M works across all publishers, with citation data. Broadens
                       coverage of women's-health / disparities / bioengineering literature.
  * NASA OSDR        — NASA's Open Science Data Repository (GeneLab): spaceflight biology
                       *datasets* (omics, physiology), not papers. Already all space-bio,
                       so it ignores the space/women scoping toggles.

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
from datetime import datetime, timezone

_UA = "AdrasteaResearchLibrary/0.3 (Adrastea non-profit; research discovery)"
_ATOM = {"a": "http://www.w3.org/2005/Atom"}
_ARXIV_NS = "{http://arxiv.org/schemas/atom}"
_OPENSEARCH_TOTAL = "{http://a9.com/-/spec/opensearch/1.1/}totalResults"

SOURCES = ("Europe PMC", "bioRxiv/medRxiv", "arXiv", "OpenAlex", "NASA OSDR")
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
_OPENALEX_SORT = {"relevance": "relevance_score:desc", "cited": "cited_by_count:desc",
                  "newest": "publication_date:desc"}


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
# OpenAlex — https://docs.openalex.org/ (free, keyless)
# --------------------------------------------------------------------------- #
def _openalex_abstract(inv: dict | None) -> str:
    """OpenAlex ships abstracts as an inverted index {word: [positions]}; rebuild it."""
    if not inv:
        return ""
    positions = sorted((i, word) for word, idxs in inv.items() for i in idxs)
    return " ".join(word for _, word in positions)


def _parse_openalex(data: dict) -> list[dict]:
    out = []
    for w in data.get("results", []):
        oid = w.get("id") or ""
        if not oid:
            continue
        doi_full = w.get("doi") or ""
        loc = w.get("primary_location") or {}
        venue = (loc.get("source") or {}).get("display_name") or ""
        authors = ", ".join((a.get("author") or {}).get("display_name", "")
                            for a in (w.get("authorships") or []))
        out.append({
            "uid": f"openalex:{oid.rsplit('/', 1)[-1]}",
            "title": _clean(w.get("display_name") or "Untitled").rstrip("."),
            "authors": authors,
            "year": str(w.get("publication_year") or ""),
            "venue": venue,
            "abstract": _clean(_openalex_abstract(w.get("abstract_inverted_index"))),
            "doi": doi_full.replace("https://doi.org/", ""),
            "url": doi_full or loc.get("landing_page_url") or oid,
            "source": "OpenAlex",
            "cited_by": int(w.get("cited_by_count") or 0),
        })
    return out


def _openalex(query, limit, space_only, women_lens, sort, token=None):
    # Comma separates filters in OpenAlex, so keep it out of the search value.
    q = _epmc_query(query.replace(",", " "), space_only, women_lens)
    filt = urllib.parse.quote(f"title_and_abstract.search:{q}", safe=":")
    select = ("id,doi,display_name,publication_year,cited_by_count,authorships,"
              "primary_location,abstract_inverted_index")
    url = (f"https://api.openalex.org/works?filter={filt}"
           f"&per_page={limit}&select={select}")
    if _OPENALEX_SORT.get(sort):
        url += "&sort=" + urllib.parse.quote(_OPENALEX_SORT[sort], safe=":")
    data = json.loads(_get(url))
    return _parse_openalex(data), int((data.get("meta") or {}).get("count") or 0)


# --------------------------------------------------------------------------- #
# NASA OSDR / GeneLab — https://osdr.nasa.gov/ (space-biology datasets, keyless)
# --------------------------------------------------------------------------- #
def _parse_osdr(data: dict) -> list[dict]:
    out = []
    for hit in ((data.get("hits") or {}).get("hits") or []):
        s = hit.get("_source") or {}
        acc = s.get("Accession") or s.get("Study Identifier")
        if not acc:
            continue
        title = s.get("Study Title") or s.get("Study Publication Title") or acc
        # author list is double-space separated (e.g. "Braun JL  Hockey BL"); some
        # records mangle names with stray commas ("Charles,R,Farber") — tidy both.
        authors = ", ".join(
            " ".join(re.sub(r"[,]+", " ", a).split())
            for a in re.split(r"\s{2,}", (s.get("Study Publication Author List") or "").strip())
            if a.strip())
        organism = s.get("organism") or ""
        if isinstance(organism, list):  # OSDR returns organism as a string or a list
            organism = ", ".join(str(o) for o in organism)
        rd = s.get("Study Public Release Date")
        try:
            year = str(datetime.fromtimestamp(float(rd), timezone.utc).year) if rd else ""
        except (ValueError, TypeError, OSError):
            year = ""
        out.append({
            "uid": f"osdr:{acc}",
            "title": _clean(title).rstrip("."),
            "authors": authors,
            "year": year,
            "venue": f"NASA OSDR dataset · {organism}" if organism else "NASA OSDR dataset",
            "abstract": _clean(s.get("Study Description")
                               or s.get("Study Protocol Description") or ""),
            "doi": "",
            "url": f"https://osdr.nasa.gov/bio/repo/data/studies/{acc}",
            "source": "NASA OSDR",
            "cited_by": 0,
        })
    return out


def _osdr(query, limit, space_only, women_lens, sort):
    # OSDR is entirely space-biology data — the scope toggles don't apply; the user's
    # term does the topical filtering. Datasets have no citation count or DOI.
    url = ("https://osdr.nasa.gov/osdr/data/search"
           f"?term={urllib.parse.quote(query)}&size={limit}")
    data = json.loads(_get(url))
    total = (data.get("hits") or {}).get("total") or 0
    if isinstance(total, dict):  # newer Elasticsearch wraps it as {"value": N}
        total = total.get("value") or 0
    return _parse_osdr(data), int(total)


_FETCHERS = {"Europe PMC": _europepmc, "bioRxiv/medRxiv": _preprints,
             "arXiv": _arxiv, "OpenAlex": _openalex, "NASA OSDR": _osdr}


def search(query: str, sources=SOURCES, limit: int = 25, space_only: bool = True,
           women_lens: bool = False, sort: str = "relevance"):
    """Search the given sources. Returns (results, errors, totals).

    `totals` maps each reached source to its full match count. A failure in one source
    lands in `errors` and never kills the others. Results are de-duplicated across sources
    by DOI (falling back to uid) — the same paper can appear in Europe PMC and OpenAlex
    under different ids.
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

    seen_doi, seen_uid, deduped = set(), set(), []
    for p in results:
        doi = (p.get("doi") or "").lower().strip()
        if doi and doi in seen_doi:
            continue
        if p["uid"] in seen_uid:
            continue
        if doi:
            seen_doi.add(doi)
        seen_uid.add(p["uid"])
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
