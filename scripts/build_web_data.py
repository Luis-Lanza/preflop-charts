#!/usr/bin/env python3
"""Build the payload the Astro page renders (spec S7 of astro-preflop-web.md).

Reads data/charts.json (produced by scripts/scrape.py) and writes
web/src/data/charts.json with:

  * one flat list of the 114 spots, each with its colour-coded grid,
  * a `nav` tree that mirrors how a hand is built: your seat, then who is in
    the hand (nobody / one rival / two rivals), then the situation that pair
    unlocks,
  * structured action steps so the client can show the breadcrumb and knows
    which seats took part,
  * cells as indexes into a deduplicated table of colour splits.

The client indexes this data; it never derives poker structure itself.

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
    "facing-a-3-bet",
    "facing-a-4-bet",
    "facing-a-4-bet-all-in",
    "facing-a-5-bet-all-in",
    "squeezing",
    "cold-4-bet",
]

DECISION = {
    "rfi": "Your open",
    "facing-a-raise": "Fold, call or 3-bet",
    "facing-a-3-bet": "Fold, call or 4-bet",
    "facing-a-4-bet": "Fold, call or 5-bet",
    "facing-a-4-bet-all-in": "Call or fold for stacks",
    "facing-a-5-bet-all-in": "Call or fold for stacks",
    "squeezing": "Fold or squeeze",
    "cold-4-bet": "Fold or cold 4-bet",
}

# what the situation chip says: the action waiting for you
CHIP = {
    "rfi": "Everyone folded",
    "facing-a-raise": "Rival opens",
    "facing-a-3-bet": "Rival 3-bets",
    "facing-a-4-bet": "Rival 4-bets",
    "facing-a-4-bet-all-in": "Rival 4-bet jam",
    "facing-a-5-bet-all-in": "Rival 5-bet jam",
    "squeezing": "Squeeze",
    "cold-4-bet": "Cold 4-bet",
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
    stat = stat.replace("AIbb", "all-in").replace("  ", " ").strip().rstrip(".")
    return stat.replace(" of hands,", " of hands,")


def build_lookups(charts: list[dict]) -> dict:
    open_size, three_bet, four_bet = {}, {}, {}
    for chart in charts:
        size = hero_size(chart)
        if chart["family"] == "rfi":
            open_size[chart["seat"]] = (
                f"{chart['open_to']:g}bb" if chart["open_to"] else ""
            )
        elif chart["family"] == "facing-a-raise":
            for opener, action in parse_spot(chart["spot"]):
                if action == "open":
                    three_bet[(chart["seat"], opener)] = size
        elif chart["family"] == "facing-a-3-bet":
            for villain, action in parse_spot(chart["spot"]):
                if action == "3-bet":
                    four_bet[(chart["seat"], villain)] = size
    return {"open": open_size, "three_bet": three_bet, "four_bet": four_bet}


def steps(chart: dict, lookups: dict) -> list[dict]:
    """Structured record of the action sequence: who did what, in order.

    `actor` is a seat label, or "you" for the hero's own actions. `text` is the
    breadcrumb line, so prose and structure can never drift apart.
    """
    family, hero = chart["family"], chart["seat"]
    names = [seat for seat, _ in parse_spot(chart["spot"])]
    opens = lookups["open"]
    three, four = lookups["three_bet"], lookups["four_bet"]
    open_sz = lambda seat: opens.get(seat) or "2.5bb"  # noqa: E731

    out: list[dict] = []

    def add(actor: str, action: str, text: str) -> None:
        out.append({"actor": actor, "action": action, "text": text})

    if family == "rfi":
        add("you", "open", "Everyone folds to you")

    elif family == "facing-a-raise":
        villain = names[0]
        add(villain, "open", f"{villain} opens to {open_sz(villain)}")
        add("you", "respond", f"You are in {hero}")

    elif family == "facing-a-3-bet":
        villain = names[0]
        add("you", "open", f"You open from {hero} to {open_sz(hero)}")
        if three.get((villain, hero)):
            add(villain, "3bet", f"{villain} 3-bets to {three[(villain, hero)]}bb")
        else:
            add(villain, "3bet", f"{villain} 3-bets")

    elif family == "facing-a-4-bet":
        villain = names[0]
        add(villain, "open", f"{villain} opens to {open_sz(villain)}")
        if three.get((hero, villain)):
            add("you", "3bet", f"You 3-bet to {three[(hero, villain)]}bb")
        else:
            add("you", "3bet", "You 3-bet")
        if four.get((villain, hero)):
            add(villain, "4bet", f"{villain} 4-bets to {four[(villain, hero)]}bb")
        else:
            add(villain, "4bet", f"{villain} 4-bets")

    elif family == "facing-a-4-bet-all-in":
        villain = names[0]
        add(villain, "open", f"{villain} opens to {open_sz(villain)}")
        if three.get((hero, villain)):
            add("you", "3bet", f"You 3-bet to {three[(hero, villain)]}bb")
        else:
            add("you", "3bet", "You 3-bet")
        add(villain, "4bet-jam", f"{villain} shoves all-in")

    elif family == "facing-a-5-bet-all-in":
        villain = names[0]
        add("you", "open", f"You open from {hero} to {open_sz(hero)}")
        if three.get((villain, hero)):
            add(villain, "3bet", f"{villain} 3-bets to {three[(villain, hero)]}bb")
        else:
            add(villain, "3bet", f"{villain} 3-bets")
        if four.get((hero, villain)):
            add("you", "4bet", f"You 4-bet to {four[(hero, villain)]}bb")
        else:
            add("you", "4bet", "You 4-bet")
        add(villain, "5bet-jam", f"{villain} 5-bet shoves all-in")

    elif family == "cold-4-bet":
        opener, three_bettor = names[0], names[1]
        add(opener, "open", f"{opener} opens to {open_sz(opener)}")
        if three.get((three_bettor, opener)):
            add(
                three_bettor,
                "3bet",
                f"{three_bettor} 3-bets to {three[(three_bettor, opener)]}bb",
            )
        else:
            add(three_bettor, "3bet", f"{three_bettor} 3-bets")
        add("you", "cold-4bet", f"You cold 4-bet from {hero} to {hero_size(chart)}bb")

    elif family == "squeezing":
        opener, caller = names[0], names[1]
        add(opener, "open", f"{opener} opens to {open_sz(opener)}")
        add(caller, "call", f"{caller} calls")
        add("you", "squeeze", f"You squeeze from {hero} to {hero_size(chart)}bb")

    else:
        raise ValueError(f"unhandled family {family}")

    return out


def main() -> int:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    charts = [c for family in source["families"] for c in family["charts"]]
    lookups = build_lookups(charts)

    hands = [cell["hand"] for cell in charts[0]["cells"]]
    for chart in charts:
        if [cell["hand"] for cell in chart["cells"]] != hands:
            raise SystemExit(f"cell order differs in {chart['id']}")
    combos = [6 if len(h) == 2 else 4 if h.endswith("s") else 12 for h in hands]

    patterns: list[list[dict]] = []
    pattern_index: dict[tuple, int] = {}

    def pattern_id(cell: dict) -> str:
        key = tuple(
            (seg["color"], round(seg["from"], 1), round(seg["to"], 1))
            for seg in cell["segments"]
        )
        if key not in pattern_index:
            pattern_index[key] = len(patterns)
            patterns.append([{"color": c, "from": f, "to": t} for c, f, t in key])
        return code(pattern_index[key])

    family_order = {family: index for index, family in enumerate(FAMILY_ORDER)}
    spots: list[dict] = []
    for chart in charts:
        if not chart["seat"]:
            raise SystemExit(f"chart without a seat: {chart['id']}")
        steps_ = steps(chart, lookups)
        # one entry per opponent, in the order they first act (a villain who
        # opens and later 4-bets is still one rival)
        rivals = list(
            dict.fromkeys(step["actor"] for step in steps_ if step["actor"] != "you")
        )
        spots.append(
            {
                "id": chart["id"],
                "family": chart["family"],
                "familyLabel": chart["family_title"],
                "hero": chart["seat"],
                "headline": chart["spot"] or "Everyone folded",
                "chip": CHIP[chart["family"]],
                "decision": DECISION[chart["family"]],
                "steps": [{"seat": s["actor"], "action": s["action"]} for s in steps_],
                "history": [s["text"] for s in steps_],
                "rivals": rivals,
                "stat": clean_stat(chart["stat"]),
                "action": raise_label(chart),
                "legend": chart["legend"],
                "g": "".join(pattern_id(cell) for cell in chart["cells"]),
            }
        )

    by_id = {spot["id"]: spot for spot in spots}
    if len(by_id) != len(spots):
        raise SystemExit("duplicate spot ids")

    def situation(spot: dict) -> dict:
        return {"id": spot["id"], "label": spot["chip"], "sub": spot["familyLabel"]}

    nav: dict[str, dict] = {}
    for seat in SEATS:
        own = [spot for spot in spots if spot["hero"] == seat]
        solo = next((s for s in own if not s["rivals"]), None)
        pairs: list[dict] = []
        for rival in SEATS:
            if rival == seat:
                continue
            situations = sorted(
                (s for s in own if s["rivals"] == [rival]),
                key=lambda s: family_order[s["family"]],
            )
            if not situations:
                continue
            pairs.append(
                {
                    "rival": rival.lower(),
                    "label": rival,
                    "side": "before" if SEAT_ORDER[rival] < SEAT_ORDER[seat] else "after",
                    "situations": [situation(s) for s in situations],
                }
            )
        triples: list[dict] = []
        for opener in SEATS:
            for third in SEATS:
                if opener == third:
                    continue
                situations = sorted(
                    (s for s in own if s["rivals"] == [opener, third]),
                    key=lambda s: family_order[s["family"]],
                )
                if not situations:
                    continue
                triples.append(
                    {
                        "opener": opener.lower(),
                        "openerLabel": opener,
                        "third": third.lower(),
                        "thirdLabel": third,
                        "situations": [situation(s) for s in situations],
                    }
                )
        # the big blind never opens, so it has no solo spot
        nav[seat.lower()] = {
            "solo": situation(solo) if solo else None,
            "pairs": pairs,
            "triples": triples,
        }

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
        "spots": spots,
        "nav": nav,
        "heroes": [{"id": seat.lower(), "label": seat} for seat in SEATS],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8"
    )
    total = sum(
        (1 if n["solo"] else 0)
        + sum(len(p["situations"]) for p in n["pairs"])
        + sum(len(t["situations"]) for t in n["triples"])
        for n in nav.values()
    )
    print(
        f"{len(spots)} spots ({total} in nav), {len(patterns)} patterns -> "
        f"{OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
