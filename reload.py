# Plugin reload script for QGIS console
import sys
for mod in list(sys.modules.keys()):
    if 'clean_log' in mod:
        del sys.modules[mod]

from clean_log import CleanLogs
from qgis.utils import iface

plugin = CleanLogs(iface)
plugin.initGui()
print("Plugin Clean Log reloaded")
