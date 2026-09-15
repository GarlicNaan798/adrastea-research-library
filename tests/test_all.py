"""Offline checks for the parsing, storage, and export logic.

Run:  py -m pytest        (if pytest is installed)
or:   py tests/test_all.py (plain asserts, no framework needed)

The parser samples are trimmed from real Europe PMC / arXiv responses, so these
tests fail loudly if either provider changes shape in a way we don't handle.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
import export
import sources

EPMC_SAMPLE = {"resultList": {"result": [
    {"id": "42729855", "source": "MED", "title": "Sex differences in bone loss.",
     "authorString": "Doe J, Smith A.", "pubYear": "2026",
     "journalInfo": {"journal": {"title": "Frontiers in network physiology"}},
     "abstractText": "An abstract about microgravity.",
     "doi": "10.3389/fnetp.2026.1931834", "citedByCount": 5},
    {"id": "noid_missing_source"},  # malformed -> must be skipped, not crash
]}}

ARXIV_SAMPLE = """<feed xmlns="http://www.w3.org/2005/Atom"
 xmlns:arxiv="http://arxiv.org/schemas/atom">
 <entry>
  <id>http://arxiv.org/abs/1304.7183v1</id>
  <published>2013-04-24T10:13:04Z</published>
  <title>Sessile drops
   in microgravity</title>
  <summary>Interfaces with a liquid govern several phenomena.</summary>
  <author><name>Amelia Carolina Sparavigna</name></author>
  <arxiv:doi>10.1000/xyz</arxiv:doi>
  <link title="pdf" href="https://arxiv.org/pdf/1304.7183v1"/>
 </entry>
</feed>"""


def test_parse_epmc():
    rows = sources._parse_epmc(EPMC_SAMPLE)
    assert len(rows) == 1, "malformed entry (no source) must be skipped"
    p = rows[0]
    assert p["uid"] == "epmc:MED:42729855"
    assert p["url"] == "https://doi.org/10.3389/fnetp.2026.1931834"
    assert p["venue"] == "Frontiers in network physiology"
    assert p["cited_by"] == 5
    assert p["title"].endswith("loss")  # trailing period stripped


def test_parse_arxiv():
    rows = sources._parse_arxiv(ARXIV_SAMPLE)
    assert len(rows) == 1
    p = rows[0]
    assert p["uid"] == "arxiv:1304.7183v1"
    assert p["year"] == "2013"
    assert p["title"] == "Sessile drops in microgravity"  # whitespace collapsed
    assert p["authors"] == "Amelia Carolina Sparavigna"
    assert p["doi"] == "10.1000/xyz"


def test_db_roundtrip():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)  # empty file is a valid (empty) sqlite db
    try:
        paper = sources._parse_epmc(EPMC_SAMPLE)[0]
        assert db.save(paper, path) is True
        assert db.save(paper, path) is False, "dedup: same uid must not double-insert"
        assert db.saved_uids(path) == {paper["uid"]}
        db.set_note(paper["uid"], "cite in grant", path)
        assert db.list_saved(path)[0]["note"] == "cite in grant"
        db.remove(paper["uid"], path)
        assert db.list_saved(path) == []
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_preprint_label():
    # A Europe PMC preprint (SRC:PPR) should be badged by its server, not "Europe PMC"
    # real Europe PMC records nest the preprint server under bookOrReportDetails
    ppr = {"resultList": {"result": [{
        "id": "PPR813641", "source": "PPR",
        "bookOrReportDetails": {"publisher": "bioRxiv"},
        "title": "Osteoblast mechanotransduction in microgravity.",
        "authorString": "Roe J.", "pubYear": "2024", "doi": "10.1101/2024.01.01.123",
    }]}}
    p = sources._parse_epmc(ppr)[0]
    assert p["source"] == "bioRxiv"
    assert p["uid"] == "epmc:PPR:PPR813641"
    assert p["venue"] == "bioRxiv"  # falls back to server name when no journal


ADS_SAMPLE = {"response": {"numFound": 4321, "docs": [
    {"bibcode": "2024npjMG..10...5S", "title": ["Bone loss in <b>microgravity</b>"],
     "author": ["Smith, A.", "Doe, J."], "year": "2024", "pub": "npj Microgravity",
     "doi": ["10.1038/s41526-024-00001"], "abstract": "We study bone.",
     "citation_count": 12},
    {"title": ["no bibcode -> skipped"]},
]}}


def test_parse_ads():
    rows = sources._parse_ads(ADS_SAMPLE)
    assert len(rows) == 1, "doc without a bibcode must be skipped"
    p = rows[0]
    assert p["uid"] == "ads:2024npjMG..10...5S"
    assert p["source"] == "NASA ADS"
    assert p["title"] == "Bone loss in microgravity"  # markup stripped
    assert p["authors"] == "Smith, A., Doe, J."
    assert p["cited_by"] == 12
    assert p["url"].startswith("https://ui.adsabs.harvard.edu/abs/")


def test_clean_markup():
    # Europe PMC entity-encoded markup must not reach the UI as literal tags
    assert sources._clean("&lt;b&gt;Simulated&lt;/b&gt; microgravity") == "Simulated microgravity"
    assert sources._clean("<i>in vitro</i> bone   loss") == "in vitro bone loss"


def test_query_builders():
    # space scope is opt-out; women lens is opt-in
    assert "microgravity" in sources._epmc_query("bone loss", True, False)
    assert "microgravity" not in sources._epmc_query("bone loss", False, False)
    q = sources._epmc_query("bone loss", True, True)
    assert "microgravity" in q and "reproductive" in q

    # arXiv ANDs the user's own words (precision), then AND-groups the scope
    aq = sources._arxiv_query("bone density loss", True, False)
    assert "all:bone AND all:density AND all:loss" in aq
    assert "all:microgravity" in aq
    # short words (<=2 chars) are dropped so they don't blow up the query
    assert sources._arxiv_query("of a", False, False) == "all:*"


def test_export():
    a = sources._parse_epmc(EPMC_SAMPLE)[0]
    b = sources._parse_arxiv(ARXIV_SAMPLE)[0]
    csv_out = export.to_csv([a, b])
    assert csv_out.splitlines()[0].startswith("title,authors,year")
    assert "Sessile drops in microgravity" in csv_out

    bib = export.to_bibtex([a, b])
    assert bib.count("@article{") == 2
    # two entries -> two distinct cite keys
    keys = [ln.split("{", 1)[1].rstrip(",\n") for ln in bib.splitlines()
            if ln.startswith("@article{")]
    assert len(set(keys)) == 2


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} checks passed.")
