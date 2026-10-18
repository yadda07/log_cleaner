import logging

from qgis.PyQt.QtCore import QCoreApplication, QObject, QThread, Qt, pyqtSignal
from qgis.core import QgsMessageLog, Qgis


_QGIS_INFO = Qgis.MessageLevel.Info
_QGIS_WARNING = Qgis.MessageLevel.Warning
_QGIS_CRITICAL = Qgis.MessageLevel.Critical
_QUEUED = Qt.ConnectionType.QueuedConnection

_LEVEL_MAP = {
    logging.DEBUG: _QGIS_INFO,
    logging.INFO: _QGIS_INFO,
    logging.WARNING: _QGIS_WARNING,
    logging.ERROR: _QGIS_CRITICAL,
    logging.CRITICAL: _QGIS_CRITICAL,
}


class _LogBridge(QObject):
    """Relais Qt garantissant l'appel à QgsMessageLog sur le thread principal."""

    record_ready = pyqtSignal(object, str, object)

    def __init__(self, handler, parent=None):
        super().__init__(parent)
        self._handler = handler
        self.record_ready.connect(self._write_main_thread, _QUEUED)

    def _write_main_thread(self, record, msg, qgis_level):
        try:
            QgsMessageLog.logMessage(msg, self._handler.tag, level=qgis_level)
        except Exception:
            self._handler.handleError(record)


class QgisLogHandler(logging.Handler):
    """Handler Python logging vers le panneau Message Log de QGIS."""

    def __init__(self, tag="LogCleaner", level=logging.DEBUG):
        super().__init__(level)
        self.tag = tag
        self._bridge = _LogBridge(self)

    def emit(self, record):
        try:
            msg = self.format(record)
            qgis_level = _LEVEL_MAP.get(record.levelno, _QGIS_INFO)
            app = QCoreApplication.instance()
            if app is not None and QThread.currentThread() is not app.thread():
                self._bridge.record_ready.emit(record, msg, qgis_level)
            else:
                QgsMessageLog.logMessage(msg, self.tag, level=qgis_level)
        except Exception:
            self.handleError(record)


def setup_logging():
    """Configure le logger racine du plugin pour écrire dans le Message Log QGIS."""
    logger = logging.getLogger("log_cleaner")
    if any(isinstance(h, QgisLogHandler) for h in logger.handlers):
        return
    handler = QgisLogHandler()
    handler.setFormatter(logging.Formatter("%(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
