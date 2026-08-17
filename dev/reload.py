# Plugin reload script for QGIS console — DEV ONLY
import sys
import os
import shutil

try:
    from qgis.utils import plugins, iface
except ImportError:
    print("ERROR: This script must be run inside a QGIS Python console")
    sys.exit(1)

if iface is None:
    print("ERROR: iface is None — not in a QGIS context")
    sys.exit(1)

# 1. Unload ancien plugin et restaure la titlebar
try:
    old = plugins.get('log_cleaner')
    if old:
        old.unload()
        print("Old plugin unloaded")
except Exception as e:
    print(f"Unload error: {e}")

# 2. Supprime recursivement les __pycache__ du plugin log_cleaner
plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print(f"plugin_dir={plugin_dir}")

for root, dirs, _files in os.walk(plugin_dir, topdown=False):
    for d in dirs:
        if d != '__pycache__':
            continue
        p = os.path.join(root, d)
        # Garde-fou : vérifier que la cible est bien sous plugin_dir
        try:
            if os.path.commonpath([p, plugin_dir]) != plugin_dir:
                print(f"SKIP out-of-tree {p}")
                continue
        except ValueError:
            print(f"SKIP invalid path {p}")
            continue
        try:
            shutil.rmtree(p)
            print(f"Removed {p}")
        except Exception as e:
            print(f"Failed {p}: {e}")

# 3. Supprime les modules du cache Python (strict : commence par 'log_cleaner.')
for mod in list(sys.modules.keys()):
    if mod == 'log_cleaner' or mod.startswith('log_cleaner.'):
        del sys.modules[mod]

# 4. Reimporte et register
try:
    from log_cleaner import CleanLogs
    plugin = CleanLogs(iface)
    plugin.initGui()
    plugins['log_cleaner'] = plugin
    print("Plugin Clean Log reloaded and registered")
except Exception as e:
    print(f"Reload failed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
