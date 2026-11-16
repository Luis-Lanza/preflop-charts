"""Data integrity tests for data/charts.json (task T1, specs S1/S4/S5).

Run: python3 -m unittest discover -s tests -v
"""

import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "charts.json"

RANKS = "AKQJT98765432"
# The 13x13 grid: diagonal is pairs, above it suited, below it offsuit.
# Offsuit cells still name the higher rank first (cell K,A is "AKo", not "KAo").
HANDS = [
    r + c + "s" if i < j else r + c if i == j else c + r + "o"
    for i, r in enumerate(RANKS)
    for j, c in enumerate(RANKS)
]
EXPECTED_FAMILIES = {
    "rfi": 5,
    "facing-a-raise": 15,
    "facing-a-3-bet": 15,
    "facing-a-4-bet": 15,
    "facing-a-4-bet-all-in": 9,  # site index claims 12; the page publishes 9
    "facing-a-5-bet-all-in": 15,
    "cold-4-bet": 20,
    "squeezing": 20,
}
RFI_STATS = {
    "UTG": (17.5, 232),
    "HJ": (21.6, 286),
    "CO": (28.5, 378),
    "BTN": (40.5, 538),
    "SB": (55.8, 740),
}


def load():
    if not DATA.exists():
        raise AssertionError(f"missing {DATA}; run scripts/scrape.py first")
    return json.loads(DATA.read_text())


class ChartsDataTest(unittest.TestCase):
    def setUp(self):
        self.data = load()
        self.charts = [c for f in self.data["families"] for c in f["charts"]]

    def test_family_sizes_and_total(self):
        got = {f["id"]: len(f["charts"]) for f in self.data["families"]}
        self.assertEqual(got, EXPECTED_FAMILIES)
        self.assertEqual(len(self.charts), 114)  # 117 claimed by the index, 114 published

    def test_every_chart_has_the_169_hands_once(self):
        for chart in self.charts:
            with self.subTest(chart=chart["id"]):
                self.assertEqual(len(chart["cells"]), 169)
                self.assertEqual([c["hand"] for c in chart["cells"]], HANDS)

    def test_action_fractions_sum_to_100(self):
        for chart in self.charts:
            for cell in chart["cells"]:
                with self.subTest(chart=chart["id"], hand=cell["hand"]):
                    if cell["out_of_range"]:
                        self.assertEqual(cell["actions"], [])
                        continue
                    self.assertAlmostEqual(
                        sum(a["pct"] for a in cell["actions"]), 100.0, delta=1.0
                    )

    def test_colour_segments_sum_to_100(self):
        for chart in self.charts:
            for cell in chart["cells"]:
                with self.subTest(chart=chart["id"], hand=cell["hand"]):
                    self.assertAlmostEqual(
                        sum(s["to"] - s["from"] for s in cell["segments"]),
                        100.0,
                        delta=1.0,
                    )

    def test_cell_colours_come_from_the_chart_legend(self):
        for chart in self.charts:
            legend = {entry["color"] for entry in chart["legend"]}
            with self.subTest(chart=chart["id"]):
                self.assertTrue(legend, "chart has no legend")
                for cell in chart["cells"]:
                    allowed = legend | ({"#1F1E1E"} if cell["out_of_range"] else set())
                    for seg in cell["segments"]:
                        self.assertIn(seg["color"], allowed)

    def test_charts_are_identified(self):
        for chart in self.charts:
            with self.subTest(chart=chart["id"]):
                self.assertTrue(chart["title"])
                self.assertTrue(chart["stat"])
                self.assertGreaterEqual(len(chart["legend"]), 2)

    def test_rfi_percentages_match_the_published_figures(self):
        rfi = next(f for f in self.data["families"] if f["id"] == "rfi")
        got = {
            c["seat"]: (c["chosen_pct"], c["chosen_combos"]) for c in rfi["charts"]
        }
        self.assertEqual(got, RFI_STATS)

    def test_format_is_6max_100bb(self):
        self.assertEqual(self.data["source"]["format"], "6-max cash, 100 big blinds")


if __name__ == "__main__":
    unittest.main()
