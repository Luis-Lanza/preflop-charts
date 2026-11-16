#!/usr/bin/env python3
"""Build the compact payload the Astro page renders (spec S7).

Reads data/charts.json (produced by scripts/scrape.py) and writes
web/src/data/charts.json with:

  * every chart grouped by the seat that has to act,
  * a precomputed hero + spot -> chart resolution (the client never derives
    poker semantics),
  * cells as indexes into a deduplicated table of colour splits,
  * a generated action history with the sizes found in the data itself.

Usage: python3 scripts/build_web_data.py
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "charts.json"
OUT = ROOT / "web" / "src" / "data" / "charts.json"

SEATS = ["UTG", "HJ", "CO", "BTN", "SB", "BB"]
SEAT_ORDER = {seat: index for index, seat in enumerate(SEATS)}
OUT_OF_RANGE = "#1F1E1E"

FAMILY_ORDER = [
    "rfi",
    "facing-a-raise",
    "squeezing",
    "facing-a-3-bet",
    "facing-a-4-bet",
    "facing-a-4-bet-all-in",
    "facing-a-5-bet-all-in",
    "cold-4-bet",
]

DECISION = {
    "rfi": "Your open",
    "facing-a-raise": "Fold, call or 3-bet",
    "squeezing": "Fold or squeeze",
    "facing-a-3-bet": "Fold, call or 4-bet",
    "facing-a-4-bet": "Fold, call or 5-bet",
    "facing-a-4-bet-all-in": "Call or fold for stacks",
    "facing-a-5-bet-all-in": "Call or fold for stacks",
    "cold-4-bet": "Fold or cold 4-bet",
}

BASE36 = "0123456789abcdefghijklmnopqrstuvwxyz"


def code(index: int) -> str:
    return BASE36[index // 36] + BASE36[index % 36]


def raise_label(chart: dict) -> str:
    for entry in chart["legend"]:
        if entry["label"].startswith(("Raise", "All-In")):
            return entry["label"]
    return ""


def hero_size(chart: dict) -> str:
    label = raise_label(chart)
    if label.startswith("All-In"):
        return "all-in"
    return label.removeprefix("Raise ")


def sized(size: str, fallback: str) -> str:
    return fallback if not size else f"{fallback} {size}"


def parse_spot(spot: str) -> list[tuple[str, str]]:
    """'vs UTG open, HJ 3-bet' -> [('UTG', 'open'), ('HJ', '3-bet')]."""
    if not spot.startswith("vs "):
        return []
    parts = []
    for chunk in spot[3:].split(", "):
        tokens = chunk.split()
        if len(tokens) >= 2:
            parts.append((tokens[0], " ".join(tokens[1:])))
    return parts


def clean_stat(stat: str) -> str:
    stat = stat.replace("AIbb", "all-in").replace("  ", " ").strip()
    return stat.rstrip(".").replace(" of hands,", " of hands,")


def build_lookups(charts: list[dict]) -> dict:
    open_size = {}
    three_bet = {}
    four_bet = {}
    for chart in charts:
        size = hero_size(chart)
        if chart["family"] == "rfi":
            open_size[chart["seat"]] = f"{chart['open_to']:g}bb" if chart["open_to"] else ""
        elif chart["family"] == "facing-a-raise":
            # hero 3-bets over the opener named in the spot
            for opener, action in parse_spot(chart["spot"]):
                if action == "open":
                    three_bet[(chart["seat"], opener)] = size
        elif chart["family"] == "facing-a-3-bet":
            # hero opened, villain 3-bet, hero's raise is the 4-bet size
            for villain, action in parse_spot(chart["spot"]):
                if action == "3-bet":
                    four_bet[(chart["seat"], villain)] = size
    return {"open": open_size, "three_bet": three_bet, "four_bet": four_bet}


def history(chart: dict, lookups: dict) -> list[str]:
    family, hero, spot = chart["family"], chart["seat"], chart["spot"]
    parts = parse_spot(spot)
    opens, three, four = lookups["open"], lookups["three_bet"], lookups["four_bet"]
    names = [seat for seat, _ in parts]

    if family == "rfi":
        return ["Everyone folds to you"]

    if family == "facing-a-raise":
        villain = names[0]
        return [
            f"{villain} opens to {opens.get(villain) or '2.5bb'}",
            f"You are in {hero}",
        ]

    if family == "facing-a-3-bet":
        villain = names[0]
        lines = [f"You open from {hero} to {opens.get(hero) or '2.5bb'}"]
        if three.get((villain, hero)):
            lines.append(f"{villain} 3-bets to {three[(villain, hero)]}bb")
        else:
            lines.append(f"{villain} 3-bets")
        return lines

    if family == "facing-a-4-bet":
        villain = names[0]
        lines = [f"{villain} opens to {opens.get(villain) or '2.5bb'}"]
        if three.get((hero, villain)):
            lines.append(f"You 3-bet to {three[(hero, villain)]}bb")
        else:
            lines.append("You 3-bet")
        if four.get((villain, hero)):
            lines.append(f"{villain} 4-bets to {four[(villain, hero)]}bb")
        else:
            lines.append(f"{villain} 4-bets")
        return lines

    if family == "facing-a-4-bet-all-in":
        villain = names[0]
        lines = [f"{villain} opens to {opens.get(villain) or '2.5bb'}"]
        if three.get((hero, villain)):
            lines.append(f"You 3-bet to {three[(hero, villain)]}bb")
        else:
            lines.append("You 3-bet")
        lines.append(f"{villain} shoves all-in")
        return lines

    if family == "facing-a-5-bet-all-in":
        villain = names[0]
        lines = [f"You open from {hero} to {opens.get(hero) or '2.5bb'}"]
        if three.get((villain, hero)):
            lines.append(f"{villain} 3-bets to {three[(villain, hero)]}bb")
        else:
            lines.append(f"{villain} 3-bets")
        if four.get((hero, villain)):
            lines.append(f"You 4-bet to {four[(hero, villain)]}bb")
        else:
            lines.append("You 4-bet")
        lines.append(f"{villain} 5-bet shoves all-in")
        return lines

    if family == "cold-4-bet":
        opener, three_bettor = names[0], names[1]
        lines = [f"{opener} opens to {opens.get(opener) or '2.5bb'}"]
        if three.get((three_bettor, opener)):
            lines.append(f"{three_bettor} 3-bets to {three[(three_bettor, opener)]}bb")
        else:
            lines.append(f"{three_bettor} 3-bets")
        lines.append(f"You cold 4-bet from {hero} to {hero_size(chart)}bb")
        return lines

    if family == "squeezing":
        opener, caller = names[0], names[1]
        return [
            f"{opener} opens to {opens.get(opener) or '2.5bb'}",
            f"{caller} calls",
            f"You squeeze from {hero} to {hero_size(chart)}bb",
        ]

    raise ValueError(f"unhandled family {family}")


def main() -> int:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    charts = [c for family in source["families"] for c in family["charts"]]
    lookups = build_lookups(charts)

    # every chart must use the same 169-cell order, so the client can label cells
    hands = [cell["hand"] for cell in charts[0]["cells"]]
    for chart in charts:
        if [cell["hand"] for cell in chart["cells"]] != hands:
            raise SystemExit(f"cell order differs in {chart['id']}")
    combos = [6 if len(h) == 2 else 4 if h.endswith("s") else 12 for h in hands]

    patterns: list[list[dict]] = []
    pattern_index: dict[tuple, int] = {}

    def pattern_key(cell: dict) -> tuple:
        return tuple(
            (seg["color"], round(seg["from"], 1), round(seg["to"], 1))
            for seg in cell["segments"]
        )

    def pattern_id(cell: dict) -> str:
        key = pattern_key(cell)
        if key not in pattern_index:
            pattern_index[key] = len(patterns)
            patterns.append(
                [
                    {"color": c, "from": f, "to": t}
                    for c, f, t in key
                ]
            )
        return code(pattern_index[key])

    spots: list[dict] = []
    for chart in charts:
        if not chart["seat"]:
            raise SystemExit(f"chart without a seat: {chart['id']}")
        spots.append(
            {
                "id": chart["id"],
                "family": chart["family"],
                "familyLabel": chart["family_title"],
                "hero": chart["seat"],
                "heroLabel": chart["seat"],
                "headline": chart["spot"] or "Everyone folded",
                "decision": DECISION[chart["family"]],
                "history": history(chart, lookups),
                "stat": clean_stat(chart["stat"]),
                "action": raise_label(chart),
                "legend": chart["legend"],
                "g": "".join(pattern_id(cell) for cell in chart["cells"]),
            }
        )

    order = {family: index for index, family in enumerate(FAMILY_ORDER)}

    def villain_rank(spot: dict) -> tuple:
        """Order spots by who acted first, not alphabetically (UTG before BB)."""
        seats = [seat for seat, _ in parse_spot(spot["headline"])]
        return tuple(SEAT_ORDER.get(seat, 99) for seat in seats) or (0,)

    spots.sort(
        key=lambda s: (
            SEAT_ORDER.get(s["hero"], 99),
            order.get(s["family"], 99),
            villain_rank(s),
        )
    )

    payload = {
        "meta": {
            "format": source["source"]["format"],
            "source": "plusev.poker/charts",
            "built": dt.date.today().isoformat(),
            "charts": len(spots),
            "patterns": len(patterns),
            # g is one base-36 code per cell: 2 characters each, 169 cells per chart
            "cellsPerChart": 169,
            "codeWidth": 2,
        },
        "patterns": patterns,
        "hands": hands,
        "combos": combos,
        "heroes": [
            {
                "id": seat.lower(),
                "label": seat,
                "spots": [s for s in spots if s["hero"] == seat],
            }
            for seat in SEATS
        ],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8"
    )
    size = OUT.stat().st_size
    print(
        f"{len(spots)} spots, {len(patterns)} patterns -> {OUT.relative_to(ROOT)} ({size / 1024:.0f} KB)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
