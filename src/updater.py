"""Windows Product Phase W8 -- Download -> Verify -> Install -> Restart.

Plain, synchronous functions consumed by
``SettingsInterface._on_update_now_clicked`` (src/app.py). Deliberately
matches this codebase's existing synchronous-network-call style (see
``DiabloAPI`` in src/api.py and ``_on_check_updates_clicked`` in
src/app.py) rather than introducing async/``QNetworkAccessManager``
networking - this whole app already blocks on ``requests`` calls and
pumps ``QApplication.processEvents()`` around them.

No custom restart-helper process here by design: the real installer
(``installer/diablo4companion.iss``) is Inno Setup, and Inno Setup's own
``[Run]`` "launch after install" mechanism already restarts the app once
the user finishes the wizard. This module only gets the verified
installer running and then gets this (old) process out of its way.
"""

import hashlib
import os
import subprocess

import requests

# Exact filenames a build of this app's Inno Setup installer produces
# (see installer/diablo4companion.iss's OutputBaseFilename) and the
# SHA256 sidecar the CI build now computes alongside it (see
# .github/workflows/windows-build.yml). Matched EXACTLY against a
# release asset's "name" field - never a pattern/guess, since a
# mismatch here would mean downloading and running the wrong file.
INSTALLER_ASSET_NAME = "Diablo4Companion-Setup.exe"
CHECKSUM_ASSET_NAME = "Diablo4Companion-Setup.exe.sha256"

# Chunk size for streamed downloads.
_DOWNLOAD_CHUNK_BYTES = 65536


def find_installer_asset(release: dict) -> dict | None:
    """Return the GitHub release asset dict for the real installer exe,
    or ``None`` if this release has no such asset attached.

    ``None`` is a real, expected outcome (e.g. an old/malformed release
    published before this asset existed, or one missing it for any
    other reason) - not a bug, and callers must not crash on it.
    """

    for asset in release.get("assets", []) or []:
        if asset.get("name") == INSTALLER_ASSET_NAME:
            return asset
    return None


def find_checksum_asset(release: dict) -> dict | None:
    """Return the GitHub release asset dict for the installer's
    ``.sha256`` sidecar, or ``None`` if this release doesn't have one
    (e.g. an older release published before W8 added this mechanism).
    Always optional - never required by ``verify_download`` below."""

    for asset in release.get("assets", []) or []:
        if asset.get("name") == CHECKSUM_ASSET_NAME:
            return asset
    return None


def download_asset(asset: dict, dest_path: str, progress_callback=None) -> None:
    """Stream-download a GitHub release asset to ``dest_path``.

    ``dest_path`` must be a path under a fresh ``tempfile.mkdtemp()``
    directory (the caller's responsibility) - never a predictable
    shared path, since two updates run in quick succession must not
    collide or race on the same file.

    ``progress_callback(bytes_downloaded, total_bytes)`` is invoked
    after each chunk when given; ``total_bytes`` is ``None`` when the
    server doesn't report a size. Raises ``requests.RequestException``
    on a network/timeout error, and ``OSError`` (via a raised
    ``IOError``-style ``RuntimeError``) if the stream ends short of the
    asset's declared size.
    """

    url = asset["browser_download_url"]
    expected_size = asset.get("size")

    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()

    total_bytes = expected_size
    if total_bytes is None:
        content_length = response.headers.get("Content-Length")
        if content_length is not None and content_length.isdigit():
            total_bytes = int(content_length)

    bytes_downloaded = 0
    try:
        with open(dest_path, "wb") as fh:
            for chunk in response.iter_content(chunk_size=_DOWNLOAD_CHUNK_BYTES):
                if not chunk:
                    continue
                fh.write(chunk)
                bytes_downloaded += len(chunk)
                if progress_callback is not None:
                    progress_callback(bytes_downloaded, total_bytes)
    finally:
        response.close()

    if expected_size is not None and bytes_downloaded != expected_size:
        raise RuntimeError(
            f"Incomplete download: got {bytes_downloaded} bytes, "
            f"expected {expected_size} bytes."
        )


def verify_download(
    file_path: str, asset: dict, checksum_asset_data: bytes | None
) -> tuple[bool, str]:
    """Verify a downloaded installer file against the release asset's
    metadata and (when available) a real SHA256 checksum.

    Always checks the file exists and its size matches ``asset["size"]``
    exactly (when GitHub reports a size). When ``checksum_asset_data``
    (the raw contents of the ``.sha256`` sidecar - a hex digest, as
    bytes) is given, additionally hashes the actual file and compares -
    ANY mismatch there is a hard failure, never overridden by a passing
    size check. When no checksum was available at all, this is stated
    honestly in the returned reason rather than implying a full
    integrity check happened.

    Returns ``(is_valid, reason)``.
    """

    if not os.path.isfile(file_path):
        return False, f"Downloaded file not found at {file_path}."

    actual_size = os.path.getsize(file_path)
    expected_size = asset.get("size")
    if expected_size is not None and actual_size != expected_size:
        return False, (
            f"Size mismatch: downloaded file is {actual_size} bytes, "
            f"release asset reports {expected_size} bytes."
        )

    if checksum_asset_data is None:
        return True, "size-only check passed, no checksum available"

    expected_hex = checksum_asset_data.decode("ascii", errors="strict").strip().lower()
    # A .sha256 sidecar produced by `Get-FileHash | Format-List` or
    # `sha256sum`-style tooling may have trailing whitespace/newlines or
    # a "<hash>  <filename>" shape - only the leading hex token matters.
    expected_hex = expected_hex.split()[0] if expected_hex.split() else ""

    hasher = hashlib.sha256()
    with open(file_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_DOWNLOAD_CHUNK_BYTES), b""):
            hasher.update(chunk)
    actual_hex = hasher.hexdigest().lower()

    if actual_hex != expected_hex:
        return False, (
            f"Checksum mismatch: downloaded file's SHA256 does not match "
            f"the published checksum. Refusing to install."
        )

    return True, "size and SHA256 checksum both verified"


def launch_installer(installer_path: str) -> None:
    """Launch the verified installer as a separate process and return
    immediately - never blocks waiting for the (interactive) installer
    wizard to finish.

    ``shell=False`` always, and ``installer_path`` is the sole argument
    - no GitHub-metadata-derived string is ever interpolated into a
    shell command. Lets any exception (e.g. the file no longer existing,
    or not being executable) propagate naturally; the caller wraps this
    in its own try/except so it can show a clear status message instead
    of closing the app on a failed launch.
    """

    subprocess.Popen([installer_path], shell=False)
