"""Build variants: the guide's own planner profiles, and what selecting
one changes.

    QT_QPA_PLATFORM=offscreen .venv/bin/python3 -m pytest tests/test_build_variants.py -v

A Maxroll guide's variants ARE its planner profiles (the guide links
``d4/planner/to4erl0e#3``, i.e. profile index 3), so the names asserted
here are the planner's own. Nothing invents a "Leveling" or "1-70"
label: if the planner does not have it, neither do we.

The image assertions need the Data API; the rest run offline.
"""

import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault(
    "D4COMPANION_IMAGE_CACHE",
    str(Path(__file__).resolve().parent / "_image_cache"),
)

from PySide6.QtWidgets import QApplication  # noqa: E402

from src import item_images  # noqa: E402
from src.api_config import items_api_base_url  # noqa: E402
from src.gear_planner import build_entries_from_verified_gear  # noqa: E402
from src.leveling_card import LevelingCard  # noqa: E402
from src.managers.leveling_manager import LevelingManager  # noqa: E402

_app = QApplication.instance() or QApplication([])

BUILDS = Path(__file__).resolve().parent.parent / "builds"
BLAZING = "Blazing Scream Warlock"
# Exactly what planner to4erl0e contains, in its own order.
PLANNER_VARIANTS = ["Starter", "Midgame", "Endgame", "Speedfarm"]

_needs_api = unittest.skipUnless(items_api_base_url(), "No Data API configured")


def _manager(build_name: str = BLAZING) -> LevelingManager:
    m = LevelingManager()
    assert m.set_current_build(build_name), build_name
    return m


def _gear_names(manager: LevelingManager) -> list[str]:
    vb = manager.get_verified_build() or {}
    return [g["item_name"] for g in vb.get("gear", [])]


class ImportedDataTests(unittest.TestCase):
    """3) and 4): what was imported, and where the names came from."""

    def setUp(self):
        self.build = json.loads((BUILDS / "blazing_scream_warlock.json").read_text(encoding="utf-8"))

    def test_all_planner_variants_were_imported(self):
        self.assertEqual([v["name"] for v in self.build["variants"]], PLANNER_VARIANTS)

    def test_each_variant_carries_its_own_verified_gear(self):
        for variant in self.build["variants"]:
            gear = variant["verified_build"]["gear"]
            self.assertGreaterEqual(len(gear), 10, variant["name"])
            for item in gear:
                self.assertTrue(item.get("slot"), variant["name"])
                self.assertTrue(item.get("item_name"), variant["name"])

    def test_variants_are_attributed_to_the_real_planner(self):
        for index, variant in enumerate(self.build["variants"]):
            self.assertEqual(variant["source"], "maxroll_planner")
            self.assertEqual(variant["source_url"],
                             f"https://maxroll.gg/d4/planner/to4erl0e#{index}")
            self.assertEqual(variant["planner_index"], index)

    def test_no_stage_or_level_label_is_invented(self):
        """The planner states level 70 for every profile and nothing
        else - so no variant may claim a range like "1-70", and none may
        claim a tier the data doesn't give."""

        for variant in self.build["variants"]:
            self.assertEqual(variant.get("level"), 70, variant["name"])
            self.assertNotIn("level_range", variant)
            self.assertNotIn("tier", variant)
            self.assertNotIn("stage", variant)

    def test_the_previous_verified_data_was_not_overwritten(self):
        """The build's own verified_build came from a different verified
        source; importing variants must not have destroyed it."""

        base = self.build["verified_build"]
        self.assertEqual(base["source"], "mobalytics_p4wnyhof_hub")
        self.assertEqual(len(base["gear"]), 10)

    def test_paragon_steps_are_recorded_as_data_not_as_variants(self):
        for variant in self.build["variants"]:
            self.assertTrue(variant["paragon_steps"], variant["name"])
        navne = {v["name"] for v in self.build["variants"]}
        self.assertNotIn("Paragon", navne)
        self.assertNotIn("Leveling", navne)


class ManagerTests(unittest.TestCase):
    """1), 2), 7): selecting, and not leaking state between builds."""

    def test_a_build_without_variants_still_loads(self):
        m = _manager("Blizzard Sorcerer")
        self.assertEqual(m.get_variants(), [])
        self.assertIsNotNone(m.get_verified_build())
        self.assertTrue(_gear_names(m))

    def test_a_build_with_variants_exposes_them_in_order(self):
        self.assertEqual([v["name"] for v in _manager().get_variants()], PLANNER_VARIANTS)

    def test_selecting_a_variant_changes_the_verified_build(self):
        m = _manager()
        base = _gear_names(m)
        self.assertTrue(m.set_current_variant("starter"))
        starter = _gear_names(m)
        self.assertNotEqual(base, starter)
        self.assertTrue(m.set_current_variant("endgame"))
        self.assertNotEqual(starter, _gear_names(m))

    def test_deselecting_returns_to_the_builds_own_data(self):
        m = _manager()
        base = _gear_names(m)
        m.set_current_variant("endgame")
        m.set_current_variant(None)
        self.assertEqual(_gear_names(m), base)

    def test_an_unknown_variant_is_refused_not_silently_ignored(self):
        m = _manager()
        m.set_current_variant("endgame")
        self.assertFalse(m.set_current_variant("speed_farming_1_70"))
        self.assertEqual(m.current_variant_id, "endgame", "A refused id must change nothing")

    def test_switching_build_clears_the_variant(self):
        m = _manager()
        m.set_current_variant("speedfarm")
        m.set_current_build("Blizzard Sorcerer")
        self.assertIsNone(m.current_variant_id)
        self.assertEqual(m.get_variants(), [])

    def test_no_gear_from_the_previous_build_survives(self):
        m = _manager()
        m.set_current_variant("endgame")
        blazing = set(_gear_names(m))
        m.set_current_build("Blizzard Sorcerer")
        sorcerer = set(_gear_names(m))
        self.assertTrue(sorcerer)
        self.assertNotIn("Infernal Homunculus", sorcerer)
        self.assertFalse(blazing & sorcerer & {"Infernal Homunculus", "Elegy"})


class SlotAndImageTests(unittest.TestCase):
    """5), 6), 9), 10): what Character and Gear Builder end up showing."""

    def test_character_and_gear_builder_follow_the_selected_variant(self):
        m = _manager()
        entries = {}
        for variant in ("starter", "endgame"):
            m.set_current_variant(variant)
            entries[variant] = build_entries_from_verified_gear(
                m.get_verified_build()["gear"], set())
        # Both pages build from this same list (see test_gear_images.py).
        self.assertNotEqual(
            [(e.slot_label, e.item_name) for e in entries["starter"]],
            [(e.slot_label, e.item_name) for e in entries["endgame"]],
        )

    def test_no_stale_slot_survives_a_variant_switch(self):
        m = _manager()
        m.set_current_variant("starter")
        starter = {e.item_name for e in build_entries_from_verified_gear(
            m.get_verified_build()["gear"], set()) if e.item_name}
        m.set_current_variant("endgame")
        endgame = {e.item_name for e in build_entries_from_verified_gear(
            m.get_verified_build()["gear"], set()) if e.item_name}
        kun_starter = starter - endgame
        self.assertTrue(kun_starter, "The two variants are identical - nothing to prove")
        self.assertFalse(kun_starter & endgame)

    @_needs_api
    def test_images_follow_the_variant_through_the_normal_pipeline(self):
        m = _manager()
        m.set_current_variant("endgame")
        fundet = []
        for item in m.get_verified_build()["gear"]:
            sti = item_images.fetch_image_for_item(item["item_name"])
            if sti:
                fundet.append(item["item_name"])
                self.assertEqual(
                    os.path.basename(sti),
                    item_images.image_filename_for_item(item["item_name"]),
                )
        self.assertIn("Elegy", fundet)
        self.assertIn("Temerity", fundet)

    @_needs_api
    def test_a_variant_whose_gear_has_no_artwork_stays_blank(self):
        """The Starter variant is all crafted/aspect gear - the catalogue
        has artwork for none of it, and that must show as nothing rather
        than another item's picture."""

        m = _manager()
        m.set_current_variant("starter")
        for entry in build_entries_from_verified_gear(m.get_verified_build()["gear"], set()):
            if entry.item_name and item_images.image_filename_for_item(entry.item_name) is None:
                self.assertIsNone(entry.item_image, entry.item_name)


class SelectorTests(unittest.TestCase):
    """The selector is generated from data, and hides itself otherwise."""

    def test_selector_lists_exactly_the_builds_own_variants(self):
        card = LevelingCard()
        card.set_variants(_manager().get_variants(), None)
        labels = [card.variant_combo.itemText(i) for i in range(card.variant_combo.count())]
        self.assertEqual(labels, [f"{n} (Lvl 70)" for n in PLANNER_VARIANTS])
        self.assertFalse(card.variant_row.isHidden())

    def test_selector_is_hidden_for_a_build_without_variants(self):
        card = LevelingCard()
        card.set_variants(_manager("Blizzard Sorcerer").get_variants(), None)
        self.assertTrue(card.variant_row.isHidden())
        self.assertEqual(card.variant_combo.count(), 0)

    def test_selector_emits_the_variant_id_from_the_data(self):
        card = LevelingCard()
        card.set_variants(_manager().get_variants(), None)
        set_ud = []
        card.variant_changed.connect(set_ud.append)
        card.variant_combo.setCurrentIndex(2)
        self.assertEqual(set_ud, ["endgame"])


if __name__ == "__main__":
    unittest.main()
