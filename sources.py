"""Free scholarly search over Europe PMC (biomedical) and arXiv (engineering / physics).

No API keys, no third-party deps — just the standard library. Parsing is deliberately
split from fetching so the parsers stay unit-testable offline (see tests/test_sources.py).
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

_UA = "AdrasteaResearchLibrary/0.1 (Adrastea non-profit; research discovery)"
_ATOM = {"a": "http://www.w3.org/2005/Atom"}
_ARXIV_NS = "{http://arxiv.org/schemas/atom}"

SOURCES = ("Europe PMC", "arXiv")


def _get(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


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
            "title": (r.get("title") or "Untitled").strip().rstrip("."),
            "authors": r.get("authorString") or "",
            "year": str(r.get("pubYear") or ""),
            "venue": journal or "",
            "abstract": r.get("abstractText") or "",
            "doi": doi,
            "url": f"https://doi.org/{doi}" if doi
                   else f"https://europepmc.org/article/{src}/{pid}",
            "source": "Europe PMC",
            "cited_by": int(r.get("citedByCount") or 0),
        })
    return out


def _europepmc(query: str, limit: int) -> list[dict]:
    q = urllib.parse.quote(query)
    url = ("https://www.ebi.ac.uk/europepmc/webservices/rest/search"
           f"?query={q}&format=json&resultType=core&pageSize={limit}")
    return _parse_epmc(json.loads(_get(url)))


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


def _arxiv(query: str, limit: int) -> list[dict]:
    q = urllib.parse.quote(f"all:{query}")
    url = ("http://export.arxiv.org/api/query"
           f"?search_query={q}&start=0&max_results={limit}"
           "&sortBy=relevance&sortOrder=descending")
    return _parse_arxiv(_get(url))


_FETCHERS = {"Europe PMC": _europepmc, "arXiv": _arxiv}


def search(query: str, sources=SOURCES, limit: int = 25):
    """Search the given sources. Returns (results, errors).

    A failure in one source (e.g. a network blip) never kills the others — it lands
    in `errors` keyed by source name so the UI can surface it and still show the rest.
    """
    query = (query or "").strip()
    if not query:
        return [], {}
    results, errors = [], {}
    for name in sources:
        try:
            results.extend(_FETCHERS[name](query, limit))
        except Exception as exc:  # noqa: BLE001 — one source down != whole search down
            errors[name] = str(exc)
    # citation-count desc, undated last — a mild "importance" nudge across sources
    results.sort(key=lambda p: p["cited_by"], reverse=True)
    return results, errors


if __name__ == "__main__":  # live smoke check: `py sources.py "women health spaceflight"`
    import sys
    res, err = search(sys.argv[1] if len(sys.argv) > 1 else "women health spaceflight",
                      limit=3)
    print(f"{len(res)} results, errors={err}")
    for p in res[:5]:
        print(f"  [{p['source']}] {p['year']}  {p['title'][:70]}  (cited {p['cited_by']})")
