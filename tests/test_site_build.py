"""Smoke tests for the built Astro page (specs S1, S2).

Verifies the static build is self-contained and ships the same 114 spots as the
source data. Run `pnpm build` in web/ first.
"""

import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "web" / "dist" / "index.html"
WEB_DATA = ROOT / "web" / "src" / "data" / "charts.json"
PAYLOAD = re.compile(
    r'<script type="application/json" id="payload"[^>]*>(.*?)</script>', re.S
)


class SiteBuildTest(unittest.TestCase):
    def setUp(self):
        if not DIST.exists():
            raise AssertionError(f"missing {DIST}; run `pnpm build` inside web/")
        self.html = DIST.read_text(encoding="utf-8")

    def test_page_is_one_self_contained_file(self):
        self.assertLess(len(self.html.encode()), 400_000, "page got too heavy")
        self.assertNotRegex(self.html, r"<script[^>]+src=", "no external scripts")
        self.assertNotRegex(self.html, r'<link[^>]+rel="stylesheet"', "no external css")
        self.assertIn("function boot()", self.html, "client script is not inlined")

    def test_payload_matches_the_web_data(self):
        match = PAYLOAD.search(self.html)
        self.assertIsNotNone(match, "payload script tag missing")
        built = json.loads(match.group(1))
        source = json.loads(WEB_DATA.read_text(encoding="utf-8"))
        built_ids = {s["id"] for h in built["heroes"] for s in h["spots"]}
        source_ids = {s["id"] for h in source["heroes"] for s in h["spots"]}
        self.assertEqual(built_ids, source_ids)
        self.assertEqual(len(built_ids), 114)

    def test_seat_buttons_are_rendered_server_side(self):
        heroes = re.findall(r'data-hero="([a-z]+)"', self.html)
        self.assertEqual(heroes, ["utg", "hj", "co", "btn", "sb", "bb"])

    def test_markup_hooks_the_client_needs_exist(self):
        for hook in ('id="grid"', 'id="spots"', 'id="history"', 'id="legend"', 'id="copy"'):
            with self.subTest(hook=hook):
                self.assertIn(hook, self.html)


if __name__ == "__main__":
    unittest.main()
