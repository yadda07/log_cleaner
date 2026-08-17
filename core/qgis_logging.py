import logging
import sys

from qgis.core import QgsMessageLog, Qgis


try:
    _QGIS_INFO = Qgis.MessageLevel.Info
    _QGIS_WARNING = Qgis.MessageLevel.Warning
    _QGIS_CRITICAL = Qgis.MessageLevel.Critical
except AttributeError:
    _QGIS_INFO = Qgis.Info
    _QGIS_WARNING = Qgis.Warning
    _QGIS_CRITICAL = Qgis.Critical

_LEVEL_MAP = {
    logging.DEBUG: _QGIS_INFO,
    logging.INFO: _QGIS_INFO,
    logging.WARNING: _QGIS_WARNING,
    logging.ERROR: _QGIS_CRITICAL,
    logging.CRITICAL: _QGIS_CRITICAL,
}


class QgisLogHandler(logging.Handler):
    """Handler Python logging vers le panneau Message Log de QGIS."""

    def __init__(self, tag="LogCleaner", level=logging.DEBUG):
        super().__init__(level)
        self._tag = tag

    def emit(self, record):
        try:
            msg = self.format(record)
            qgis_level = _LEVEL_MAP.get(record.levelno, _QGIS_INFO)
            QgsMessageLog.logMessage(msg, self._tag, level=qgis_level)
        except Exception:
            # Dernier recours : ne jamais perdre le log
            try:
                sys.stderr.write(f"LogCleaner_FALLBACK {record.getMessage()}\n")
            except Exception:
                pass


def setup_logging():
    """Configure le logger racine du plugin pour écrire dans le Message Log QGIS."""
    logger = logging.getLogger("log_cleaner")
    if any(isinstance(h, QgisLogHandler) for h in logger.handlers):
        return
    handler = QgisLogHandler()
    handler.setFormatter(logging.Formatter("%(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
