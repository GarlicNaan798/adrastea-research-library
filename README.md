# Adrastea Research Library

A small, free web app for finding and collecting research papers on the science of
**women's health, bioengineering, and equity in spaceflight** — the questions at the
heart of [Adrastea](https://github.com/GarlicNaan798)'s mission to bridge the gender gap
in space.

Search five open scholarly databases at once, save what matters into a collection, and
export it to CSV or BibTeX. No account, no tracking, no API keys.

### 🔭 Use it now → **[adrastea-research.streamlit.app](https://adrastea-research.streamlit.app)**

No install — just open the link in any browser.

![Adrastea](brand/adrastea-mark.svg)

## What it does

- **Search five open databases at once** (no keys, no signup)
  - **Europe PMC** — biomedical & clinical literature (women's health, physiology, medicine)
  - **bioRxiv / medRxiv** — preprints, catching brand-new work before journal publication
  - **arXiv** — bioengineering, physics, and space-science preprints
  - **OpenAlex** — ~240M works across all publishers, with citation data
  - **NASA OSDR / GeneLab** — spaceflight-biology *datasets* (omics, physiology)
- **Precision toggles** — a default-on *space scope* keeps results on-mission, and an
  opt-in *women's-health lens* narrows to sex differences, reproductive and maternal health.
- **One-click topics** — pills like *bone density loss*, *reproductive health*,
  *radiation exposure*, *muscle atrophy*.
- **A collection worth keeping** — save papers, add notes, and export to **CSV** or
  **BibTeX** for a reference manager or grant. Re-import a CSV any time to reload it.
- **Resilient** — if one database is unreachable, the others still return results.

Your collection is private to your browser session — nothing is stored on a server.
Export it to keep it; import the CSV later to pick up where you left off.

## Use it

**As a website (easiest):** open **[adrastea-research.streamlit.app](https://adrastea-research.streamlit.app)** —
anyone can use it in their browser, no install. (To run your own copy, see *Deploy* below.)

**Run it locally:** you need [Python 3.10+](https://www.python.org/downloads/).

```bash
git clone https://github.com/GarlicNaan798/adrastea-research-library.git
cd adrastea-research-library
pip install -r requirements.txt
py -m streamlit run app.py
```

It opens at `http://localhost:8501`. (On macOS/Linux use `python3` instead of `py`.)

## Deploy your own (free, ~2 minutes)

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. **Create app → Deploy a public app from GitHub.**
3. Repository: `GarlicNaan798/adrastea-research-library`, branch `main`, main file `app.py`.
4. Click **Deploy**. Streamlit installs `requirements.txt` and gives you a public URL to share.

No secrets or configuration needed — every source is keyless.

## Project layout

| File | Purpose |
|------|---------|
| `app.py` | Streamlit UI — search, results, collection |
| `sources.py` | The five source clients + query scoping (standard library only) |
| `db.py` | In-session collection store |
| `export.py` | CSV / BibTeX export and CSV import |
| `brand.py` | Adrastea styling and source badges |
| `tests/test_all.py` | Offline checks — `py tests/test_all.py` |

## Roadmap

- Deeper recall + "showing 50 of N" so nothing relevant is silently cut off.
- A unified cross-source relevance ranking (today "relevance" keeps each source's order).
- Tag and filter your saved collection.

## License

MIT — see [LICENSE](LICENSE). Built for the Adrastea Research Foundation.
