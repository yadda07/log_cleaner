# Clean Log QGIS Plugin

## Description

A development productivity tool for QGIS plugin developers. This plugin integrates a clear button directly into the Message Log panel title bar, enabling rapid log cleanup during debugging and testing workflows without cluttering the main toolbar.

## Features

- **Native integration**: Button placed in the Message Log dock title bar alongside the close button
- **One-click operation**: Clears all message log tabs instantly
- **QGIS-native implementation**: Built using standard PyQt and QGIS APIs without external dependencies
- **Clean unload**: Restores original title bar when plugin is disabled

## Compatibility

- **QGIS versions**: 3.22+
- **Python versions**: 3.9+
- **PyQt**: Compatible with both PyQt5 and PyQt6
- **Operating systems**: Windows, Linux, macOS
- **Dependencies**: None

## Installation

1. Copy the `clean_log_c` folder to your QGIS plugins directory
2. Enable the plugin via **Plugins > Manage and Install Plugins**
3. Open the Message Log panel to see the integrated clear button

## Architecture

```
clean_log_c/
├── __init__.py          # Plugin entry point
├── clean_log.py         # Core implementation
├── metadata.txt         # Plugin metadata
├── clean.png            # Button icon
└── README.md            # Documentation
```

### Core Components

**MessageLogCleaner**  
Static utility class handling dock location and content clearing logic.

**CleanLogs**  
Main plugin class managing initialization, title bar customization, and cleanup.

### Key Methods

- `find_message_log_dock()`: Locates the Message Log QDockWidget by objectName or title
- `_add_button_to_dock()`: Creates custom title bar with label, clear button, and close button
- `clear_log()`: Iterates through all log tabs and clears content
- `unload()`: Restores original title bar widget

## Development Standards

The plugin follows QGIS core development practices:

- Modular separation between business logic and UI components
- Strict PEP8 compliance with concise variable names
- Structured error handling with source, cause, and context reporting
- Proper resource cleanup with original state restoration
- Memory-safe reference management

