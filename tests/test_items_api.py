"""Integration tests for the Diablo4Companion Data API - run against
the real production server, through the application's own data layer.

    .venv/bin/python3 -m pytest tests/test_items_api.py -v

These deliberately do **not** mock the API. The question they exist to
answer is "does this application actually read the verified dataset
from the production server?", and a mock cannot answer that - it can
only prove the app agrees with itself. Every assertion about counts and
hashes is checked against what the server reports, and against the
dataset's own sha256, so a silently swapped dataset fails the suite.

The server address is **configuration, not code** (see
src/api_config.py - this repo is public and the API is on a private
LAN). Point the tests at it with:

    D4COMPANION_API_URL=http://<server>:<port>/api/v1 \\
        .venv/bin/python3 -m pytest tests/ -q

or put the same line in ``api_url.txt`` at the repo root. Without it
these tests **skip** rather than fail: an unconfigured checkout hasn't
broken anything, it just can't reach a server.
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Keep the tests' image downloads out of the user's real cache.
os.environ.setdefault(
    "D4COMPANION_IMAGE_CACHE",
    str(Path(__file__).resolve().parent / "_image_cache"),
)

from src import item_images, unique_drop_service as service  # noqa: E402
from src import api_config  # noqa: E402
from src.api_config import configured_source, items_api_base_url  # noqa: E402
from src.items_api import ItemsAPI  # noqa: E402

EXPECTED_ITEMS = 453
EXPECTED_CATEGORIES = {"charms": 222, "mythics": 16, "uniques": 215}
EXPECTED_SHA256 = "79aacf51f387b491c69d073d82dbdf7417acffb88363ade6d1f645002aad0a4c"

CONFIGURED_URL = items_api_base_url()

if not CONFIGURED_URL:
    raise unittest.SkipTest(
        "No Data API configured - set D4COMPANION_API_URL or api_url.txt "
        "to run the integration tests (see src/api_config.py)."
    )


class ApiConfigTests(unittest.TestCase):
    """The app must use the address it was *configured* with - and must
    contain no address of its own, so it can never quietly talk to the
    wrong server (the development machine, say)."""

    def test_source_contains_no_hardcoded_address(self):
        import re

        with open(Path(api_config.__file__), encoding="utf-8") as f:
            source = f.read()
        # A real address starts with a host character; the docstring's
        # placeholder "http://<server>:<port>" deliberately does not.
        found = re.findall(r"https?://[A-Za-z0-9]\S*", source)
        self.assertEqual(found, [], f"An endpoint is baked into the source: {found}")

    def test_url_comes_from_configuration(self):
        self.assertIn(configured_source(), ("environment", "settings", "api_url.txt"))
        self.assertTrue(CONFIGURED_URL.endswith("/api/v1"), CONFIGURED_URL)

    def test_service_layer_uses_the_configured_url(self):
        # The layer the UI actually calls - not just the constant.
        self.assertEqual(service.api_base_url(), CONFIGURED_URL)

    def test_unconfigured_client_fails_loudly_instead_of_guessing(self):
        blank = ItemsAPI(base_url="")
        self.assertFalse(blank.configured)
        self.assertIsNone(blank.health())
        self.assertEqual(blank.items(), [])
        self.assertIsNone(blank.image_url("x.png"))
        self.assertIn("No Data API address is configured", blank.last_error)


class ApiClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = ItemsAPI()

    # 1) health
    def test_health(self):
        health = self.api.health()
        self.assertIsNotNone(health, f"No response from {self.api.base_url}")
        self.assertEqual(health["status"], "ok")
        self.assertEqual(health["item_count"], EXPECTED_ITEMS)
        self.assertEqual(health["image_count"], EXPECTED_ITEMS)

    # 2) version
    def test_version(self):
        version = self.api.version()
        self.assertIsNotNone(version)
        self.assertEqual(version["api_version"], "1.0.0")
        self.assertEqual(version["dataset_version"], "1.0.0")
        self.assertEqual(version["source"], "PureDiablo")
        self.assertEqual(version["status"], "verified")

    # 3+4) loading all items, and the expected count
    def test_all_items_loaded(self):
        items = self.api.items()
        self.assertEqual(len(items), EXPECTED_ITEMS)
        self.assertTrue(all(i.get("name") for i in items))

    # 5) categories
    def test_categories_match_dataset(self):
        counts = {c["category"]: c["item_count"] for c in self.api.categories()}
        self.assertEqual(counts, EXPECTED_CATEGORIES)
        self.assertEqual(sum(counts.values()), EXPECTED_ITEMS)

    def test_category_endpoint_returns_that_category_only(self):
        mythics = self.api.category("mythics")
        self.assertEqual(len(mythics), EXPECTED_CATEGORIES["mythics"])
        self.assertTrue(all(i["category"] == "mythics" for i in mythics))

    # 6) search
    def test_search_harlequin_crest(self):
        hits = self.api.search("Harlequin")
        self.assertTrue(hits, "Search returned nothing for 'Harlequin'")
        self.assertIn("Harlequin Crest", [h["name"] for h in hits])

    # 7) single item lookup
    def test_single_item_lookup(self):
        item = self.api.item("Harlequin Crest")
        self.assertIsNotNone(item)
        self.assertEqual(item["name"], "Harlequin Crest")
        self.assertEqual(item["category"], "mythics")
        self.assertTrue(item["description"].strip())

    def test_unknown_item_is_none_not_invented(self):
        self.assertIsNone(self.api.item("Definitely Not A Real Item 12345"))

    # 8) image URL generation
    def test_image_url_generation(self):
        url = self.api.image_url("images/mythics/Harlequin-Crest-1089568.png")
        self.assertEqual(url, f"{CONFIGURED_URL}/images/Harlequin-Crest-1089568.png")
        self.assertIsNone(self.api.image_url(""))

    def test_image_downloads_and_caches(self):
        data = self.api.image_bytes("Harlequin-Crest-1089568.png")
        self.assertIsNotNone(data)
        self.assertGreater(len(data), 0)
        self.assertEqual(data[:4], b"\x89PNG")

        path = item_images.fetch("images/mythics/Harlequin-Crest-1089568.png")
        self.assertIsNotNone(path)
        self.assertTrue(os.path.isfile(path))
        # The cache is a copy, never a second source of truth.
        with open(path, "rb") as f:
            self.assertEqual(f.read(), data)

    # 9) API unavailable
    def test_api_unavailable_returns_nothing_and_says_why(self):
        dead = ItemsAPI(base_url="http://127.0.0.1:1/api/v1", timeout=2)
        self.assertIsNone(dead.health())
        self.assertEqual(dead.items(), [])
        self.assertEqual(dead.categories(), [])
        self.assertIsNotNone(dead.last_error, "A failure must record why")

    # 10) missing image
    def test_missing_image_returns_none(self):
        self.assertIsNone(self.api.image_bytes("does-not-exist-12345.png"))
        self.assertIsNone(item_images.fetch("does-not-exist-12345.png"))

    # 13) the dataset really is the verified one
    def test_dataset_sha256_matches_verified_dataset(self):
        self.assertEqual(self.api.version()["sha256"], EXPECTED_SHA256)


class UniqueDropServiceTests(unittest.TestCase):
    """The page's own data layer - this is what the UI calls."""

    @classmethod
    def setUpClass(cls):
        service.refresh()
        cls.uniques = service.all_uniques()

    def test_catalogue_comes_from_the_api(self):
        self.assertTrue(service.data_available())
        self.assertIsNone(service.data_error())
        info = service.dataset_info()
        self.assertIsNotNone(info)
        self.assertEqual(info["sha256"], EXPECTED_SHA256)
        self.assertEqual(info["dataset_version"], "1.0.0")

    def test_uniques_and_mythics_are_all_present(self):
        from_api = [u for u in self.uniques if u["category"] in ("uniques", "mythics")]
        self.assertEqual(
            len(from_api),
            EXPECTED_CATEGORIES["uniques"] + EXPECTED_CATEGORIES["mythics"],
        )

    def test_no_charms_on_the_uniques_page(self):
        self.assertNotIn("charms", {u["category"] for u in self.uniques})

    def test_records_have_the_shape_the_ui_reads(self):
        for unique in self.uniques:
            for field in ("id", "name", "type", "class", "slot", "target_bosses"):
                self.assertIn(field, unique, f"{unique.get('name')} is missing '{field}'")
            self.assertIn(unique["type"], ("Unique", "Mythic Unique"))
            self.assertTrue(unique["class"].strip())
            self.assertTrue(unique["slot"].strip())

    def test_slot_is_derived_from_the_servers_own_type_string(self):
        crest = service.find_unique("Harlequin Crest")
        self.assertIsNotNone(crest)
        self.assertEqual(crest["type"], "Mythic Unique")
        self.assertEqual(crest["slot"], "Helm")
        self.assertEqual(crest["api"]["type"], "Mythic Unique Helm")

    def test_descriptions_come_from_the_dataset(self):
        crest = service.find_unique("Harlequin Crest")
        self.assertTrue(crest["description"])
        self.assertEqual(crest["description"], crest["api"]["description"].strip())

    def test_boss_relationship_survived_the_move_to_the_api(self):
        # The API has no boss data - this mapping is the app's own, and
        # losing it would quietly gut the whole page.
        with_boss = [u for u in self.uniques if u["target_bosses"]]
        self.assertTrue(with_boss, "No Unique has a target boss any more")
        for unique in with_boss:
            self.assertTrue(service.get_bosses_for_unique(unique["id"]))

    def test_locally_known_uniques_are_not_lost(self):
        # The dataset doesn't list every Unique this project has boss
        # data for; those entries must still appear.
        names = {u["name"] for u in self.uniques}
        self.assertIn("Windforce", names)

    def test_search_finds_harlequin_crest(self):
        hits = service.search_items("harlequin")
        self.assertIn("Harlequin Crest", [h["name"] for h in hits])

    def test_image_filename_is_a_plain_basename(self):
        crest = service.find_unique("Harlequin Crest")
        self.assertEqual(crest["image_filename"], "Harlequin-Crest-1089568.png")

    def test_no_duplicate_entries_after_merging(self):
        ids = [u["id"] for u in self.uniques]
        names = [u["name"].lower() for u in self.uniques]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate ids in the merged catalogue")
        self.assertEqual(len(names), len(set(names)), "The same item appears twice")

    def test_item_known_under_an_older_local_id_is_not_duplicated(self):
        # "The Eightfold Idol" sits in the local boss table under the id
        # "eightfold_idol"; before the name-based match it appeared
        # twice - once from the API without a boss, once from the table.
        matches = [u for u in self.uniques if u["name"] == "The Eightfold Idol"]
        self.assertEqual(len(matches), 1)
        entry = matches[0]
        self.assertEqual(entry["id"], "eightfold_idol")
        self.assertEqual(entry["category"], "uniques")   # came from the API
        self.assertTrue(entry["target_bosses"])          # kept its boss

    def test_harlequin_crest_comes_from_the_api(self):
        crest = service.find_unique("Harlequin Crest")
        self.assertTrue(crest["from_api"])
        self.assertIsNotNone(crest["api"])
        self.assertEqual(crest["api"]["name"], "Harlequin Crest")
        self.assertIn("verified", crest["source"])
        # The displayed facts are the dataset's own, not a local copy.
        self.assertEqual(crest["description"], crest["api"]["description"].strip())
        self.assertEqual(crest["class"], crest["api"]["class"])

    def test_every_api_sourced_record_really_has_an_api_record(self):
        for unique in self.uniques:
            if unique["from_api"]:
                self.assertIsNotNone(unique["api"], unique["name"])
                self.assertEqual(unique["api"]["name"], unique["name"])

    def test_item_without_an_api_record_is_not_presented_as_api_data(self):
        """The 11 entries the dataset doesn't list are kept for their
        boss mapping only - they must never pass for verified data."""

        local = [u for u in self.uniques if not u["from_api"]]
        self.assertTrue(local, "Expected some local-only entries")
        for unique in local:
            self.assertIsNone(unique["api"])
            self.assertEqual(unique["category"], "local")
            self.assertIn("NOT in the verified dataset", unique["source"])
            self.assertNotIn("Data API", unique["source"])
            # No API fields may be faked in either: no description and
            # no image filename, rather than an invented one.
            self.assertIsNone(unique.get("description"))
            self.assertIsNone(unique.get("image_filename"))
            # Kept only because they carry the mapping.
            self.assertTrue(unique["target_bosses"], f"{unique['name']} maps to no boss")

    def test_removing_local_entries_would_empty_two_bosses(self):
        """Why they are kept at all - stated as a test so a future
        cleanup sees the consequence before deleting them."""

        local_ids = {u["id"] for u in self.uniques if not u["from_api"]}
        emptied = []
        for boss in service.all_bosses():
            items = service.get_uniques_for_boss(boss["id"])
            if items and all(u["id"] in local_ids for u in items):
                emptied.append(boss["name"])
        self.assertEqual(len(emptied), 2, f"Expected 2 bosses to depend on them, got {emptied}")

    def test_no_hardcoded_item_catalogue_in_the_production_path(self):
        # src/unique_data.py is now only the boss-mapping table: far
        # smaller than the catalogue, and nothing may be served from it
        # as an item list.
        from src.unique_data import UNIQUES

        self.assertLess(len(UNIQUES), len(self.uniques))
        self.assertGreater(len(self.uniques), 200)


if __name__ == "__main__":
    unittest.main()
