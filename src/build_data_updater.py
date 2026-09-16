"""Windows Product Phase W10 -- Build Data Updates.

A completely separate update system from ``src/updater.py`` (Windows
Product Phases W7-W9, app version / installer download-verify-install-
rollback). That module updates the *application itself* via GitHub
Releases; this module updates the *Diablo 4 build JSON files*
(``builds/*.json``) that ship inside the app, without requiring a new
app version/install at all.

Deliberately independent: no shared state, no import of/from
``src/updater.py``. The two concepts (app version vs. build-data
version) are tracked, checked and updated completely separately - see
PROJECT_STATUS.md's W10 entry.

Hosting: no new infrastructure. GitHub already serves any committed
file as a plain public GET via
``https://raw.githubusercontent.com/<repo>/<branch>/<path>`` - the same
kind of endpoint this project's Maxroll data pipeline and W5-W9's
GitHub Releases API already rely on. ``builds/manifest.json`` (committed
alongside the real build files) is the authoritative file list plus a
plain human-readable date-string version stamp (e.g. ``"2026-09-16"``)
- deliberately NOT tied to a git commit SHA (W5 removed the app's
production git dependency on purpose) and NOT a semver scheme (build
data doesn't need one). ``YYYY-MM-DD`` sorts correctly with plain
string comparison, so callers never need a date-parsing library to
decide "is the remote version newer" - see ``SettingsInterface``'s
Build Data section in ``src/app.py``.

Style matches this codebase's existing synchronous-network-call
convention (see ``src/api.py``'s ``DiabloAPI`` and ``src/updater.py``)
rather than introducing async networking.
"""

import json
import os
import shutil
import tempfile

import requests

from src.managers.leveling_manager import LevelingManager

# Same repo/branch this project's build is already hosted on (see
# src/app.py's GITHUB_REPO and PROJECT_STATUS.md) - not guessed.
DEFAULT_REPO = "jens3105/Diablo4Companion"
DEFAULT_BRANCH = "feature/dashboard-v2"

RAW_BASE_URL = "https://raw.githubusercontent.com"

MANIFEST_FILENAME = "manifest.json"

# Network timeouts, matching the style of the other timeouts already
# used across this codebase (src/api.py, src/app.py, src/updater.py).
_MANIFEST_TIMEOUT_SECONDS = 10
_FILE_TIMEOUT_SECONDS = 15


def _raw_builds_url(repo: str, branch: str, filename: str) -> str:
    return f"{RAW_BASE_URL}/{repo}/{branch}/builds/{filename}"


def fetch_remote_manifest(
    repo: str = DEFAULT_REPO, branch: str = DEFAULT_BRANCH
) -> dict:
    """Fetch and parse the remote ``builds/manifest.json`` from GitHub.

    Returns ``{"version": str, "files": [str, ...]}``. Raises a clear
    exception (``requests.RequestException`` for a network/HTTP
    failure, ``ValueError`` for invalid JSON or a manifest missing the
    required fields) on any failure - the caller decides how to present
    a network failure vs. a genuine success, so this never swallows the
    difference.
    """

    url = _raw_builds_url(repo, branch, MANIFEST_FILENAME)

    response = requests.get(url, timeout=_MANIFEST_TIMEOUT_SECONDS)
    response.raise_for_status()

    try:
        data = response.json()
    except ValueError as exc:
        raise ValueError(
            f"Remote manifest at {url} is not valid JSON: {exc}"
        ) from exc

    if not isinstance(data, dict) or "version" not in data or "files" not in data:
        raise ValueError(
            f"Remote manifest at {url} is missing the required "
            f"'version'/'files' fields."
        )

    return {"version": data["version"], "files": list(data["files"])}


def read_local_manifest(builds_dir: str) -> dict | None:
    """Read the LOCAL ``builds_dir/manifest.json``, or ``None`` if it is
    missing (e.g. an install predating this phase) or invalid JSON.

    Never raises - this is a read of local state used to render "what
    version do we currently have", and a missing/corrupt local manifest
    must degrade to "no known local version", not a crash. The manifest
    file being committed to the repo (and therefore bundled by the
    existing PyInstaller ``datas`` glob, ``builds/*.json``, with zero
    ``.spec``/``.iss`` changes) is what makes it double as the local
    version record too - no separate QSettings/database entry needed.
    """

    path = os.path.join(builds_dir, MANIFEST_FILENAME)

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict) or "version" not in data:
        return None

    return data


def download_build_data(
    remote_manifest: dict,
    builds_dir: str,
    progress_callback=None,
    repo: str = DEFAULT_REPO,
    branch: str = DEFAULT_BRANCH,
) -> None:
    """Download and install every build file listed in
    ``remote_manifest["files"]`` - the ONLY files ever downloaded, never
    a guessed name.

    Each file is downloaded into a fresh ``tempfile.mkdtemp()``
    directory and verified in full (HTTP success, non-empty content,
    valid JSON, and the same minimal schema check
    ``LevelingManager.is_valid_build_schema`` already uses - reused
    here directly, not reinvented) BEFORE any real file under
    ``builds_dir`` is touched. If any file fails any check, this raises
    immediately with a message naming the specific file and reason, and
    ``builds_dir`` is left completely untouched - no partial apply.

    Only once every file has downloaded and verified successfully are
    the real files replaced, one per file, via ``os.replace`` (atomic
    on both POSIX and Windows *when source and destination are on the
    same filesystem* - the temp directory is therefore created as a
    sibling of ``builds_dir`` rather than in the system-wide temp
    location, so the rename is guaranteed atomic rather than silently
    falling back to a non-atomic copy+delete). The manifest's own
    version-stamp file is replaced LAST, only after every data file
    succeeded, so an interruption between a data-file replacement and
    the manifest replacement just means a retry re-detects "update
    still available" rather than any inconsistent/corrupt state.

    ``progress_callback(files_done, total_files)`` is called after each
    file finishes downloading+verifying, matching the simple-progress-
    callback style ``src/updater.py``'s ``download_asset`` already uses
    (this module does not import from ``src/updater.py`` - the two are
    deliberately independent).
    """

    files = list(remote_manifest.get("files") or [])
    total_files = len(files)

    builds_dir_abs = os.path.abspath(builds_dir)
    os.makedirs(builds_dir_abs, exist_ok=True)

    # Sibling of builds_dir (not the system temp dir) so the final
    # os.replace() calls below are a genuine same-filesystem atomic
    # rename on both POSIX and Windows, never a cross-filesystem
    # fallback.
    temp_root = os.path.dirname(builds_dir_abs)
    temp_dir = tempfile.mkdtemp(prefix="d4c_build_data_", dir=temp_root)

    try:
        verified_temp_paths = []  # [(filename, temp_path), ...], in order

        for index, filename in enumerate(files):
            url = _raw_builds_url(repo, branch, filename)

            try:
                response = requests.get(url, timeout=_FILE_TIMEOUT_SECONDS)
            except requests.RequestException as exc:
                raise RuntimeError(
                    f"Failed to download build data file '{filename}': "
                    f"network error ({exc})."
                ) from exc

            if response.status_code != 200:
                raise RuntimeError(
                    f"Failed to download build data file '{filename}': "
                    f"HTTP {response.status_code}."
                )

            content = response.content
            if not content:
                raise RuntimeError(
                    f"Failed to verify build data file '{filename}': "
                    f"downloaded content is empty."
                )

            try:
                data = json.loads(content)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Failed to verify build data file '{filename}': "
                    f"not valid JSON ({exc})."
                ) from exc

            if not LevelingManager.is_valid_build_schema(data):
                raise RuntimeError(
                    f"Failed to verify build data file '{filename}': "
                    f"missing required 'build_name'/'milestones' fields."
                )

            temp_path = os.path.join(temp_dir, filename)
            with open(temp_path, "wb") as fh:
                fh.write(content)

            verified_temp_paths.append((filename, temp_path))

            if progress_callback is not None:
                progress_callback(index + 1, total_files)

        # Every file in the manifest downloaded and verified - only now
        # is the real builds_dir touched, one atomic rename per file.
        for filename, temp_path in verified_temp_paths:
            real_path = os.path.join(builds_dir_abs, filename)
            os.replace(temp_path, real_path)

        # The manifest's own version-stamp file is written and swapped
        # in LAST, only after every data file succeeded above.
        manifest_temp_path = os.path.join(temp_dir, MANIFEST_FILENAME)
        with open(manifest_temp_path, "w", encoding="utf-8") as fh:
            json.dump(remote_manifest, fh, indent=2)
        os.replace(manifest_temp_path, os.path.join(builds_dir_abs, MANIFEST_FILENAME))

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
