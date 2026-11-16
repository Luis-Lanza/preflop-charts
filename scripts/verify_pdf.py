#!/usr/bin/env python3
"""Verify the built PDF against data/charts.json (specs S1, S2).

Checks:
  * page count matches the planned pagination (6 charts per page, one family per run)
  * every chart title is rendered on the page the plan assigns it to
  * the page is A4 and the cover states the real chart total

Usage: python3 scripts/verify_pdf.py [path/to.pdf]
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from build_pdf import PDF_OUT, PER_PAGE  # noqa: E402

WS = re.compile(r"\s+")


def page_text(pdf: pathlib.Path, page: int) -> str:
    out = subprocess.run(
        ["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(pdf), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return WS.sub(" ", out)


def main() -> int:
    pdf = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else PDF_OUT
    data = json.loads((ROOT / "data" / "charts.json").read_text(encoding="utf-8"))
    failures: list[str] = []

    plan, page_no = [], 2
    for family in data["families"]:
        pages = max(1, -(-len(family["charts"]) // PER_PAGE))
        plan.append((family, page_no, pages))
        page_no += pages
    expected_pages = page_no - 1

    info = subprocess.run(
        ["pdfinfo", str(pdf)], check=True, capture_output=True, text=True
    ).stdout
    pages = int(re.search(r"Pages:\s+(\d+)", info).group(1))
    if pages != expected_pages:
        failures.append(f"page count {pages} != planned {expected_pages}")
    if "594.96 x 841.92 pts" not in info:
        failures.append("page size is not A4")

    total_charts = sum(len(f["charts"]) for f in data["families"])
    cover = page_text(pdf, 1)
    if f"{total_charts} charts" not in cover:
        failures.append(f"cover does not state {total_charts} charts")

    checked = 0
    for family, first, count in plan:
        for index in range(count):
            page = first + index
            text = page_text(pdf, page)
            chunk = family["charts"][index * PER_PAGE : (index + 1) * PER_PAGE]
            for chart in chunk:
                checked += 1
                if chart["title"] not in text:
                    failures.append(f"p{page}: missing chart {chart['title']!r}")
            if family["title"].upper() not in text.upper():
                failures.append(f"p{page}: missing family header {family['title']!r}")
            # the header is uppercased by CSS, so match case-insensitively
            if f"page {page} / {pages}" not in text.lower():
                failures.append(f"p{page}: page number missing")

    print(f"pages: {pages}  charts found: {checked}/{total_charts}")
    if failures:
        for failure in failures:
            print("FAIL", failure)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
