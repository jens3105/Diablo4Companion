"""Gear artwork: build data -> item identity -> image -> slot.

    QT_QPA_PLATFORM=offscreen .venv/bin/python3 -m pytest tests/test_gear_images.py -v

The rule these tests exist to hold: a picture is found by the item's
NAME through the server's catalogue, never by a per-build image path.
That is what makes a new build show its gear illustrated without anyone
adding a mapping - and it is also why an aspect, which has no artwork in
the dataset, must show nothing rather than some other item's picture.

Needs the Data API (see src/api_config.py); skips without it.
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

from src.api_config import items_api_base_url  # noqa: E402

if not items_api_base_url():
    raise unittest.SkipTest("No Data API configured (see src/api_config.py)")

from PySide6.QtWidgets import QApplication, QHBoxLayout, QWidget  # noqa: E402

from src import item_images  # noqa: E402
from src.gear_builder_interface import GearSlotCard  # noqa: E402
from src.gear_planner import (  # noqa: E402
    SlotStatus,
    build_entries_from_verified_gear,
    SlotChip,
)

_app = QApplication.instance() or QApplication([])

BUILDS = Path(__file__).resolve().parent.parent / "builds"


def _gear(navn: str) -> list[dict]:
    data = json.loads((BUILDS / f"{navn}.json").read_text(encoding="utf-8"))
    return (data.get("verified_build") or {}).get("gear", [])


def _entries(navn: str):
    return build_entries_from_verified_gear(_gear(navn), set())


class ItemImageLookupTests(unittest.TestCase):
    def setUp(self):
        item_images.reset_index()

    def test_a_catalogue_item_resolves_to_its_own_artwork(self):
        self.assertEqual(item_images.image_filename_for_item("Harlequin Crest"),
                         "Harlequin-Crest-1089568.png")
        # Name matching is normalized, not literal.
        self.assertEqual(item_images.image_filename_for_item("harlequin crest"),
                         "Harlequin-Crest-1089568.png")

    def test_an_aspect_has_no_artwork_and_says_so(self):
        for navn in ("Aspect of Ignition", "Embattled Aspect",
                     "Aspect of Diabolical Armor"):
            self.assertIsNone(item_images.image_filename_for_item(navn), navn)

    def test_an_unknown_name_never_borrows_another_items_picture(self):
        self.assertIsNone(item_images.image_filename_for_item("Not A Real Item 12345"))
        self.assertIsNone(item_images.image_filename_for_item(""))

    def test_fetching_puts_the_real_file_in_the_cache(self):
        path = item_images.fetch_image_for_item("Elegy")
        self.assertIsNotNone(path)
        self.assertTrue(os.path.isfile(path))
        with open(path, "rb") as f:
            self.assertEqual(f.read(4), b"\x89PNG")


class BuildToSlotTests(unittest.TestCase):
    """Build data -> the right item in the right slot, for both pages."""

    def test_blazing_scream_slots_and_items(self):
        forventet = {
            "Helm": "Harlequin Crest",
            "Chest": "Aspect of Diabolical Armor",
            "Gloves": "Aspect of Ignition",
            "Pants": "Temerity",
            "Boots": "Embattled Aspect",
            "Amulet": "Moloch's Beating Flame",
            "Ring 1": "The Eightfold Idol",
            "Ring 2": "Aspect of Scorching Heat",
        }
        faktisk = {e.slot_label: e.item_name for e in _entries("blazing_scream_warlock")}
        for slot, item in forventet.items():
            self.assertEqual(faktisk.get(slot), item, slot)
        # The two-handed/offhand slots keep the build's own wording.
        self.assertIn("Elegy", faktisk.values())
        self.assertIn("Infernal Homunculus", faktisk.values())

    def test_items_in_the_catalogue_get_a_picture_the_rest_stay_blank(self):
        med, uden = [], []
        for e in _entries("blazing_scream_warlock"):
            if e.item_name is None:
                continue
            (med if item_images.fetch_image_for_item(e.item_name) else uden).append(e.item_name)
        self.assertIn("Harlequin Crest", med)
        self.assertIn("Temerity", med)
        self.assertIn("Aspect of Ignition", uden)
        self.assertEqual(len(med), 6, f"expected six illustrated items, got {med}")

    def test_character_and_gear_builder_use_the_same_entries(self):
        """One canonical gear source - the two pages build their widgets
        from the identical SlotEntry list."""

        entries = _entries("blazing_scream_warlock")
        chip = SlotChip(entries[0])
        card = GearSlotCard(entries[0])
        self.assertEqual(chip.entry.item_name, card.entry.item_name)
        self.assertEqual(chip.entry.slot_label, card.entry.slot_label)
        self.assertIs(chip.entry, card.entry)

    def test_a_chip_shows_the_picture_once_it_is_cached(self):
        item_images.fetch_image_for_item("Harlequin Crest")
        entry = next(e for e in _entries("blazing_scream_warlock")
                     if e.item_name == "Harlequin Crest")
        self.assertIsNotNone(entry.item_image, "A cached image must reach the entry")
        chip = SlotChip(entry)
        self.assertFalse(chip.image_label.pixmap().isNull())

    def test_a_slot_without_artwork_shows_no_image_at_all(self):
        entry = next(e for e in _entries("blazing_scream_warlock")
                     if e.item_name == "Aspect of Ignition")
        self.assertIsNone(entry.item_image)
        chip = SlotChip(entry)
        self.assertTrue(chip.image_label.pixmap().isNull())
        # ...and the slot still says what the build requires.
        self.assertIn("Aspect of Ignition", chip.name_label.text())


class ChipLayoutTests(unittest.TestCase):
    """The first version of this drew the item name on top of its own
    artwork: the chip has a fixed height computed from its rows, and the
    image row was left out of that sum. Only a rendered picture showed
    it, so the geometry is asserted here."""

    def _chip(self, item_name: str) -> SlotChip:
        item_images.fetch_image_for_item(item_name)
        entry = next(e for e in _entries("blazing_scream_warlock")
                     if e.item_name == item_name)
        host = QWidget()
        layout = QHBoxLayout(host)
        chip = SlotChip(entry)
        layout.addWidget(chip)
        host.resize(400, 300)
        host.show()
        _app.processEvents()
        self.addCleanup(host.deleteLater)
        return chip

    def test_the_image_never_overlaps_the_text(self):
        chip = self._chip("Harlequin Crest")
        self.assertFalse(chip.image_label.isHidden())
        self.assertLessEqual(
            chip.image_label.geometry().bottom(),
            chip.slot_label.geometry().top(),
            "The artwork overlaps the slot label",
        )
        self.assertLessEqual(
            chip.slot_label.geometry().bottom(),
            chip.name_label.geometry().top(),
            "The slot label overlaps the item name",
        )

    def test_everything_fits_inside_the_chip(self):
        chip = self._chip("Harlequin Crest")
        self.assertLessEqual(chip.name_label.geometry().bottom(), chip.height(),
                             "The item name is cut off at the chip's bottom edge")

    def test_a_chip_with_artwork_is_taller_than_one_without(self):
        med = self._chip("Harlequin Crest")
        uden = self._chip("Aspect of Ignition")
        self.assertGreater(med.height(), uden.height())


class SwitchingBuildTests(unittest.TestCase):
    """Nothing from the previous build may survive the switch."""

    def test_switching_build_replaces_every_slot(self):
        bs = {e.item_name for e in _entries("blazing_scream_warlock") if e.item_name}
        andet = {e.item_name for e in _entries("blizzard_sorcerer") if e.item_name}
        self.assertTrue(andet, "The second build has no gear to compare against")
        self.assertNotEqual(bs, andet)
        # Blazing Scream's signature items must be gone.
        self.assertNotIn("Infernal Homunculus", andet)
        self.assertNotIn("Moloch's Beating Flame", andet)

    def test_images_follow_the_build_not_the_page(self):
        for navn in ("blazing_scream_warlock", "blizzard_sorcerer"):
            for e in _entries(navn):
                if e.item_image is None:
                    continue
                forventet = item_images.image_filename_for_item(e.item_name)
                self.assertEqual(os.path.basename(e.item_image), forventet,
                                 f"{navn}: {e.item_name} showed the wrong picture")

    def test_every_build_in_the_repo_maps_cleanly(self):
        """All 27 builds go through the same path - no build may crash
        it, and no item may end up with another item's artwork."""

        for fil in sorted(BUILDS.glob("*.json")):
            if fil.name == "manifest.json":
                continue
            gear = (json.loads(fil.read_text(encoding="utf-8")).get("verified_build") or {}).get("gear", [])
            for entry in build_entries_from_verified_gear(gear, set()):
                if entry.item_name is None:
                    self.assertEqual(entry.status, SlotStatus.OPTIONAL, fil.name)
                    continue
                filnavn = item_images.image_filename_for_item(entry.item_name)
                if entry.item_image is not None:
                    self.assertEqual(os.path.basename(entry.item_image), filnavn, fil.name)


if __name__ == "__main__":
    unittest.main()
