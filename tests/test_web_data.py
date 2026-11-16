"""Integrity tests for the web payload in web/src/data/charts.json (spec S7).

Run: python3 -m unittest discover -s tests -v
"""

import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "charts.json"
WEB = ROOT / "web" / "src" / "data" / "charts.json"

SEATS = ["UTG", "HJ", "CO", "BTN", "SB", "BB"]
CELLS = 169
CODE_WIDTH = 2
OUT_OF_RANGE = "#1F1E1E"


def codes(chart):
    """The g string packs one base-36 pattern code per cell, CODE_WIDTH chars each."""
    g = chart["g"]
    return [g[i : i + CODE_WIDTH] for i in range(0, len(g), CODE_WIDTH)]


def load(path):
    if not path.exists():
        raise AssertionError(f"missing {path}; run the build scripts first")
    return json.loads(path.read_text(encoding="utf-8"))


class WebPayloadTest(unittest.TestCase):
    def setUp(self):
        self.payload = load(WEB)
        self.source = load(SOURCE)
        self.heroes = {h["id"]: h for h in self.payload["heroes"]}
        self.spots = [s for h in self.payload["heroes"] for s in h["spots"]]

    def test_six_heroes_in_action_order(self):
        self.assertEqual([h["label"] for h in self.payload["heroes"]], SEATS)
        self.assertEqual(sorted(self.heroes), sorted(s.lower() for s in SEATS))

    def test_every_source_chart_is_reachable_once(self):
        source_ids = {
            c["id"] for f in self.source["families"] for c in f["charts"]
        }
        web_ids = [s["id"] for s in self.spots]
        self.assertEqual(len(web_ids), len(set(web_ids)), "duplicate spot ids")
        self.assertEqual(set(web_ids), source_ids)
        self.assertEqual(len(web_ids), 114)

    def test_no_hero_has_an_empty_or_single_spot_list(self):
        for hero in self.payload["heroes"]:
            with self.subTest(hero=hero["id"]):
                self.assertGreater(len(hero["spots"]), 1)

    def test_every_chart_has_169_valid_pattern_indexes(self):
        patterns = self.payload["patterns"]
        for spot in self.spots:
            with self.subTest(spot=spot["id"]):
                packed = codes(spot)
                self.assertEqual(len(packed), CELLS)
                for code in packed:
                    index = int(code, 36)
                    self.assertLess(index, len(patterns), f"bad index {code}")

    def test_patterns_are_complete_colour_splits(self):
        for index, segments in enumerate(self.payload["patterns"]):
            with self.subTest(pattern=index):
                self.assertTrue(segments)
                self.assertAlmostEqual(
                    sum(seg["to"] - seg["from"] for seg in segments), 100.0, delta=1.0
                )
                self.assertEqual(segments[0]["from"], 0.0)
                self.assertEqual(segments[-1]["to"], 100.0)

    def test_legend_covers_every_colour_used(self):
        patterns = self.payload["patterns"]
        for spot in self.spots:
            legend = {entry["color"]: entry["label"] for entry in spot["legend"]}
            with self.subTest(spot=spot["id"]):
                self.assertTrue(legend)
                for code in codes(spot):
                    for seg in patterns[int(code, 36)]:
                        color = seg["color"]
                        if color == OUT_OF_RANGE:
                            continue
                        self.assertIn(color, legend, f"{color} missing from legend")

    def test_each_spot_is_self_describing(self):
        for spot in self.spots:
            with self.subTest(spot=spot["id"]):
                self.assertTrue(spot["headline"])
                self.assertTrue(spot["decision"])
                self.assertTrue(spot["stat"])
                self.assertGreaterEqual(len(spot["history"]), 1)
                for line in spot["history"]:
                    self.assertTrue(line.strip())
                self.assertIn(spot["family"], {
                    f["id"] for f in self.source["families"]
                })

    def test_hero_appears_in_its_own_history(self):
        for hero in self.payload["heroes"]:
            for spot in hero["spots"]:
                with self.subTest(spot=spot["id"]):
                    joined = " ".join(spot["history"]).lower()
                    self.assertTrue(
                        hero["label"].lower() in joined or "you" in joined,
                        f"history never mentions the hero: {spot['history']}",
                    )

    def test_history_states_a_size_where_one_exists(self):
        sized = [s for s in self.spots if any("bb" in line for line in s["history"])]
        # most spots involve a bet, so most histories must carry a size
        self.assertGreater(len(sized), 100)

    def test_hands_and_combo_weights_are_shared(self):
        hands = self.payload["hands"]
        combos = self.payload["combos"]
        self.assertEqual(len(hands), CELLS)
        self.assertEqual(len(set(hands)), CELLS)
        self.assertEqual(len(combos), CELLS)
        self.assertEqual(sum(combos), 1326)
        self.assertEqual(hands[0], "AA")
        self.assertEqual(hands[-1], "22")
        self.assertEqual(combos[hands.index("AKs")], 4)
        self.assertEqual(combos[hands.index("AKo")], 12)

    def test_meta_is_present(self):
        meta = self.payload["meta"]
        self.assertEqual(meta["format"], "6-max cash, 100 big blinds")
        self.assertEqual(meta["charts"], 114)


if __name__ == "__main__":
    unittest.main()
