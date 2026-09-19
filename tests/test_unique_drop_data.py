"""Data-integrity tests for the Unique Drop Locations feature.

Run with: .venv/bin/python3 -m pytest tests/test_unique_drop_data.py -v
(or plain -m unittest - no Qt/QApplication needed, this only touches
src/unique_data.py, src/boss_data.py and src/unique_drop_service.py,
none of which import Qt)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import unique_drop_service as service
from src.boss_data import BOSSES
from src.unique_data import UNIQUES

_VALID_TYPES = {"Unique", "Mythic Unique"}


class UniqueDropDataTests(unittest.TestCase):
    def test_no_duplicate_unique_ids(self):
        ids = [u["id"] for u in UNIQUES]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate Unique ids found")

    def test_no_duplicate_boss_ids(self):
        ids = [b["id"] for b in BOSSES]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate Boss ids found")

    def test_no_empty_unique_names(self):
        for unique in UNIQUES:
            self.assertTrue(unique["name"].strip(), f"Empty name for id={unique['id']}")

    def test_no_empty_boss_names(self):
        for boss in BOSSES:
            self.assertTrue(boss["name"].strip(), f"Empty name for id={boss['id']}")

    def test_all_boss_references_exist(self):
        boss_ids = {b["id"] for b in BOSSES}
        for unique in UNIQUES:
            for bid in unique["target_bosses"]:
                self.assertIn(
                    bid, boss_ids, f"Unique '{unique['name']}' references unknown boss id '{bid}'"
                )

    def test_no_duplicate_boss_relations_per_unique(self):
        for unique in UNIQUES:
            targets = unique["target_bosses"]
            self.assertEqual(
                len(targets), len(set(targets)), f"Duplicate boss refs on '{unique['name']}'"
            )

    def test_all_types_valid(self):
        for unique in UNIQUES:
            self.assertIn(unique["type"], _VALID_TYPES, f"Invalid type on '{unique['name']}'")

    def test_no_empty_class_or_slot_strings(self):
        # Fields may honestly be "DATA UNAVAILABLE" but never blank.
        for unique in UNIQUES:
            self.assertTrue(unique["class"].strip())
            self.assertTrue(unique["slot"].strip())

    def test_image_paths_exist_if_set(self):
        for unique in UNIQUES:
            image = unique.get("image")
            if image is not None:
                self.assertTrue(Path(image).exists(), f"Missing image file: {image}")

    def test_validate_data_helper_matches(self):
        # The service-layer validator used by the app itself should
        # agree there are no problems (same checks, single source of truth).
        self.assertEqual(service.validate_data(), [])

    def test_get_uniques_for_boss_and_get_bosses_for_unique_are_consistent(self):
        for unique in UNIQUES:
            for boss in service.get_bosses_for_unique(unique["id"]):
                uniques_for_that_boss = service.get_uniques_for_boss(boss["id"])
                self.assertIn(
                    unique["id"],
                    [u["id"] for u in uniques_for_that_boss],
                    f"'{unique['name']}' -> '{boss['name']}' relation isn't reflected the other way",
                )

    def test_search_items_never_crashes_on_blank_query(self):
        self.assertEqual(len(service.search_items("")), len(UNIQUES))
        self.assertEqual(len(service.search_items("   ")), len(UNIQUES))

    def test_search_items_case_insensitive_partial_match(self):
        results = service.search_items("elegy")
        self.assertTrue(any(u["name"] == "Elegy" for u in results))


if __name__ == "__main__":
    unittest.main()
