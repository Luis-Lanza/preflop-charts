# Preflop charts

Two consumers of the same data, from the [PlusEV preflop chart library](https://plusev.poker/charts/):
6-max cash, 100 big blinds, 114 spots across 8 families.

* **Live site** — https://luis-lanza.github.io/preflop-charts/
* **`web/`** — interactive Astro page: pick your seat, pick the spot, see the chart,
  hover a hand for its exact mix. Builds to one self-contained `index.html`.
* **`build/plusev-preflop-charts-6max-100bb.pdf`** — printable A4 PDF, 24 pages.

## Build

```bash
python3 scripts/scrape.py        # 8 source pages -> data/charts.json  (add --refresh to re-download)
python3 scripts/build_pdf.py     # data/charts.json -> build/*.html -> PDF via headless chromium
python3 scripts/verify_pdf.py    # page count + every chart present on its page

python3 scripts/build_web_data.py   # data/charts.json -> web/src/data/charts.json
cd web && pnpm install && pnpm dev  # http://localhost:4321
cd web && pnpm build                # -> web/dist/index.html (single file, opens from disk)
```

`python3 -m unittest discover -s tests -v` covers the scraped data, the web payload
and the built page.

Requires `chromium` on `PATH`; `--html-only` stops before rendering.

## Layout

* A4 portrait, 2 columns x 3 rows per page, one family per page run.
* Cells keep the source colours: fold `#255BAB`, call `#25AB32`, raise `#AB2525`,
  all-in `#91210E`, not-in-range `#1F1E1E`.
* A cell split between two colours is a mixed frequency; the left colour covers
  the left share of the cell. No percentages are printed inside cells.
* Each chart carries its own legend and the published stat (share of hands, sizing).

## Data

The datasets (`data/charts.json`, `web/src/data/charts.json`) are generated, not
committed: `scripts/scrape.py` then `scripts/build_web_data.py` rebuild them from
the live site. CI runs both before `pnpm build`, so the published page always comes
from the current source.

`data/charts.json` is parsed from the static HTML: every cell carries its exact
fractions in `data-tip` and its colour, or colour split, in `style`. Cards the
previous player never holds are marked `out_of_range` ("Not in range") instead of
being read as folds. Raw HTML is cached under `data/raw/` for offline rebuilds.

Source pages publish **114** charts; the site's own index page claims 117. The
`facing-a-4-bet-all-in` family has 9 charts on its page, not the 12 the index
lists. The PDF follows the published pages.

## Files

```
scripts/scrape.py         source HTML -> data/charts.json
scripts/build_pdf.py      data/charts.json -> build/preflop-charts.html -> PDF
scripts/verify_pdf.py     PDF vs data: pages, chart titles, A4
scripts/build_web_data.py data/charts.json -> web payload (hero + spot -> one chart)
web/                      Astro app: index.astro markup, scripts/app.js client
tests/                    data integrity, web payload, built page
odd/tasks/                feature specs and task logs
```

## Web app

* Seats and spots are buttons: 6 seats, then the spots available from that seat
  (every folded, vs an open, vs a 3-bet, vs a 4-bet, jams, squeezes, cold 4-bets).
* The breadcrumb spells the action history with the sizes taken from the data.
* Hover or tap a cell for its exact fractions; the copy button emits the range as text.
* Keys: `1`-`6` pick a seat, `[` and `]` cycle spots. The URL hash mirrors the
  selection (`#btn/facing-a-raise-btn-vs-co-open`), so a spot can be reloaded or shared.
* `web/src/scripts/app.js` is inlined at build time, so `web/dist/index.html` is a
  single file you can open with `file://` — no server needed.
