"""Does the Unique Drop Locations page still build - now that its data
comes from the API instead of a list inside the application?

    QT_QPA_PLATFORM=offscreen .venv/bin/python3 -m pytest tests/test_ui_smoke.py -v

Config-only checks can't answer that: the page is where the adapted
records meet the widgets that read them, and a missing field there
shows up as a crash or an empty list, not as a failing assertion
somewhere else. Runs offscreen, so it needs no display.
"""

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
    raise unittest.SkipTest(
        "No Data API configured - set D4COMPANION_API_URL or api_url.txt "
        "to run the UI tests (see src/api_config.py)."
    )

from PySide6.QtWidgets import QApplication  # noqa: E402

from src import unique_drop_service as service  # noqa: E402
from src.items_api import ItemsAPI  # noqa: E402
from src.unique_drops_interface import UniqueDropsCard, UniqueDropsInterface  # noqa: E402

_app = QApplication.instance() or QApplication([])


class UniqueDropsPageTests(unittest.TestCase):
    def setUp(self):
        service._api = ItemsAPI()
        service.refresh()

    def test_page_builds_with_api_data(self):
        card = UniqueDropsCard()
        self.assertGreater(len(card._cards), 200, "The page built almost no result cards")
        self.assertEqual(len(card._cards), len(service.all_uniques()))

    def test_interface_wrapper_builds(self):
        page = UniqueDropsInterface(UniqueDropsCard())
        self.assertIsNotNone(page)

    def test_filters_are_populated_from_api_data(self):
        card = UniqueDropsCard()
        classes = [card.class_combo.itemText(i) for i in range(card.class_combo.count())]
        slots = [card.slot_combo.itemText(i) for i in range(card.slot_combo.count())]
        self.assertIn("All Classes", classes)
        self.assertIn("Helm", slots)   # derived from the server's own type string
        self.assertIn("Ring", slots)

    def test_detail_panel_shows_a_real_description_from_the_dataset(self):
        card = UniqueDropsCard()
        crest = service.find_unique("Harlequin Crest")
        card._show_detail(crest["id"])
        text = card.detail_label.text()
        self.assertIn("Harlequin Crest", text)
        self.assertIn(crest["description"][:20], text)

    def test_a_card_actually_contains_its_content(self):
        """Counting cards is not enough: an edit that pushed the label
        code into another method still produced 242 empty cards and
        passed every count-based check. This looks inside one."""

        from PySide6.QtWidgets import QLabel

        card = UniqueDropsCard()
        crest = next(c for c in card._cards if c._unique_id == "harlequin_crest")

        texts = [w.text() for w in card.findChildren(QLabel) if hasattr(w, "text")]
        self.assertTrue(any("Harlequin Crest" == t for t in texts), "No name label on the card")
        self.assertTrue(
            any("Mythic Unique" in t and "Helm" in t for t in texts),
            "No type/class/slot line on the card",
        )
        # The image box is laid out, not orphaned.
        self.assertIsNotNone(crest.image_box.parent())
        self.assertGreater(crest._image_layout.count(), 0)

    def test_ui_marks_an_item_the_dataset_does_not_have(self):
        from PySide6.QtWidgets import QLabel

        card = UniqueDropsCard()
        local = next(u for u in service.all_uniques() if not u["from_api"])

        texts = [w.text() for w in card.findChildren(QLabel) if hasattr(w, "text")]
        self.assertTrue(
            any(local["name"] == t for t in texts),
            "The locally-mapped item disappeared from the page",
        )
        self.assertTrue(
            any("not in dataset" in t for t in texts),
            "Nothing on the card says this item isn't from the verified dataset",
        )

        card._show_detail(local["id"])
        self.assertIn("NOT in the verified dataset", card.detail_label.text())

        # ...and a real API item is labelled as such.
        card._show_detail(service.find_unique("Harlequin Crest")["id"])
        self.assertIn("Data API (verified dataset)", card.detail_label.text())

    def test_search_narrows_the_list(self):
        card = UniqueDropsCard()
        card.search_input.setText("Harlequin")
        self.assertTrue(card._cards)
        self.assertLess(len(card._cards), 10)

    def test_data_unavailable_state_when_the_api_is_down(self):
        """No server, no data, no invented fallback - and the page says
        so rather than showing an empty list."""

        service._api = ItemsAPI(base_url="http://127.0.0.1:1/api/v1", timeout=2)
        service.refresh()

        self.assertFalse(service.data_available())
        card = UniqueDropsCard()
        self.assertEqual(card._cards, [])
        self.assertIn("DATA UNAVAILABLE", card.detail_label.text())
        # It must name the server it failed to reach, not just complain.
        self.assertIn("127.0.0.1:1", card.detail_label.text())


if __name__ == "__main__":
    unittest.main()
