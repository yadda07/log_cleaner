from qgis.core import QgsMessageLog, Qgis

try:
    from .clean_log import CleanLogs
except Exception as exc:
    QgsMessageLog.logMessage(
        f"LogCleaner classFactory import_failed error={type(exc).__name__}: {exc}",
        "LogCleaner",
        level=Qgis.MessageLevel.Critical
    )
    raise


def classFactory(iface):
    try:
        return CleanLogs(iface)
    except Exception as exc:
        QgsMessageLog.logMessage(
            f"LogCleaner classFactory init_failed error={type(exc).__name__}: {exc}",
            "LogCleaner",
            level=Qgis.MessageLevel.Critical
        )
        raise
