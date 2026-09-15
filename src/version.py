"""Single canonical version source for Diablo 4 Companion.

Windows Product Phase W4 -- Versioning. ``__version__`` below is the ONE
place a human edits to bump the app's version (semantic versioning,
e.g. "1.0.0"). Everything else derives from this value mechanically --
there is no second hardcoded copy anywhere in the project:

- The Python app imports ``__version__`` directly from this module.
  This works identically whether running from source or frozen by
  PyInstaller, because this is a normal ``src/`` module compiled into
  the app's PYZ archive like any other application code -- NOT a
  bundled data file read at runtime. That deliberately sidesteps the
  PyInstaller onedir ``_internal/`` data-layout surprise already hit
  once in this project (see PROJECT_STATUS.md's W3 section, where
  ``builds/*.json`` -- bundled via ``datas`` -- ended up under
  ``_internal\\builds\\`` instead of beside the exe). A plain imported
  module has no such ambiguity: PyInstaller's ``Analysis`` follows the
  ``from src.version import __version__`` import graph itself, so no
  change to ``diablo4companion.spec`` is needed at all.
- ``.github/workflows/windows-build.yml`` reads this same value with a
  one-line ``python -c "from src.version import __version__; ..."``
  step and passes it into the Inno Setup compile step via the
  ``/DMyAppVersion=...`` command-line define.
- ``installer/diablo4companion.iss`` receives the version through that
  ``/D`` define, falling back to this exact same value as a hardcoded
  default only if the script is ever compiled standalone without the
  define (e.g. an ad hoc local ``ISCC`` invocation).
"""

__version__ = "1.0.0"
