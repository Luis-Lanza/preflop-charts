# Preflop charts PDF

Printable PDF of the PlusEV preflop chart library (6-max cash, 100bb) for study and table-side reference.

## Specs

S1. User request, verbatim: "me gustaria armar un PDF con todas estas charts para poder imprimirlas y comenzar a estudiar el poker."

S2. Layout: "6 charts por hoja A4" — A4 portrait, 2 columns x 3 rows, ~20 pages for the full set.

S3. Mixed frequencies: "Solo color partido" — split cell colours only, no percentage text inside the cell.

S4. Coverage: "Los 117 charts" — all 8 families: RFI 5, facing-a-raise 15, vs-3-bet 15, vs-4-bet 15, vs-4-bet-all-in 12, vs-5-bet-all-in 15, cold-4-bet 20, squeezing 20.

S5. Source: https://plusev.poker/charts/ — every chart is "6-max cash at 100 big blinds". Colours are the site's own: Fold #255BAB, Call #25AB32, Raise #AB2525.

## Tasks

| ID | Spec | Route | Status |
| --- | --- | --- | --- |
| T1 | S1 S4 S5 | inline: scraper + normalised JSON + data test | done — 114 charts, 8/8 tests green |
| T2 | S2 | inline: print HTML, chromium --print-to-pdf | done — A4, 6/page, 24 pages |
| T3 | S3 | inline: gradient segments from source, no % in cell | done — split cells only, per-chart legend |
| T4 | S1 S2 | inline: page count + extracted-text verification | done — verify_pdf.py: 24 pages, 114/114 charts |

## Log

L1. User: "me gustaria armar un PDF con todas estas charts para poder imprimirlas y comenzar a estudiar el poker."
L2. Decisions: 6 charts/page A4, split-colour only, all 117 charts.
L3. Source pages are Astro static HTML: each cell carries `data-tip` with exact action fractions and the style carries either a flat colour or a `linear-gradient` split, so the data is parsed exactly, not eyeballed. 8 pages total.

L4. Site discrepancy: the charts index lists 12 spots for "vs 4-bet all-in" but the page publishes 9 figures; total published is 114, not 117. The PDF follows the published pages and the index row is reported to the user.
L5. Two source states beyond fold/call/raise: hands the previous player never holds are drawn `#1F1E1E` and labelled "Not in range" in `data-tip`. Parsed as `out_of_range` cells with no actions, rendered dark with their own legend key.
L6. Layout evidence: cells 7.45 x 6.1 mm, grid 96 mm wide, ink ends at 279.6 mm on a full page (A4 = 297 mm), page count and per-page chart titles verified by `scripts/verify_pdf.py`.
