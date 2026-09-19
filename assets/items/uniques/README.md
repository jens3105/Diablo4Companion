# Unique item icons (user-provided)

This folder is where **you** can put your own Unique item icon images
so Diablo4Companion's Unique Drop Locations page shows them. Companion
never downloads, scrapes, or extracts these itself - see
`src/item_icon_assets.py` and `src/unique_data.py`'s module docstrings
for why.

This folder is gitignored - files you put here stay on your own
machine and are never committed or published.

## How to add images

Easiest: run the import helper, which matches filenames to the right
item automatically:

```
python3 scripts/import_item_icons.py
```

By default it looks in `~/Downloads/Diablo4Companion-ItemIcons/` and
copies anything it recognizes into this folder with the correct name.
Run `python3 scripts/import_item_icons.py --help` for options
(including a different source folder).

Or manually: drop a `.png`, `.jpg`, `.jpeg`, or `.webp` file directly
into this folder, named after the item, e.g.:

```
assets/items/uniques/harlequin_crest.png
assets/items/uniques/windforce.png
```

Diablo4Companion checks this folder automatically at startup for a
file whose name matches each Unique's internal id (see
`src/unique_data.py`) - no restart-free "hot reload" needed, but no
code changes needed either. If a Unique has no matching file here, the
app shows a plain "No Image" placeholder for it - this is expected and
harmless, not an error.
