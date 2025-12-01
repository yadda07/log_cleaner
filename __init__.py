from .clean_log import CleanLogs

def classFactory(iface):
    return CleanLogs(iface)
