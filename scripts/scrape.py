#!/usr/bin/env python3
"""Scrape the PlusEV preflop chart library into one normalised JSON file.

Source: https://plusev.poker/charts/ (6-max cash, 100 big blinds).
Each source page is static HTML where every hand cell carries its exact action
fractions in ``data-tip`` and its colour (or colour split) in ``style``.

Usage:
    python3 scripts/scrape.py            # use cached HTML in data/raw if present
    python3 scripts/scrape.py --refresh  # re-download every page first
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "charts.json"

BASE = "https://plusev.poker/charts/"
FAMILIES = [
    ("rfi", "Raise first in", ""),
    ("facing-a-raise", "Facing a raise", "facing-a-raise/"),
    ("facing-a-3-bet", "Facing a 3-bet", "facing-a-3-bet/"),
    ("facing-a-4-bet", "Facing a 4-bet", "facing-a-4-bet/"),
    ("facing-a-4-bet-all-in", "Facing a 4-bet all-in", "facing-a-4-bet-all-in/"),
    ("facing-a-5-bet-all-in", "Facing a 5-bet all-in", "facing-a-5-bet-all-in/"),
    ("cold-4-bet", "Cold 4-bet", "cold-4-bet/"),
    ("squeezing", "Squeezes", "squeezing/"),
]

SEAT_NAMES = {
    "utg": "UTG",
    "hj": "HJ",
    "co": "CO",
    "btn": "BTN",
    "sb": "SB",
    "bb": "BB",
}

TAG = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")
ATTR = re.compile(r'(\w[\w-]*)="([^"]*)"')
CELL = re.compile(r"<td\b([^>]*)>(.*?)</td>", re.S)
FIGURE = re.compile(r'<figure class="range-grid">(.*?)</figure>', re.S)
SECTION = re.compile(r"<section\b([^>]*)>")
H2 = re.compile(r"<h2\b[^>]*>(.*?)</h2>", re.S)
H3 = re.compile(r"<h3\b[^>]*>(.*?)</h3>", re.S)
CAPTION = re.compile(r"<caption\b[^>]*>(.*?)</caption>", re.S)
LEGEND_KEY = re.compile(
    r'<span class="range-key"><i style="background:(#[0-9A-Fa-f]{6})"></i>(.*?)</span>'
)
# RFI pages use class="opener-stat", the other families use class="spot-stat".
STAT = re.compile(r'<p class="(?:spot|opener)-stat[^"]*"[^>]*>(.*?)</p>', re.S)


def text(fragment: str) -> str:
    return WS.sub(" ", html.unescape(TAG.sub("", fragment))).strip()


def attrs(fragment: str) -> dict[str, str]:
    return {k: html.unescape(v) for k, v in ATTR.findall(fragment)}


def fetch(family_id: str, path: str, refresh: bool) -> str:
    RAW.mkdir(parents=True, exist_ok=True)
    cache = RAW / f"{family_id}.html"
    if cache.exists() and not refresh:
        return cache.read_text(encoding="utf-8")
    url = BASE + path
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (study charts)"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode("utf-8")
    cache.write_text(body, encoding="utf-8")
    return body


def parse_segments(style: str) -> list[dict]:
    """Turn a cell style into ordered colour segments in percent."""
    style = html.unescape(style)
    flat = re.fullmatch(r"\s*background:\s*(#[0-9A-Fa-f]{6})\s*;?\s*", style)
    if flat:
        return [{"color": flat.group(1).upper(), "from": 0.0, "to": 100.0}]

    grad = re.search(r"linear-gradient\((.*)\)", style)
    if not grad:
        raise ValueError(f"unrecognised cell style: {style!r}")

    stops: list[tuple[str, list[float]]] = []
    for part in grad.group(1).split(","):
        part = part.strip()
        color = re.match(r"#[0-9A-Fa-f]{6}", part)
        if not color:
            continue  # "to right"
        pcts = [float(p) for p in re.findall(r"([\d.]+)%", part)]
        stops.append((color.group(0).upper(), pcts))

    segments = []
    for i, (color, pcts) in enumerate(stops):
        start = pcts[0] if pcts else 0.0
        if len(pcts) > 1:
            end = pcts[1]
        elif i + 1 < len(stops) and stops[i + 1][1]:
            end = stops[i + 1][1][0]
        else:
            end = 100.0
        segments.append({"color": color, "from": start, "to": end})
    return segments


NOT_IN_RANGE = "Not in range"


def parse_actions(tip: str) -> list[dict]:
    """Action fractions from a data-tip such as "K9s\nFold: 100%"."""
    actions = []
    for line in tip.split("\n")[1:]:
        match = re.fullmatch(r"\s*(.+?):\s*([\d.]+)%\s*", line)
        if match:
            actions.append({"name": match.group(1).strip(), "pct": float(match.group(2))})
    return actions


def parse_chart(figure: str, block: str) -> dict:
    cell_html = re.search(r"<table\b.*?</table>", figure, re.S)
    if not cell_html:
        raise ValueError("figure without table")
    cells = []
    for raw_attrs, body in CELL.findall(cell_html.group(0)):
        a = attrs(raw_attrs)
        hand = text(body)
        tip = a.get("data-tip", "")
        actions = parse_actions(tip)
        cells.append(
            {
                "hand": hand,
                "actions": actions,
                # hands the previous player never holds are drawn dark, not folded
                "out_of_range": not actions and NOT_IN_RANGE in tip,
                "segments": parse_segments(a.get("style", "")),
            }
        )

    legend = [
        {"color": color.upper(), "label": text(label)}
        for color, label in LEGEND_KEY.findall(figure)
    ]

    stat_match = STAT.search(block)
    stat = text(stat_match.group(1)) if stat_match else ""
    # the source appends a link label inside the same paragraph
    stat = stat.split(" Why this seat plays this way")[0]
    stat = re.sub(r"\s+([,.])", r"\1", stat)
    pct = re.search(r"([\d.]+)% of hands", stat)
    combos = re.search(r"([\d,]+) of 1,326", stat)
    open_to = re.search(r"opening to ([\d.]+)\s*bb", stat)
    raise_to = re.search(r"raising to ([\d.]+)\s*bb", stat)

    caption = re.search(r"<caption\b[^>]*>(.*?)</caption>", figure, re.S)
    return {
        "caption": text(caption.group(1)) if caption else "",
        "stat": stat,
        "chosen_pct": float(pct.group(1)) if pct else None,
        "chosen_combos": int(combos.group(1).replace(",", "")) if combos else None,
        "open_to": float(open_to.group(1)) if open_to else None,
        "raise_to": float(raise_to.group(1)) if raise_to else None,
        "legend": legend,
        "cells": cells,
    }


def parse_page(family_id: str, family_title: str, document: str) -> list[dict]:
    starts = [m.start() for m in SECTION.finditer(document)]
    starts.append(len(document))
    charts = []
    for start, end in zip(starts, starts[1:]):
        block = document[start:end]
        if 'class="range-grid"' not in block:
            continue
        open_tag = SECTION.match(block)
        section_attrs = attrs(open_tag.group(1)) if open_tag else {}
        seat_id = section_attrs.get("id", "")
        h2 = H2.search(block)
        section_title = text(h2.group(1)) if h2 else ""
        seat = SEAT_NAMES.get(seat_id, seat_id.upper() or section_title)

        figures = list(FIGURE.finditer(block))
        heads = [(m.start(), text(m.group(1))) for m in H3.finditer(block)]
        for index, figure in enumerate(figures):
            spot = ""
            for position, label in heads:
                if position < figure.start():
                    spot = label
                else:
                    break
            chart = parse_chart(figure.group(1), block[figure.end() :])
            slug = re.sub(r"[^a-z0-9]+", "-", spot.lower()).strip("-") if spot else "open"
            chart.update(
                {
                    "id": f"{family_id}-{seat.lower()}-{slug}",
                    "family": family_id,
                    "family_title": family_title,
                    "seat": seat,
                    "spot": spot,
                    "section_title": section_title,
                    "title": f"{seat} {spot}" if spot else f"{seat} open",
                }
            )
            charts.append(chart)
    return charts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="re-download source pages")
    args = parser.parse_args()

    families = []
    for family_id, title, path in FAMILIES:
        document = fetch(family_id, path, args.refresh)
        h1 = re.search(r"<h1\b[^>]*>(.*?)</h1>", document, re.S)
        charts = parse_page(family_id, title, document)
        families.append(
            {
                "id": family_id,
                "title": title,
                "page_title": text(h1.group(1)) if h1 else title,
                "url": BASE + path,
                "charts": charts,
            }
        )
        print(f"{family_id:24s} {len(charts):3d} charts  {title}", file=sys.stderr)

    payload = {
        "source": {
            "site": BASE,
            "license_note": "Free public charts from plusev.poker, exported for personal study.",
            "format": "6-max cash, 100 big blinds",
            "fetched": dt.date.today().isoformat(),
            "sha256": hashlib.sha256(
                json.dumps(
                    [[f["id"], len(f["charts"])] for f in families], sort_keys=True
                ).encode()
            ).hexdigest()[:16],
        },
        "families": families,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    total = sum(len(f["charts"]) for f in families)
    print(f"{total} charts -> {OUT.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
