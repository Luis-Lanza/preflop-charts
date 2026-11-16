# Astro preflop chart web app

Interactive replacement for the printed PDF: pick your position and the action in front of
you, see the chart instantly, with exact mixed frequencies on hover.

## Specs

S1. User request, verbatim: "puedes hacer una web, que se vea una tabla preflop. y que se haya botones para seleccionar mi posocion la del rival y que sea algo interactivo envez de imprimir las tablas? Algo rapido de usar? ... ahora quiero implementar eso que te digo con astro"

S2. Stack: Astro, static output, no UI framework dependency — one vanilla client script so the page stays fast.

S3. Interaction: two selectors. First "your position" (UTG/HJ/CO/BTN/SB/BB), then the spot available from that seat, worded as the action in front of you ("vs UTG open", "vs HJ 3-bet", "everyone folded"). Selecting both resolves to exactly one of the 114 charts.

S4. Chart rendering: same 13x13 grid and colours as the PDF and the source site; a cell split between colours is a mixed frequency, with no percentages printed in the cell.

S5. Interactive gain over print: hovering or tapping a cell shows that hand's exact fractions ("Fold 36% · Raise 16 64%"), plus a breadcrumb of the action sequence with stack sizes, the published stat line, the per-chart legend, and a copy-range button that emits the range as text grouped by action.

S6. Fast to use: no page reloads, no build step at runtime, URL hash mirrors the selection so a spot can be reloaded or shared, and the layout works on a phone (single column, tappable cells).

S7. Data source: `data/charts.json` (produced by `scripts/scrape.py` from plusev.poker/charts, 6-max cash 100bb, 114 charts). No data is retyped by hand.

## Tasks

| ID | Spec | Route | Status |
| --- | --- | --- | --- |
| T1 | S7 | inline: `scripts/build_web_data.py` -> compact web payload + python test | done — 114 spots, 1234 shared patterns, 202 KB |
| T2 | S1 S2 | inline: minimal Astro project under `web/` | done — astro 7.4.12, static, no UI framework |
| T3 | S3 S4 | inline: selectors, resolver wiring, grid render | done — seat + spot buttons, precomputed resolution |
| T4 | S5 S6 | inline: hover/tap fractions, breadcrumb, copy, hash state | done — plus 1-6 / [/] keys |
| T5 | S1 S6 | inline: build, payload test, headless screenshot check | done — 23 tests, dist is one 216 KB file |

## Log

L1. User: "puedes hacer una web, que se vea una tabla preflop. y que se haya botones para seleccionar mi posocion la del rival y que sea algo interactivo envez de imprimir las tablas? Algo rapido de usar? cachas? esto que hicimos esta bien pero ahora quiero implementar eso que te digo con astro"
L2. Decision: the PDF stays as the printable artifact; the web app is a second consumer of the same `data/charts.json`.
L3. Decision: chart resolution is precomputed in Python (hero seat + spot -> chart id) so the client only indexes data; the client never derives poker semantics.
L4. Constraint found in the data: three source states beyond fold/call/raise (`out_of_range`, all-in, jam sizes) and spot strings such as "vs UTG open, HJ 3-bet" that carry the history; labels are generated from caption + spot, not hand-written per chart.

L5. Resolution design: the payload groups spots by acting seat, so the client only indexes data. Chart id -> hero + spot + generated history with sizes looked up in the same dataset (open sizes from RFI, 3-bet sizes from facing-a-raise, 4-bet sizes from facing-a-3-bet).
L6. Cells are shipped as base-36 codes into a deduplicated table of colour splits (1234 patterns for 19,266 cells); hand order and combo weights travel with the payload so the client holds no poker semantics.
L7. Build detail: `app.js` is imported with Vite's `?raw` and inlined via `<script is:inline set:html>`, so `web/dist/index.html` runs from `file://` with no assets. Verified by loading the built file over `file://` in headless chromium (desktop 1280px, mobile 390px) and by DOM assertions: 169 cells, chips per seat, gradients present, `data-ready="true"`.
