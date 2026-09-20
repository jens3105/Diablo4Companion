"""Tests for the in-app updater: check -> compare -> download -> verify
-> launch installer.

    QT_QPA_PLATFORM=offscreen .venv/bin/python3 -m pytest tests/test_updater.py -v

Everything here is offline. The GitHub Releases API, the asset download
and the installer launch are all faked, so the suite tests *our*
decisions - which release counts as newer, when a download is refused,
what gets executed - rather than GitHub's availability. The one thing
that cannot be faked, a real installer run on real Windows, is covered
by .github/workflows/windows-build.yml instead.
"""

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import requests  # noqa: E402

from src import app as app_module  # noqa: E402
from src import updater  # noqa: E402
from src.version import __version__  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


def _release(tag: str, *, with_installer=True, with_checksum=True, size=1234) -> dict:
    """A GitHub Releases API payload shaped like the real one."""

    assets = []
    if with_installer:
        assets.append({
            "name": updater.INSTALLER_ASSET_NAME,
            "size": size,
            "browser_download_url": f"https://example.invalid/{tag}/setup.exe",
        })
    if with_checksum:
        assets.append({
            "name": updater.CHECKSUM_ASSET_NAME,
            "size": 64,
            "browser_download_url": f"https://example.invalid/{tag}/setup.exe.sha256",
        })
    return {"tag_name": tag, "name": tag, "body": "notes", "assets": assets}


class VersionComparisonTests(unittest.TestCase):
    """1) The rule that decides whether an update exists at all."""

    def test_parses_plain_and_v_prefixed_tags(self):
        self.assertEqual(app_module._parse_semver("1.0.12"), (1, 0, 12))
        self.assertEqual(app_module._parse_semver("v1.0.13"), (1, 0, 13))
        self.assertEqual(app_module._parse_semver("V2.10.0"), (2, 10, 0))
        self.assertEqual(app_module._parse_semver("  v1.2.3  "), (1, 2, 3))

    def test_refuses_to_guess_at_a_tag_it_cannot_parse(self):
        for tag in ("latest", "v1.0", "1.0.0-beta", "", "1.0.x", "v1.0.0.1"):
            self.assertIsNone(app_module._parse_semver(tag), tag)

    def test_ordering_is_numeric_not_lexicographic(self):
        p = app_module._parse_semver
        self.assertGreater(p("v1.0.13"), p("v1.0.12"))
        # The case a string comparison gets wrong: "1.0.9" > "1.0.10".
        self.assertGreater(p("v1.0.10"), p("v1.0.9"))
        self.assertGreater(p("v1.1.0"), p("v1.0.99"))
        self.assertEqual(p("v1.0.14"), p("1.0.14"))


class _FakeResponse:
    def __init__(self, payload=None, status_code=200, content=b""):
        self._payload = payload
        self.status_code = status_code
        self.content = content
        self.headers = {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


class ReleaseCheckTests(unittest.TestCase):
    """2), 9) and 10): parsing the latest release and the states it
    puts the UI into."""

    def test_reads_the_official_latest_release_endpoint(self):
        self.assertTrue(
            app_module.GITHUB_RELEASES_API_URL.endswith("/releases/latest"),
            "Must use the latest-release endpoint, which excludes drafts "
            "and pre-releases by definition",
        )

    def test_repo_matches_this_checkouts_actual_git_remote(self):
        """The owner/repo is a constant because an installed app has no
        git checkout - but it must match the real remote, not a guess."""

        try:
            remote = subprocess.run(
                ["git", "-C", str(REPO_ROOT), "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            self.skipTest("Not a git checkout")
        if not remote:
            self.skipTest("No origin remote")

        slug = remote.rstrip("/")
        slug = slug[:-4] if slug.endswith(".git") else slug
        slug = slug.split(":")[-1] if slug.startswith("git@") else "/".join(slug.split("/")[-2:])
        self.assertEqual(app_module.GITHUB_REPO, slug)

    def test_update_available_state(self):
        release = _release("v99.0.0")
        with mock.patch.object(app_module.requests, "get", return_value=_FakeResponse(release)):
            status, data = app_module._check_for_newer_release()
        self.assertEqual(status, "update_available")
        self.assertEqual(data["tag_name"], "v99.0.0")

    def test_up_to_date_state(self):
        with mock.patch.object(app_module.requests, "get",
                               return_value=_FakeResponse(_release(f"v{__version__}"))):
            status, _ = app_module._check_for_newer_release()
        self.assertEqual(status, "up_to_date")

    def test_an_older_release_is_not_an_update(self):
        with mock.patch.object(app_module.requests, "get",
                               return_value=_FakeResponse(_release("v0.0.1"))):
            status, _ = app_module._check_for_newer_release()
        self.assertEqual(status, "up_to_date")

    def test_no_releases_published_yet(self):
        with mock.patch.object(app_module.requests, "get",
                               return_value=_FakeResponse(None, status_code=404)):
            status, data = app_module._check_for_newer_release()
        self.assertEqual(status, "no_releases")
        self.assertIsNone(data)

    def test_network_error_is_not_mistaken_for_up_to_date(self):
        with mock.patch.object(app_module.requests, "get",
                               side_effect=requests.ConnectionError("no route")):
            status, _ = app_module._check_for_newer_release()
        self.assertEqual(status, "network_error")

    def test_unparseable_tag_is_reported_not_guessed(self):
        with mock.patch.object(app_module.requests, "get",
                               return_value=_FakeResponse(_release("nightly"))):
            status, data = app_module._check_for_newer_release()
        self.assertEqual(status, "unparseable")
        self.assertEqual(data["tag_name"], "nightly")


class AssetTests(unittest.TestCase):
    """3) A release without the installer asset must not be installed."""

    def test_finds_the_official_installer_and_checksum_assets(self):
        release = _release("v9.9.9")
        self.assertEqual(updater.find_installer_asset(release)["name"],
                         "Diablo4Companion-Setup.exe")
        self.assertEqual(updater.find_checksum_asset(release)["name"],
                         "Diablo4Companion-Setup.exe.sha256")

    def test_missing_installer_asset_returns_none(self):
        self.assertIsNone(updater.find_installer_asset(_release("v9.9.9", with_installer=False)))

    def test_missing_checksum_asset_returns_none(self):
        self.assertIsNone(updater.find_checksum_asset(_release("v9.9.9", with_checksum=False)))


class DownloadTests(unittest.TestCase):
    """4) A failed download must leave the installed app untouched."""

    def test_failed_download_raises_and_writes_no_usable_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "setup.exe")
            with mock.patch.object(updater.requests, "get",
                                   side_effect=requests.ConnectionError("dropped")):
                with self.assertRaises(requests.RequestException):
                    updater.download_asset(
                        {"browser_download_url": "https://example.invalid/x", "size": 10}, dest)
            self.assertFalse(os.path.exists(dest) and os.path.getsize(dest) > 0)


class VerificationTests(unittest.TestCase):
    """5) and 6): nothing is executed unless it verifies."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "setup.exe")
        self.payload = b"pretend installer bytes"
        with open(self.path, "wb") as f:
            f.write(self.payload)
        self.digest = hashlib.sha256(self.payload).hexdigest()
        self.asset = {"size": len(self.payload)}

    def test_matching_sha256_passes(self):
        ok, reason = updater.verify_download(self.path, self.asset, self.digest.encode())
        self.assertTrue(ok, reason)

    def test_sha256_sidecar_with_filename_and_newline_still_parses(self):
        sidecar = f"{self.digest}  Diablo4Companion-Setup.exe\n".encode()
        ok, reason = updater.verify_download(self.path, self.asset, sidecar)
        self.assertTrue(ok, reason)

    def test_mismatched_sha256_fails_hard(self):
        ok, reason = updater.verify_download(self.path, self.asset, (b"0" * 64))
        self.assertFalse(ok)
        self.assertIn("hecksum", reason)

    def test_a_passing_size_never_overrides_a_failing_checksum(self):
        # Same size, wrong content - size alone would have said yes.
        with open(self.path, "wb") as f:
            f.write(b"x" * len(self.payload))
        ok, _ = updater.verify_download(self.path, self.asset, self.digest.encode())
        self.assertFalse(ok)

    def test_size_mismatch_fails_even_without_a_checksum(self):
        ok, reason = updater.verify_download(self.path, {"size": 999999}, None)
        self.assertFalse(ok)
        self.assertIn("Size mismatch", reason)

    def test_missing_file_fails(self):
        ok, _ = updater.verify_download(os.path.join(self.tmp.name, "nope.exe"),
                                        self.asset, None)
        self.assertFalse(ok)

    def test_no_checksum_available_is_stated_honestly(self):
        ok, reason = updater.verify_download(self.path, self.asset, None)
        self.assertTrue(ok)
        self.assertIn("no checksum", reason)


class LaunchTests(unittest.TestCase):
    """8) What actually gets executed, and how."""

    def test_installer_is_launched_directly_without_a_shell(self):
        with mock.patch.object(updater.subprocess, "Popen") as popen:
            updater.launch_installer(r"C:\Temp\d4c\Diablo4Companion-Setup.exe")
        popen.assert_called_once_with(
            [r"C:\Temp\d4c\Diablo4Companion-Setup.exe"], shell=False)

    def test_nothing_from_the_release_metadata_reaches_a_shell(self):
        args, kwargs = None, None
        with mock.patch.object(updater.subprocess, "Popen") as popen:
            updater.launch_installer("/tmp/setup.exe")
            args, kwargs = popen.call_args
        self.assertIs(kwargs.get("shell"), False)
        self.assertEqual(len(args[0]), 1, "Only the installer path may be passed")


class UserConfigPreservationTests(unittest.TestCase):
    """7) api_url.txt must survive an update.

    The installer decides this, so the installer script is what gets
    checked: Inno Setup only writes the files it ships, and there is no
    step that clears the target directory. A real install-over-install
    is proven on Windows in the build workflow.
    """

    def setUp(self):
        self.iss = (REPO_ROOT / "installer" / "diablo4companion.iss").read_text(encoding="utf-8")

    def test_installer_never_clears_the_install_directory(self):
        self.assertNotIn("[InstallDelete]", self.iss,
                         "An InstallDelete section could remove user files")

    def test_installer_only_ships_its_own_build_output(self):
        kilder = [line for line in self.iss.splitlines()
                  if line.strip().startswith("Source:")]
        self.assertTrue(kilder)
        for line in kilder:
            self.assertIn("dist\\Diablo4Companion", line,
                          "The installer must only write its own build output")

    def test_the_app_looks_for_its_config_in_the_install_directory(self):
        from src.api_config import URL_FILE, url_file_path

        self.assertEqual(URL_FILE, "api_url.txt")
        self.assertTrue(url_file_path().endswith(URL_FILE))

    def test_no_internal_address_is_baked_into_the_repo(self):
        import re

        for path in (REPO_ROOT / "src").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertEqual(
                re.findall(r"192\.168\.\d+\.\d+", text), [],
                f"{path.name} contains a private network address",
            )


if __name__ == "__main__":
    unittest.main()
