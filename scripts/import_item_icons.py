"""Import helper for user-provided Unique item icons.

Companion never fetches/scrapes/datamines item icons itself (see
src/item_icon_assets.py's module docstring). This script only helps
YOU copy YOUR OWN image files into the right place with the right
name - it never downloads anything from the internet.

Usage:
    python3 scripts/import_item_icons.py
    python3 scripts/import_item_icons.py --source /path/to/your/icons

Matching is exact-only after normalizing punctuation/case/separators
(e.g. "Harlequin Crest.png", "harlequin-crest.PNG", and
"HARLEQUIN_CREST.png" all match the "harlequin_crest" Unique) - never
fuzzy, so an unrecognized filename is reported as unmatched rather than
silently attached to the wrong item.
"""

import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtGui import QGuiApplication, QImage

from src import item_icon_assets, unique_drop_service as service

DEFAULT_SOURCE = os.path.expanduser("~/Downloads/Diablo4Companion-ItemIcons")


def _validate_image(path: str) -> bool:
    """Qt-based decode check (reuses the same image stack the app's own
    _load_item_pixmap uses) - True only if the file is a real, readable
    image with non-zero dimensions."""

    image = QImage(path)
    return not image.isNull() and image.width() > 0 and image.height() > 0


def import_icons(source_dir: str) -> dict:
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)

    known_ids = {u["id"] for u in service.all_uniques()}
    id_by_normalized = {item_icon_assets.normalize_id(uid): uid for uid in known_ids}

    dest_dir = item_icon_assets.icons_dir()
    os.makedirs(dest_dir, exist_ok=True)

    result = {"imported": [], "unmatched": [], "corrupt": [], "skipped_unchanged": []}

    if not os.path.isdir(source_dir):
        print(f"Source folder does not exist: {source_dir}")
        return result

    for filename in sorted(os.listdir(source_dir)):
        stem, ext = os.path.splitext(filename)
        if ext.lower() not in item_icon_assets.SUPPORTED_EXTENSIONS:
            continue

        source_path = os.path.join(source_dir, filename)
        normalized = item_icon_assets.normalize_id(stem)
        unique_id = id_by_normalized.get(normalized)

        if unique_id is None:
            result["unmatched"].append(filename)
            continue

        if not _validate_image(source_path):
            result["corrupt"].append(filename)
            continue

        dest_path = os.path.join(dest_dir, f"{unique_id}{ext.lower()}")

        if os.path.isfile(dest_path) and _files_identical(source_path, dest_path):
            result["skipped_unchanged"].append(unique_id)
            continue

        shutil.copyfile(source_path, dest_path)
        result["imported"].append(unique_id)

    return result


def _files_identical(path_a: str, path_b: str) -> bool:
    if os.path.getsize(path_a) != os.path.getsize(path_b):
        return False
    with open(path_a, "rb") as fa, open(path_b, "rb") as fb:
        return fa.read() == fb.read()


def print_coverage_report():
    known_ids = [u["id"] for u in service.all_uniques()]
    report = item_icon_assets.coverage_report(known_ids)
    print("\nCoverage:")
    print(f"  Unique items: {report['total']}")
    print(f"  Images:       {report['with_image']}/{report['total']}")
    print(f"  Missing:      {report['missing']}")
    if report["missing_ids"]:
        print("  Missing item ids:")
        for uid in report["missing_ids"]:
            print(f"    - {uid}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help=f"Folder to import images from (default: {DEFAULT_SOURCE})",
    )
    args = parser.parse_args()

    result = import_icons(args.source)

    print(f"Imported: {len(result['imported'])}")
    for uid in result["imported"]:
        print(f"  + {uid}")

    if result["skipped_unchanged"]:
        print(f"Unchanged (already up to date): {len(result['skipped_unchanged'])}")

    if result["corrupt"]:
        print(f"Corrupt/unreadable (skipped): {len(result['corrupt'])}")
        for filename in result["corrupt"]:
            print(f"  ! {filename}")

    if result["unmatched"]:
        print(f"Unmatched (no known Unique with this name): {len(result['unmatched'])}")
        for filename in result["unmatched"]:
            print(f"  ? {filename}")

    print_coverage_report()


if __name__ == "__main__":
    main()
