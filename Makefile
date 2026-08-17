# Makefile for Log Cleaner QGIS Plugin

PLUGINNAME = log_cleaner
VERSION = $(shell grep -m1 '^version=' metadata.txt | cut -d= -f2)
PY_FILES = clean_log.py __init__.py core ui
EXTRAS = metadata.txt clean.svg assets LICENSE README.md
BUILD_DIR = build/$(PLUGINNAME)
ZIPNAME = $(PLUGINNAME)-$(VERSION).zip

# OS-aware install dir
ifeq ($(OS),Windows_NT)
	INSTALL_DIR = $(USERPROFILE)/AppData/Roaming/QGIS/QGIS4/profiles/default/python/plugins/$(PLUGINNAME)
else
	INSTALL_DIR = $(HOME)/.local/share/QGIS/QGIS4/profiles/default/python/plugins/$(PLUGINNAME)
endif

default: zip

compile:
	@echo "No compilation needed for this plugin"

stage:
	rm -rf build
	mkdir -p $(BUILD_DIR) dist
	cp -r $(PY_FILES) $(EXTRAS) $(BUILD_DIR)/
	find $(BUILD_DIR) -type d -name '__pycache__' -prune -exec rm -rf {} +
	find $(BUILD_DIR) -type f -name '*.py[co]' -delete

zip: stage
	rm -f dist/$(ZIPNAME)
	cd build && zip -r ../dist/$(ZIPNAME) $(PLUGINNAME)
	@echo "Plugin packaged as dist/$(ZIPNAME)"

clean:
	rm -rf build dist
	@echo "Cleaned build artifacts"

install: stage
	mkdir -p $(INSTALL_DIR)
	cp -r $(BUILD_DIR)/. $(INSTALL_DIR)/
	@echo "Plugin installed in $(INSTALL_DIR)"

.PHONY: compile stage zip clean install
