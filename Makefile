# Makefile for Clean Log QGIS Plugin

PLUGINNAME = clean_log
PY_FILES = clean_log.py __init__.py
EXTRAS = metadata.txt clean.png

default: zip

compile:
	@echo "No compilation needed for this plugin"

zip: 
	zip -r $(PLUGINNAME).zip $(PY_FILES) $(EXTRAS)
	@echo "Plugin packaged as $(PLUGINNAME).zip"

clean:
	rm -f $(PLUGINNAME).zip
	@echo "Cleaned package files"

install: zip
	cp $(PLUGINNAME).zip ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/
	@echo "Plugin installed"

.PHONY: compile zip clean install
