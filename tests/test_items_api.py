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
DROP_DATASET_VERSION = "1.3.0"

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

    def test_the_app_holds_no_item_or_drop_data_of_its_own(self):
        """The whole point of this phase: every item on the page came
        from the server, and src/unique_data.py no longer exists."""

        import importlib
        from pathlib import Path

        with self.assertRaises(ImportError):
            importlib.import_module("src.unique_data")
        self.assertFalse(
            (Path(__file__).resolve().parent.parent / "src" / "unique_data.py").exists()
        )
        for unique in self.uniques:
            self.assertTrue(unique["from_api"], f"{unique['name']} did not come from the server")

    def test_mapping_coverage_is_what_we_think_it_is(self):
        """Coverage after the Season 15 research: 151 target bosses and
        26 shared-pool records from the server, 11 more from this
        project's own mapping, and the rest honestly unknown."""

        import collections

        fordeling = collections.Counter(u.get("drop_type") for u in self.uniques)
        # 151 verified + 1 single-source + 11 legacy fallback
        self.assertEqual(fordeling["target_boss"], 163)
        self.assertEqual(fordeling["mythic_pool"], 13)
        self.assertEqual(fordeling["general_pool"], 15)
        self.assertEqual(fordeling[None], 51, "Unverified items must stay unknown")
        for name in ("Harlequin Crest", "Fists of Fate"):
            entry = service.find_unique(name)
            self.assertEqual(entry["target_bosses"], [], f"{name} must not name a boss")

    def test_items_from_the_windows_report_now_have_verified_sources(self):
        """The seven items the Windows test showed as DATA UNAVAILABLE.
        Six now have a verified Season 15 drop source; Nemesis Bracers
        has none in any source and must stay unavailable."""

        forventet = {
            "Might of the Ursine": "target_boss",
            "Misericorde": "target_boss",
            "Mjölnic Ryng": "target_boss",
            "Mother's Embrace": "general_pool",
            "Nails of the Gore-Crowned": "target_boss",
            "Nesekem, the Herald": "mythic_pool",
            "Nemesis Bracers": None,
        }
        for name, drop_type in forventet.items():
            entry = service.find_unique(name)
            self.assertIsNotNone(entry, f"{name} is missing from the catalogue")
            self.assertTrue(entry["from_api"], f"{name} did not come from the API")
            self.assertTrue(entry["description"], f"{name} has no description")
            self.assertEqual(entry["drop_type"], drop_type, name)

    def test_a_mapped_item_still_shows_its_boss(self):
        moloch = service.find_unique("Moloch's Beating Flame")
        self.assertEqual([b["name"] for b in service.get_bosses_for_unique(moloch["id"])],
                         ["The Butcher"])

    def test_accented_names_survive_normalization(self):
        import unicodedata

        from src.item_icon_assets import normalize_id

        for name in ("Mjölnic Ryng", "Berú of Arreat - Charm"):
            self.assertEqual(
                normalize_id(name),
                normalize_id(unicodedata.normalize("NFD", name)),
                "Two spellings of the same name produce different ids",
            )

    # --- drop sources (server dataset, Season 15) -------------------

    def test_drop_source_dataset_loads(self):
        meta = service.drop_source_info()
        self.assertEqual(meta["season"], 15)
        self.assertEqual(meta["dataset_version"], DROP_DATASET_VERSION)
        self.assertGreaterEqual(len(meta["source_list"]), 2, "Needs independent sources")

    def test_target_boss_data_displays(self):
        for name, boss in (("Misericorde", "Bartuc"),
                           ("Might of the Ursine", "Harbinger of Hatred"),
                           ("Mjölnic Ryng", "Bartuc"),
                           ("Nails of the Gore-Crowned", "The Butcher")):
            entry = service.find_unique(name)
            self.assertEqual(entry["drop_type"], "target_boss", name)
            self.assertEqual(entry["drop_boss_names"], [boss], name)
            self.assertTrue(entry["target_bosses"], f"{name} resolved to no boss record")
            self.assertGreaterEqual(len(entry["drop_verified_by"]), 2, name)

    def test_general_pool_data_displays(self):
        for name in ("Mother's Embrace", "Fists of Fate"):
            entry = service.find_unique(name)
            self.assertEqual(entry["drop_type"], "general_pool", name)
            self.assertEqual(entry["target_bosses"], [], f"{name} must not name a boss")

    def test_mythic_pool_data_displays(self):
        for name in ("Harlequin Crest", "Nesekem, the Herald"):
            entry = service.find_unique(name)
            self.assertEqual(entry["drop_type"], "mythic_pool", name)
            self.assertEqual(entry["target_bosses"], [], f"{name} must not name a boss")

    def test_unverified_item_stays_data_unavailable(self):
        entry = service.find_unique("Nemesis Bracers")
        self.assertIsNone(entry["drop_type"])
        self.assertEqual(entry["target_bosses"], [])
        self.assertEqual(entry["drop_boss_names"], [])
        self.assertIsNone(ItemsAPI().drop_source("Nemesis Bracers"),
                          "The server must not carry an unverified record")

    def test_no_invented_sources(self):
        """Every drop record on the server cites the sources that agreed
        on it, and every one of them is marked verified."""

        payload = ItemsAPI().drop_sources()
        for record in payload["items"]:
            for drop in record["drop_sources"]:
                self.assertEqual(drop["status"], "verified", record["item_name"])
                self.assertEqual(drop["season"], 15, record["item_name"])
                self.assertGreaterEqual(len(drop["sources"]), 1, record["item_name"])
                if drop["type"] == "target_boss":
                    self.assertTrue(drop.get("name"), record["item_name"])

    def test_special_items_keep_their_season_15_notes(self):
        for name in ("Harlequin Crest", "Fists of Fate"):
            entry = service.find_unique(name)
            self.assertTrue(entry["notes"], f"{name} lost its special note")
            self.assertIn("Horadric Cube", entry["notes"])

    def test_windforce_survived_the_move_to_the_server(self):
        # It used to be local data. It is still on the page, now served.
        windforce = service.find_unique("Windforce")
        self.assertTrue(windforce["drop_from_api"])
        self.assertEqual(windforce["category"], "supplement")
        self.assertEqual(windforce["drop_boss_names"], ["Urivar"])

    def test_item_dataset_sha256_did_not_change(self):
        # Adding drop sources must not touch the canonical item dataset.
        self.assertEqual(ItemsAPI().version()["sha256"], EXPECTED_SHA256)

    def test_api_is_still_read_only(self):
        import requests

        for method in ("POST", "PUT", "PATCH", "DELETE"):
            r = requests.request(method, f"{CONFIGURED_URL}/drop-sources", timeout=5)
            self.assertEqual(r.status_code, 405, method)

    # --- the server is authoritative -------------------------------

    def test_server_data_overrides_the_local_mapping(self):
        """The three items where this project's older research and the
        Season 15 sources disagree. The server wins, every time."""

        for name, boss in (("Galvanic Azurite", "Duriel, King of Maggots"),
                           ("Yen's Blessing", "Urivar"),
                           ("Paingorger's Gauntlets", "Grigoire, The Galvanic Saint")):
            entry = service.find_unique(name)
            self.assertTrue(entry["drop_from_api"], f"{name} fell back to local data")
            self.assertEqual(entry["drop_verification"], "verified", name)
            bosses = [b["name"] for b in service.get_bosses_for_unique(entry["id"])]
            self.assertEqual(bosses, [boss], name)

    def test_no_drop_source_is_local_any_more(self):
        for unique in self.uniques:
            self.assertNotEqual(unique.get("drop_verification"), "local_legacy",
                                f"{unique['name']} still shows local drop data")

    def test_the_11_missing_items_come_from_the_servers_supplement(self):
        """They used to live in the app. Now the server publishes them,
        with a verified boss and their metadata marked as older
        research - and they are still on the page."""

        supplement = [u for u in self.uniques if u["category"] == "supplement"]
        self.assertEqual(len(supplement), 11)
        for unique in supplement:
            self.assertTrue(unique["from_api"])
            self.assertEqual(unique["metadata_status"], "local_legacy")
            self.assertEqual(unique["drop_verification"], "verified")
            self.assertTrue(unique["target_bosses"], f"{unique['name']} lost its boss")
            self.assertGreaterEqual(len(unique["drop_verified_by"]), 2, unique["name"])
        self.assertIn("Windforce", [u["name"] for u in supplement])

    def test_special_notes_come_from_the_server(self):
        for name, fragment in (("Harlequin Crest", "Horadric Cube"),
                               ("Fists of Fate", "Helltide")):
            entry = service.find_unique(name)
            self.assertTrue(entry["notes"], f"{name} lost its note")
            self.assertIn(fragment, entry["notes"])
            # And it really is the server's copy, not a local one.
            record = ItemsAPI().drop_source(name)
            self.assertEqual(record["note"], entry["notes"])

    # --- confidence levels ------------------------------------------

    def test_single_source_is_distinguishable_from_verified(self):
        entry = service.find_unique("Bane of Ahjad-Den")
        self.assertEqual(entry["drop_verification"], "single_source")
        self.assertEqual(entry["drop_confidence"], "low")
        self.assertEqual(entry["drop_verified_by"], ["slashingcreeps"])

        payload = ItemsAPI().drop_sources()
        verified_names = {i["item_name"] for i in payload["items"]}
        self.assertNotIn("Bane of Ahjad-Den", verified_names,
                         "A single-source record must not sit among the verified ones")
        self.assertEqual([i["item_name"] for i in payload["single_source_items"]],
                         ["Bane of Ahjad-Den"])
        for record in payload["items"]:
            for drop in record["drop_sources"]:
                self.assertEqual(drop["verification_status"], "verified")
                self.assertGreaterEqual(drop["source_count"], 2)

    # --- the unresolved stay unresolved -----------------------------

    def test_unresolved_items_stay_unresolved(self):
        payload = ItemsAPI().drop_sources()
        self.assertEqual(payload["unresolved_count"], 51)
        for name in payload["unresolved_items"]:
            entry = service.find_unique(name)
            self.assertIsNotNone(entry, name)
            self.assertIsNone(entry["drop_type"], f"{name} was given a drop source")
            self.assertEqual(entry["target_bosses"], [], name)
            self.assertIsNone(entry["drop_verification"], name)

    def test_the_counts_reconcile(self):
        """231 catalogue items = 179 verified + 1 single-source + 51
        unresolved. The 30 legacy mappings are a separate layer and are
        not counted here."""

        payload = ItemsAPI().drop_sources()
        self.assertEqual(payload["catalogue_size"], 231)
        self.assertEqual(payload["count"], 179)
        self.assertEqual(payload["single_source_count"], 1)
        self.assertEqual(payload["unresolved_count"], 51)
        self.assertEqual(
            payload["count"] + payload["single_source_count"] + payload["unresolved_count"],
            payload["catalogue_size"],
        )
        # Everything on the page comes from the server: the 231
        # catalogue items plus the 11 the catalogue is missing.
        from_api = [u for u in self.uniques if u["from_api"]]
        self.assertEqual(len(from_api), len(self.uniques))
        self.assertEqual(len(self.uniques), payload["catalogue_size"]
                         + payload["catalogue_supplement_count"])

    def test_drop_source_file_reload_and_version_reporting(self):
        version = ItemsAPI().version()
        drops = version["drop_sources"]
        self.assertEqual(drops["version"], DROP_DATASET_VERSION)
        self.assertEqual(drops["season"], 15)
        self.assertEqual(drops["item_count"], 179)
        self.assertEqual(len(drops["sha256"]), 64)
        # The item dataset's own hash is untouched by any of this.
        self.assertEqual(version["sha256"], EXPECTED_SHA256)

    def test_no_duplicate_entries_after_merging(self):
        ids = [u["id"] for u in self.uniques]
        names = [u["name"].lower() for u in self.uniques]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate ids in the merged catalogue")
        self.assertEqual(len(names), len(set(names)), "The same item appears twice")

    def test_item_known_under_an_older_local_id_is_not_duplicated(self):
        # This one used to exist twice: once from the API without a
        # boss, once from the local table under the older id
        # "eightfold_idol". With no local table there is one record, and
        # its id is simply its normalized name.
        matches = [u for u in self.uniques if u["name"] == "The Eightfold Idol"]
        self.assertEqual(len(matches), 1)
        entry = matches[0]
        self.assertEqual(entry["id"], "the_eightfold_idol")
        self.assertEqual(entry["category"], "uniques")
        self.assertTrue(entry["target_bosses"])

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
            self.assertIsNotNone(unique["api"], unique["name"])
            raa = unique["api"]
            # Catalogue records carry "name"; supplement records, which
            # come from the drop-source dataset, carry "item_name".
            self.assertEqual(raa.get("name") or raa.get("item_name"), unique["name"])

    def test_item_without_an_api_record_is_not_presented_as_api_data(self):
        """The 11 entries the dataset doesn't list are kept for their
        boss mapping only - they must never pass for verified data."""

        supplement = [u for u in self.uniques if u["category"] == "supplement"]
        self.assertTrue(supplement, "Expected the catalogue supplement")
        for unique in supplement:
            self.assertEqual(unique["metadata_status"], "local_legacy")
            self.assertNotIn(unique["name"], {i["name"] for i in ItemsAPI().items()},
                             "A supplement item must not also be in the catalogue")
            # No catalogue metadata may be faked in: no image.
            self.assertIsNone(unique.get("image_filename"))

    def test_every_supplement_item_resolves_to_a_real_boss(self):
        for unique in [u for u in self.uniques if u["category"] == "supplement"]:
            self.assertTrue(service.get_bosses_for_unique(unique["id"]), unique["name"])

    def test_no_hardcoded_item_catalogue_in_the_production_path(self):
        import subprocess
        from pathlib import Path

        rod = Path(__file__).resolve().parent.parent / "src"
        fundet = subprocess.run(
            ["grep", "-rlnE", r"(from|import)[^#]*unique_data", str(rod)],
            capture_output=True, text=True).stdout.strip()
        self.assertEqual(fundet, "", f"Production code still imports unique_data: {fundet}")
        self.assertGreater(len(self.uniques), 200)


if __name__ == "__main__":
    unittest.main()
