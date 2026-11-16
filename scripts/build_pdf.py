#!/usr/bin/env python3
"""Render data/charts.json into a print-ready A4 PDF via headless Chromium.

Layout: 6 charts per A4 page (2 columns x 3 rows), one family per page run.
Split cells keep their source colour split and carry no percentage text.

Usage:
    python3 scripts/build_pdf.py              # build the PDF
    python3 scripts/build_pdf.py --html-only  # stop after the HTML
"""

from __future__ import annotations

import argparse
import html
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "charts.json"
BUILD = ROOT / "build"
HTML_OUT = BUILD / "preflop-charts.html"
PDF_OUT = BUILD / "plusev-preflop-charts-6max-100bb.pdf"

PER_PAGE = 6
OUT_OF_RANGE = "#1F1E1E"
FORMAT_HEADER = "6-max cash · 100 big blinds"

CSS = """
@page { size: A4 portrait; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif;
  color: #14181f;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
.page {
  width: 210mm; height: 297mm; padding: 7mm 7mm 5mm;
  display: flex; flex-direction: column;
  page-break-after: always; break-after: page; overflow: hidden;
}
.page:last-child { page-break-after: auto; break-after: auto; }
.page-head {
  display: flex; justify-content: space-between; align-items: baseline;
  font-size: 7.5pt; letter-spacing: .04em; text-transform: uppercase;
  color: #6b7280; border-bottom: .3mm solid #d8dde5;
  padding-bottom: 1.5mm; margin-bottom: 3mm; flex: none;
}
.page-head b { color: #14181f; font-size: 8.5pt; letter-spacing: .06em; }
.grid-area {
  flex: 1; display: grid; grid-template-columns: 1fr 1fr;
  grid-auto-rows: max-content; gap: 3mm 4mm; align-content: start;
}
.chart { break-inside: avoid; }
.chart-title { font-size: 7.2pt; font-weight: 700; margin: 0 0 .8mm; }
.chart-title span { font-weight: 500; color: #6b7280; }
table.range { border-collapse: collapse; width: 100%; table-layout: fixed; }
table.range td {
  height: 6.1mm; border: .18mm solid #fff; text-align: center;
  font-size: 5.3pt; font-weight: 600; color: #fff; line-height: 1;
  padding: 0; overflow: hidden;
}
table.range td.dark { color: #c9ccd2; font-weight: 500; }
.chart-foot {
  display: flex; justify-content: space-between; align-items: center;
  gap: 2mm; margin-top: .8mm; font-size: 4.6pt; color: #4b5563;
}
.keys { display: flex; flex-wrap: wrap; gap: 1.4mm; }
.key { display: flex; align-items: center; gap: .7mm; white-space: nowrap; }
.key i { width: 2.2mm; height: 2.2mm; border-radius: .4mm; display: inline-block; }
.stat { text-align: right; line-height: 1.15; }
.cover > div:last-of-type { margin-top: auto; }
.cover h1 { font-size: 26pt; margin: 0 0 1mm; letter-spacing: -.02em; }
.cover .lede { font-size: 10pt; color: #4b5563; margin: 0 0 5mm; }
.cover .meta { font-size: 8pt; color: #6b7280; }
.toc { width: 100%; border-collapse: collapse; font-size: 8pt; margin: 0 0 6mm; }
.toc th, .toc td { text-align: left; padding: 1.4mm 2mm; border-bottom: .2mm solid #e5e7eb; }
.toc th { font-size: 7pt; text-transform: uppercase; letter-spacing: .06em; color: #6b7280; }
.toc td.n { text-align: right; }
.howto { display: grid; grid-template-columns: 1fr 1fr; gap: 4mm 6mm; font-size: 7.6pt; }
.howto h3 { font-size: 8pt; margin: 0 0 1mm; }
.howto p { margin: 0 0 1.6mm; color: #374151; line-height: 1.35; }
.swatches { display: flex; gap: 3mm; flex-wrap: wrap; font-size: 7.4pt; margin: 0 0 2mm; }
.swatches span { display: flex; align-items: center; gap: 1.2mm; }
.swatches i { width: 3.4mm; height: 3.4mm; display: inline-block; border-radius: .5mm; }
.split { background: linear-gradient(to right, #25AB32 0% 55%, #AB2525 55% 100%); }
.note { font-size: 7pt; color: #6b7280; }
"""


def gradient(segments: list[dict]) -> str:
    stops = ", ".join(
        f"{s['color']} {s['from']:.1f}% {s['to']:.1f}%" for s in segments
    )
    if len(segments) == 1:
        return f"background:{segments[0]['color']}"
    return f"background:linear-gradient(to right, {stops})"


ORDER = ("Fold", "Call", "All-in", "Not in range", "Raise")


def legend_rank(label: str) -> tuple[int, str]:
    for index, prefix in enumerate(ORDER):
        if label.startswith(prefix):
            return index, label
    return len(ORDER), label


def chart_legend(chart: dict) -> list[dict]:
    """Legend entries the cells use, always in the same reading order."""
    used = {s["color"] for cell in chart["cells"] for s in cell["segments"]}
    keys = [k for k in chart["legend"] if k["color"] in used]
    if any(cell["out_of_range"] for cell in chart["cells"]):
        keys.append({"color": OUT_OF_RANGE, "label": "Not in range"})
    return sorted(keys, key=lambda k: legend_rank(k["label"]))


def stat_line(chart: dict) -> str:
    if chart.get("open_to"):
        parts = [f"<b>{chart['chosen_pct']}%</b> of hands"]
        if chart.get("chosen_combos"):
            parts.append(f"{chart['chosen_combos']} combos")
        parts.append(f"open {chart['open_to']:g}bb")
        return " · ".join(parts)
    stat = chart.get("stat", "").rstrip(".")
    return html.escape(stat).replace(" of hands,", " of hands<wbr>,")


def chart_html(chart: dict) -> str:
    rows = []
    for start in range(0, 169, 13):
        cells = []
        for cell in chart["cells"][start : start + 13]:
            style = gradient(cell["segments"])
            cls = ' class="dark"' if cell["out_of_range"] else ""
            cells.append(f'<td{cls} style="{style}">{cell["hand"]}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    keys = "".join(
        f'<span class="key"><i style="background:{k["color"]}"></i>{html.escape(k["label"])}</span>'
        for k in chart_legend(chart)
    )
    return f"""<div class="chart">
  <p class="chart-title">{html.escape(chart['title'])}</p>
  <table class="range">{''.join(rows)}</table>
  <div class="chart-foot">
    <div class="keys">{keys}</div>
    <div class="stat">{stat_line(chart)}</div>
  </div>
</div>"""


def cover_html(data: dict, plan: list[tuple[dict, int, int]]) -> str:
    total_pages = 1 + sum(count for _, _, count in plan)
    rows = "".join(
        f"<tr><td>{html.escape(f['title'])}</td><td class='n'>{len(f['charts'])}</td>"
        f"<td class='n'>{first if count == 1 else str(first) + '-' + str(first + count - 1)}</td></tr>"
        for f, first, count in plan
    )
    return f"""<section class="page cover">
  <div>
    <h1>Preflop charts</h1>
    <p class="lede">6-max cash · 100 big blinds · {sum(len(f['charts']) for f, _, _ in plan)} charts</p>
    <table class="toc">
      <tr><th>Family</th><th class="n">Charts</th><th class="n">Pages</th></tr>
      {rows}
      <tr><td><b>Total</b></td><td class="n"><b>{sum(len(f['charts']) for f, _, _ in plan)}</b></td>
      <td class="n"><b>2-{total_pages}</b></td></tr>
    </table>
  </div>
  <div>
    <div class="swatches">
      <span><i style="background:#255BAB"></i>Fold</span>
      <span><i style="background:#25AB32"></i>Call</span>
      <span><i style="background:#AB2525"></i>Raise / 3-bet / 4-bet</span>
      <span><i style="background:#91210E"></i>All-in</span>
      <span><i style="background:{OUT_OF_RANGE}"></i>Not in range (hand the previous player never holds)</span>
      <span><i class="split"></i>Split cell = mixed frequency</span>
    </div>
    <div class="howto">
      <div>
        <h3>How to read a grid</h3>
        <p>The diagonal is pocket pairs, everything above it is suited, everything below it is offsuit: AKs sits one cell right of AA, AKo one cell below it.</p>
        <p>A cell split between two colours is one hand played two ways. The action on the left covers the left-hand share of the cell, so a cell split down the middle is a 50/50 mix.</p>
      </div>
      <div>
        <h3>How to study with it</h3>
        <p>Learn one seat at a time. Keep the page for your seat open for a session and check yourself after each hand, not during it.</p>
        <p>Check the hands you folded: folds are where the silent leaks live, because nothing in the hand history tells you a fold was wrong.</p>
        <p class="note">Source: plusev.poker/charts — charts exported from the published data on {html.escape(data['source']['fetched'])}. Free for personal study. Format: {html.escape(data['source']['format'])}.</p>
      </div>
    </div>
  </div>
  <div class="meta">{total_pages} pages · print double-sided to save paper · A4, no scaling</div>
</section>"""


def family_pages(family: dict, first_page: int, total_pages: int) -> list[str]:
    charts = family["charts"]
    pages = []
    for index in range(0, len(charts), PER_PAGE):
        chunk = charts[index : index + PER_PAGE]
        page_no = first_page + index // PER_PAGE
        body = "".join(chart_html(c) for c in chunk)
        pages.append(
            f"""<section class="page">
  <div class="page-head">
    <b>{html.escape(family['title'])}</b>
    <span>{FORMAT_HEADER}</span>
    <span>page {page_no} / {total_pages}</span>
  </div>
  <div class="grid-area">{body}</div>
</section>"""
        )
    return pages


def build_html(data: dict) -> str:
    plan = []
    page_cursor = 2  # page 1 is the cover
    for family in data["families"]:
        count = max(1, -(-len(family["charts"]) // PER_PAGE))
        plan.append((family, page_cursor, count))
        page_cursor += count
    total_pages = page_cursor - 1

    pages = [cover_html(data, plan)]
    for family, first, _count in plan:
        pages.extend(family_pages(family, first, total_pages))

    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<title>Preflop charts — 6-max cash 100bb</title>"
        f"<style>{CSS}</style></head><body>{''.join(pages)}</body></html>"
    )


def render_pdf(html_path: pathlib.Path, pdf_path: pathlib.Path) -> None:
    chromium = shutil.which("chromium") or shutil.which("chromium-browser")
    if not chromium:
        raise SystemExit("chromium not found; the HTML is written, render it manually")
    subprocess.run(
        [
            chromium,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--no-pdf-header-footer",
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=10000",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ],
        check=True,
        capture_output=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html-only", action="store_true")
    args = parser.parse_args()

    if not DATA.exists():
        print("run scripts/scrape.py first", file=sys.stderr)
        return 1
    data = json.loads(DATA.read_text(encoding="utf-8"))
    BUILD.mkdir(parents=True, exist_ok=True)
    HTML_OUT.write_text(build_html(data), encoding="utf-8")
    print(f"html  -> {HTML_OUT.relative_to(ROOT)}", file=sys.stderr)
    if args.html_only:
        return 0
    render_pdf(HTML_OUT, PDF_OUT)
    print(f"pdf   -> {PDF_OUT.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
