"""Integrity tests for the web payload in web/src/data/charts.json (specs S6, S7).

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


def load(path):
    if not path.exists():
        raise AssertionError(f"missing {path}; run the build scripts first")
    return json.loads(path.read_text(encoding="utf-8"))


def codes(spot):
    """The g string packs one base-36 pattern code per cell, CODE_WIDTH chars each."""
    g = spot["g"]
    return [g[i : i + CODE_WIDTH] for i in range(0, len(g), CODE_WIDTH)]


class WebPayloadTest(unittest.TestCase):
    def setUp(self):
        self.payload = load(WEB)
        self.source = load(SOURCE)
        self.spots = self.payload["spots"]
        self.by_id = {spot["id"]: spot for spot in self.spots}
        self.nav = self.payload["nav"]

    def nav_leaves(self):
        for hero, tree in self.nav.items():
            if tree["solo"]:
                yield tree["solo"], hero, ()
            for pair in tree["pairs"]:
                for situation in pair["situations"]:
                    yield situation, hero, (pair["rival"],)
            for triple in tree["triples"]:
                for situation in triple["situations"]:
                    yield situation, hero, (triple["opener"], triple["third"])

    def test_every_source_chart_exists_once(self):
        source_ids = {c["id"] for f in self.source["families"] for c in f["charts"]}
        web_ids = [spot["id"] for spot in self.spots]
        self.assertEqual(len(web_ids), len(set(web_ids)), "duplicate spot ids")
        self.assertEqual(set(web_ids), source_ids)
        self.assertEqual(len(web_ids), 114)

    def test_nav_is_a_bijection_over_the_spots(self):
        ids = [situation["id"] for situation, _, _ in self.nav_leaves()]
        self.assertEqual(len(ids), 114, "nav lost or duplicated spots")
        self.assertEqual(len(set(ids)), 114)
        self.assertEqual(set(ids), set(self.by_id))

    def test_nav_places_each_spot_under_its_own_hero_and_rivals(self):
        for situation, hero, rivals in self.nav_leaves():
            spot = self.by_id[situation["id"]]
            with self.subTest(spot=spot["id"]):
                self.assertEqual(spot["hero"].lower(), hero)
                self.assertEqual(
                    tuple(rival.upper() for rival in spot["rivals"]),
                    tuple(rival.upper() for rival in rivals),
                )

    def test_shape_matches_the_source_library(self):
        # 5 opens (the big blind never opens), 30 pairs, 20 triples
        solos = [t["solo"] for t in self.nav.values() if t["solo"]]
        self.assertEqual(len(solos), 5)
        self.assertIsNone(self.nav["bb"]["solo"])

        pairs = [(hero, pair) for hero, t in self.nav.items() for pair in t["pairs"]]
        self.assertEqual(len(pairs), 30)
        for hero, pair in pairs:
            self.assertIn(len(pair["situations"]), (2, 3), f"{hero}/{pair['rival']}")

        triples = [
            (hero, triple) for hero, t in self.nav.items() for triple in t["triples"]
        ]
        self.assertEqual(len(triples), 20)
        for _hero, triple in triples:
            labels = sorted(s["label"] for s in triple["situations"])
            self.assertEqual(labels, ["Cold 4-bet", "Squeeze"])

    def test_rivals_are_grouped_by_seat_order(self):
        order = {seat.lower(): index for index, seat in enumerate(SEATS)}
        for hero, tree in self.nav.items():
            rivals = [pair["rival"] for pair in tree["pairs"]]
            self.assertEqual(len(rivals), len(set(rivals)))
            self.assertEqual(len(rivals), 5, f"{hero} should face all five seats")
            for pair in tree["pairs"]:
                expected = "before" if order[pair["rival"]] < order[hero] else "after"
                self.assertEqual(pair["side"], expected, f"{hero}/{pair['rival']}")

    def test_two_rival_spots_need_two_earlier_seats(self):
        order = {seat.lower(): index for index, seat in enumerate(SEATS)}
        for hero, tree in self.nav.items():
            earlier = sum(1 for seat in order if order[seat] < order[hero])
            expected = earlier * (earlier - 1) // 2
            self.assertEqual(
                len(tree["triples"]), expected, f"{hero} has {earlier} earlier seats"
            )
            for triple in tree["triples"]:
                self.assertLess(order[triple["opener"]], order[triple["third"]])
                self.assertLess(order[triple["third"]], order[hero])

    def test_situations_read_as_the_action_facing_you(self):
        for situation, _hero, _rivals in self.nav_leaves():
            with self.subTest(spot=situation["id"]):
                self.assertTrue(situation["label"])
                self.assertTrue(situation["sub"])

    def test_every_chart_has_169_valid_pattern_indexes(self):
        patterns = self.payload["patterns"]
        for spot in self.spots:
            with self.subTest(spot=spot["id"]):
                packed = codes(spot)
                self.assertEqual(len(packed), CELLS)
                for code in packed:
                    self.assertLess(int(code, 36), len(patterns), f"bad index {code}")

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
            legend = {entry["color"] for entry in spot["legend"]}
            with self.subTest(spot=spot["id"]):
                self.assertTrue(legend)
                for code in codes(spot):
                    for seg in patterns[int(code, 36)]:
                        if seg["color"] == OUT_OF_RANGE:
                            continue
                        self.assertIn(seg["color"], legend)

    def test_hands_and_combo_weights_are_shared(self):
        hands, combos = self.payload["hands"], self.payload["combos"]
        self.assertEqual(len(hands), CELLS)
        self.assertEqual(len(set(hands)), CELLS)
        self.assertEqual(sum(combos), 1326)
        self.assertEqual(hands[0], "AA")
        self.assertEqual(hands[-1], "22")
        self.assertEqual(combos[hands.index("AKs")], 4)
        self.assertEqual(combos[hands.index("AKo")], 12)

    def test_steps_explain_the_hand_and_name_the_hero(self):
        for spot in self.spots:
            with self.subTest(spot=spot["id"]):
                self.assertTrue(spot["steps"])
                acted = list(
                    dict.fromkeys(
                        step["seat"] for step in spot["steps"] if step["seat"] != "you"
                    )
                )
                self.assertEqual(acted, spot["rivals"])
                joined = " ".join(spot["history"]).lower()
                self.assertTrue("you" in joined, spot["history"])
                self.assertTrue(spot["decision"])
                self.assertTrue(spot["stat"])

    def test_history_states_a_size_where_one_exists(self):
        sized = [s for s in self.spots if any("bb" in line for line in s["history"])]
        self.assertGreater(len(sized), 100)

    def test_meta_is_present(self):
        meta = self.payload["meta"]
        self.assertEqual(meta["format"], "6-max cash, 100 big blinds")
        self.assertEqual(meta["charts"], 114)


if __name__ == "__main__":
    unittest.main()
