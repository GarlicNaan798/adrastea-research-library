# Adrastea Research Library

A small, free desktop tool for finding and collecting research papers on the science of
**women's health, bioengineering, and equity in spaceflight** — the questions at the
heart of [Adrastea](https://github.com/GarlicNaan798)'s mission to bridge the gender gap
in space.

Search open scholarly databases, save what matters into a local collection, and export
it to CSV or BibTeX. No account, no tracking, no API keys.

![Adrastea](brand/adrastea-mark.svg)

## What it does

- **Search several open databases at once**
  - **Europe PMC** — biomedical & clinical literature (women's health, physiology, medicine)
  - **bioRxiv / medRxiv** — preprints, catching brand-new work before journal publication
  - **arXiv** — bioengineering, physics, and space-science preprints
  - **NASA ADS** *(optional, free key)* — the astrophysics & space-science index
- **Mission-aligned starting points** — one-click searches like *sex differences in
  microgravity*, *bone density loss in female astronauts*, *reproductive health & space
  radiation*, *gender disparities in space science*.
- **A collection worth keeping** — save papers to a local file, add your own notes, and
  export the whole thing to **CSV** or **BibTeX** for a reference manager or grant.
- **Resilient** — if one database is unreachable, the other still returns results.

Results are ranked by citation count. Saved papers live in `collection.db`, a single
SQLite file on your machine — nothing leaves your computer except the searches themselves.

## Run it

You need [Python 3.10+](https://www.python.org/downloads/).

```bash
git clone https://github.com/GarlicNaan798/adrastea-research-library.git
cd adrastea-research-library
pip install -r requirements.txt
py -m streamlit run app.py
```

It opens in your browser at `http://localhost:8501`. (On macOS/Linux use `python3`
instead of `py`.)

### Optional: enable NASA ADS

NASA ADS indexes astrophysics & space-science literature. To add it as a source:

1. Sign in (free) at [ui.adsabs.harvard.edu](https://ui.adsabs.harvard.edu/) →
   **Account → Settings → API Token → Generate a new key**.
2. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and paste your
   token into `ADS_API_TOKEN` (or set an `ADS_API_TOKEN` environment variable).

`secrets.toml` is git-ignored, so your token is never committed. Without a token, the
app simply doesn't show NASA ADS as a source — everything else works.

## Project layout

| File | Purpose |
|------|---------|
| `app.py` | Streamlit UI — search, results, collection |
| `sources.py` | Europe PMC + arXiv clients (standard library only) |
| `db.py` | Local SQLite collection |
| `export.py` | CSV / BibTeX exporters |
| `brand.py` | Adrastea styling |
| `tests/test_all.py` | Offline checks — `py tests/test_all.py` |

## Roadmap

- "Load more" pagination to page through all matches (currently up to 50 per source).
- Tag and filter your saved collection.
- Year-range and open-access filters.

## License

MIT — see [LICENSE](LICENSE). Built for the Adrastea Research Foundation.
