# Log Cleaner — QGIS Plugin

**Version 2.2.0**

## Description

A development productivity tool for QGIS plugin developers. The plugin adds two animated buttons directly into the Message Log panel title bar: one clears the log tabs, the other removes the compiled Python bytecode cache of the current profile. No toolbar clutter, no menu entry.

## Features

- **Native integration**: Buttons placed in the Message Log dock title bar alongside the close button
- **Animated trash button**: clears all Message Log tabs recursively
- **Animated broom button**: removes `__pycache__` directories of the current profile
- **Resilient attachment**: retries title bar integration up to 20 times at 500 ms intervals
- **Background execution**: cache cleaning runs in a worker thread, the interface stays responsive
- **Explicit reporting**: files kept or locked are counted, shown in the status message and logged with their reason
- **QGIS-native implementation**: standard PyQt and QGIS APIs, no external dependency
- **Clean unload**: deterministic restoration of the native title bar when the plugin is disabled

## Cache cleaning scope

Scan roots are derived from the plugin location, so only the **current profile** is touched:

- `<profile>/python/` — plugins, expressions, `startup.py`
- `<profile>/processing/` — processing scripts

Directory junctions and symlinks are followed, which covers plugins mounted from a development repository. Walk loops are cut by `(device, inode)` identity. `.git`, `.hg`, `.svn` and `node_modules` are pruned.

### Safety rules

- Only files located **inside** a `__pycache__` directory are deleted
- Only `*.pyc`, `*.pyo` and interrupted-write leftovers (`*.pyc.<pid>`, `*.pyc.tmp`) are deleted
- A `.pyc` outside `__pycache__` (legacy sourceless layout) is **never** touched
- A `__pycache__` that is itself a symlink is never entered, it is reported instead
- Any other content (subdirectory, foreign file, symlinked file) is kept, counted and logged
- Read-only bytecode is deleted after clearing the read-only attribute
- A locked file is a real failure: it is reported as such and the operation is not declared successful

Status messages reflect the outcome without hiding anything:

```text
Cache: 12 files, 4 dirs
Cache: 3 files, 1 dirs, 2 kept (see Log Messages)
Cache: 0 files, 0 dirs, 1 locked (see Log Messages)
Cache: nothing to clean
```

Details go to the **Log Messages** panel under the `LogCleaner` tag, at WARNING level, in `key=value` form:

```text
log_cleaner.core.cache_cleaner - WARNING - cache_entries_kept cache_path=...\other\__pycache__ n_items=2 sample=notes.txt:not_bytecode
log_cleaner.core.cache_cleaner - WARNING - cache_file_locked path=...\m.cpython-312.pyc error=[WinError 32] ...
```

## Compatibility

- **QGIS versions**: 3.28 to 4.99 (as declared in `metadata.txt`)
- **PyQt**: PyQt5 and PyQt6, enum access guarded at import time
- **Python versions**: 3.9+
- **Operating systems**: Windows, Linux, macOS
- **Dependencies**: none

## Installation

1. Install the package from **Plugins > Manage and Install Plugins > Install from ZIP**, or copy the `log_cleaner` folder into your QGIS profile plugins directory
2. Enable the plugin via **Plugins > Manage and Install Plugins**
3. Open the Message Log panel: the trash and broom buttons sit in its title bar

## Architecture

```
log_cleaner/
├── __init__.py                     # Plugin entry point (classFactory)
├── clean_log.py                    # Orchestration, title bar, worker thread
├── core/
│   ├── base_cleaner.py             # Cleaner contract and CleanResult
│   ├── log_cleaner.py              # Message Log dock lookup and tab clearing
│   ├── cache_cleaner.py            # Bytecode deletion policy and reporting
│   ├── cache_paths.py              # Scan roots and __pycache__ enumeration
│   └── qgis_logging.py             # Logging bridge to the Log Messages panel
├── ui/
│   ├── animated_button.py          # Animated trash button (SVG compositing)
│   └── animated_broom_button.py    # Animated broom button (rotation)
├── assets/
│   ├── trash_base.svg              # Trash body
│   ├── trash_lid.svg               # Trash lid (animated)
│   └── broom.svg                   # Broom (animated)
├── metadata.txt                    # Plugin metadata
├── clean.svg                       # Plugin icon
├── LICENSE
└── README.md
```

The folder installed in the profile must be named `log_cleaner`, since it is the Python package name used by the internal imports.

### Core Components

**Cleaner / CleanResult** (`core/base_cleaner.py`)  
Common contract of the cleaners: `label`, `tooltip`, `icon_type`, `thread_safe`, `clean()`. `CleanResult` is a frozen dataclass carrying `success`, `removed`, `errors`, `paths_failed`, `paths_succeeded`, `elapsed_ms` and `message`.

**MessageLogCleaner** (`core/log_cleaner.py`)  
Message Log dock lookup by objectName or child scan, recursive tab content clearing. No dependency on `qgis.utils.iface`.

**PluginCacheCleaner** (`core/cache_cleaner.py`)  
Deletion policy and reporting: one outcome per `__pycache__`, read-only retry, separation between locked files and content kept on purpose, capped path lists.

**Scan roots and enumeration** (`core/cache_paths.py`)  
`resolve_scan_roots()` derives the profile roots from the plugin location and falls back to the parent directory with a WARNING when the layout is unexpected. `iter_cache_dirs()` walks the roots, follows junctions and cuts loops.

**CleanLogs** (`clean_log.py`)  
Orchestration: retry-based title bar attachment, custom `DockTitleBar` forwarding mouse events to Qt, worker thread for thread-safe cleaners, deterministic unload with native title bar restoration.

**AnimatedCleanButton / AnimatedBroomButton** (`ui/`)  
`QToolButton` subclasses compositing SVG layers with a sinusoidal animation.

## Tests

The cache logic depends only on the standard library, so its tests run without QGIS:

```bash
cd tests
python -m pytest . -q -p no:cacheprovider
```

24 tests cover scan root resolution, junction following, loop cutting, read-only files, locked files, foreign content, legacy `.pyc` protection and report bounds. Run them from the `tests` directory: from the repository root, pytest resolves the parent package and imports `__init__.py`, which requires QGIS.

The tests are development files and are not part of the published package.

## Development Standards

The plugin follows QGIS core development practices:

- Modular separation between business logic and UI components
- Strict PEP8 compliance with concise variable names
- Structured error handling with source, cause, and context reporting
- Proper resource cleanup with original state restoration
- Memory-safe reference management

