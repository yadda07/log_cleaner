import logging
import threading

from qgis.PyQt.QtCore import QObject, QTimer, QThread, Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from qgis.core import Qgis

from .core.base_cleaner import CleanResult
from .core.log_cleaner import find_message_log_dock, MessageLogCleaner
from .core.cache_cleaner import PluginCacheCleaner, invalidate_python_caches
from .core.qgis_logging import setup_logging
from .ui.animated_button import AnimatedCleanButton
from .ui.animated_broom_button import AnimatedBroomButton

_WARNING_LEVEL = Qgis.MessageLevel.Warning
_QUEUED = Qt.ConnectionType.QueuedConnection
_ATTACH_RESULT_ATTACHED = "attached"
_ATTACH_RESULT_FAILED = "failed"
_ATTACH_RESULT_RETRY = "retry"
_ATTACH_INTERVAL_MS = 500
_MAX_ATTACH_ATTEMPTS = 20
_TITLEBAR_OBJECT_NAME = "CleanLogTitleBar"
_WORKER_JOIN_MS = 5000

logger = logging.getLogger(__name__)


class CleanWorker(QObject):
    """Worker exécutant un Cleaner dans un thread séparé."""

    finished = pyqtSignal(object, object, object)

    def __init__(self, button, cleaner, cancel_event=None):
        super().__init__()
        self._button = button
        self._cleaner = cleaner
        self._cancel_event = cancel_event

    def run(self):
        try:
            if self._cancel_event is not None:
                try:
                    result = self._cleaner.clean(self._cancel_event)
                except TypeError:
                    result = self._cleaner.clean()
            else:
                result = self._cleaner.clean()
        except Exception as exc:
            result = CleanResult(success=False, message=f"Exception: {type(exc).__name__}: {exc}")
        self.finished.emit(self._button, self._cleaner, result)


class DockTitleBar(QWidget):
    """Titlebar personnalisée qui ne bloque pas le double-clic natif."""

    def mouseDoubleClickEvent(self, event):
        event.ignore()


class CleanLogs(QObject):
    """QGIS plugin for message log and Python bytecode cache cleanup."""

    def __init__(self, iface_ref):
        super().__init__()
        self.iface = iface_ref
        self.msg_dock = None
        self.close_btn = None
        self.original_titlebar = None
        self.titlebar_widget = None
        self._cleaners = []
        self._clean_buttons = []
        self._active_task = None
        self._busy_cleaners = set()
        self._button_slots = {}
        self._dock_visibility_conn = None
        self._attach_attempts = 0
        self._attach_timer = QTimer(self)
        self._attach_timer.timeout.connect(self._retry_add_button)
        self._attach_timer.setInterval(_ATTACH_INTERVAL_MS)

    @property
    def _cleaning_in_progress(self):
        return bool(self._busy_cleaners)

    @_cleaning_in_progress.setter
    def _cleaning_in_progress(self, value):
        if not value:
            self._busy_cleaners.clear()

    def initGui(self):
        setup_logging()
        self._attach_attempts = 0
        self._setup_cleaners()
        self._retry_add_button()

    def _setup_cleaners(self):
        mw = self.iface.mainWindow() if not self._cleaners else None
        if mw:
            self._cleaners = [MessageLogCleaner(mw), PluginCacheCleaner()]

    def _retry_add_button(self):
        if self._attach_attempts >= _MAX_ATTACH_ATTEMPTS:
            self._attach_timer.stop()
            logger.warning("dock_attach_exhausted attempts=%s", self._attach_attempts)
            return
        if self._add_button_to_dock() in (_ATTACH_RESULT_ATTACHED, _ATTACH_RESULT_FAILED):
            self._attach_timer.stop()
            return
        self._attach_attempts += 1
        if not self._attach_timer.isActive():
            self._attach_timer.start()

    def _add_button_to_dock(self):
        try:
            self._setup_cleaners()
            mw = self.iface.mainWindow()
            dock = find_message_log_dock(mw) if (self._cleaners and mw) else None
            if not dock:
                return _ATTACH_RESULT_RETRY
            self.msg_dock = dock
            self._connect_dock_visibility(dock)
            self._preserve_or_remove_titlebar()
            self.titlebar_widget = self._build_titlebar(self.msg_dock.windowTitle())
            self.msg_dock.setTitleBarWidget(self.titlebar_widget)
            return _ATTACH_RESULT_ATTACHED
        except (RuntimeError, AttributeError) as exc:
            self._fallback_error("CleanLogs._add_button_to_dock", f"Failed: {type(exc).__name__}", str(exc))
            return _ATTACH_RESULT_FAILED

    def _connect_dock_visibility(self, dock):
        if self._dock_visibility_conn is not None:
            return
        try:
            self._dock_visibility_conn = dock.visibilityChanged.connect(self._on_dock_visibility_changed)
        except (RuntimeError, AttributeError) as exc:
            logger.warning("dock_visibility_connect_failed error=%s reason=%s", type(exc).__name__, exc)

    def _on_dock_visibility_changed(self, visible):
        if not visible or self.msg_dock is None:
            return
        try:
            current = self.msg_dock.titleBarWidget()
            if current is None or current.objectName() != _TITLEBAR_OBJECT_NAME:
                self._attach_attempts = 0
                self._retry_add_button()
        except (RuntimeError, AttributeError) as exc:
            logger.debug("dock_visibility_check_skipped error=%s reason=%s", type(exc).__name__, exc)

    def _preserve_or_remove_titlebar(self):
        try:
            current = self.msg_dock.titleBarWidget()
        except (RuntimeError, AttributeError) as exc:
            logger.debug("titlebar_read_failed error=%s reason=%s", type(exc).__name__, exc)
            return
        if current and current.objectName() == _TITLEBAR_OBJECT_NAME:
            self.msg_dock.setTitleBarWidget(None)
            current.deleteLater()
        elif self.original_titlebar is None:
            self.original_titlebar = current

    def _dispose_clean_buttons(self):
        for old_btn in self._clean_buttons:
            try:
                if hasattr(old_btn, "abort_animation"):
                    old_btn.abort_animation()
                old_btn.clicked.disconnect()
            except (RuntimeError, TypeError) as exc:
                logger.debug("button_disconnect_noop reason=%s", exc)
            old_btn.deleteLater()
        self._clean_buttons = []
        self._button_slots = {}

    def _build_titlebar(self, dock_title):
        self._dispose_clean_buttons()
        titlebar_widget = DockTitleBar()
        titlebar_widget.setObjectName(_TITLEBAR_OBJECT_NAME)
        layout = QHBoxLayout(titlebar_widget)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        title_label = QLabel(dock_title)
        title_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(title_label)
        layout.addStretch()
        for cleaner in self._cleaners:
            btn = self._create_cleaner_button(cleaner)
            layout.addWidget(btn)
            self._clean_buttons.append(btn)
        self.close_btn = self._create_close_button()
        layout.addWidget(self.close_btn)
        return titlebar_widget

    def _create_cleaner_button(self, cleaner):
        btn_cls = AnimatedCleanButton if cleaner.icon_type == "trash" else AnimatedBroomButton
        btn = btn_cls(accent_color="#8CC63F" if cleaner.icon_type == "trash" else "#F5A623")
        btn.setToolTip(cleaner.tooltip)
        def _slot(_checked=False):
            self._execute_clean(btn, cleaner)
        btn.clicked.connect(_slot)
        self._button_slots[btn] = _slot
        return btn

    def _create_close_button(self):
        btn = QPushButton("x")
        btn.setToolTip("Close panel")
        btn.setFlat(True)
        btn.setMaximumSize(24, 24)
        btn.setStyleSheet(
            "QPushButton { font-size: 14px; font-weight: bold; border: none; background: transparent; }"
            " QPushButton:hover { color: #3daee9; }"
        )
        btn.clicked.connect(self.msg_dock.hide)
        return btn

    def _execute_clean(self, button, cleaner):
        key = cleaner.label
        logger.debug("_execute_clean START label=%s thread_safe=%s", key, cleaner.thread_safe)
        if key in self._busy_cleaners:
            logger.debug("_execute_clean SKIP busy label=%s", key)
            return
        self._busy_cleaners.add(key)
        button.start_animation()
        if not cleaner.thread_safe:
            self._run_sync_clean(button, cleaner)
            return
        self._start_worker(button, cleaner)

    def _run_sync_clean(self, button, cleaner):
        try:
            result = cleaner.clean()
        except Exception as exc:
            result = CleanResult(success=False, message=f"Exception: {type(exc).__name__}: {exc}")
        self._on_clean_finished(button, cleaner, result)

    def _start_worker(self, button, cleaner):
        cancel_event = threading.Event()
        thread = QThread(self)
        worker = CleanWorker(button, cleaner, cancel_event)
        worker.moveToThread(thread)
        thread.started.connect(worker.run, _QUEUED)
        worker.finished.connect(self._on_clean_finished, _QUEUED)
        worker.finished.connect(thread.quit, _QUEUED)
        thread.finished.connect(worker.deleteLater, _QUEUED)
        thread.finished.connect(thread.deleteLater, _QUEUED)
        thread.finished.connect(self._clear_active_task, _QUEUED)
        self._active_task = (thread, worker, cancel_event)
        thread.start()

    def _clear_active_task(self):
        self._active_task = None

    def _on_clean_finished(self, button, cleaner, result):
        self._busy_cleaners.discard(cleaner.label)
        if cleaner.icon_type == "broom":
            invalidate_python_caches()
        try:
            button.stop_animation()
        except RuntimeError as exc:
            logger.debug("button_gone stage=clean_finished reason=%s", exc)
        prefix = f"{cleaner.label}:"
        status_text = result.message if result.message.startswith(prefix) else f"{prefix} {result.message}"
        if not result.success:
            logger.warning("_on_clean_finished label=%s failed msg=%s", cleaner.label, result.message)
            self._fallback_error("CleanLogs._execute_clean", status_text)
            return
        logger.debug("_on_clean_finished label=%s elapsed_ms=%s", cleaner.label, result.elapsed_ms)
        status_bar = self.iface.statusBarIface()
        if status_bar:
            status_bar.showMessage(status_text, 3000)
        else:
            logger.warning("status_bar_unavailable msg=%s", status_text)

    def _stop_active_worker(self):
        if self._active_task is None:
            return
        thread, worker, cancel_event = self._active_task
        cancel_event.set()
        try:
            worker.finished.disconnect(self._on_clean_finished)
        except (RuntimeError, TypeError) as exc:
            logger.debug("worker_disconnect_noop stage=unload reason=%s", exc)
        try:
            if thread.isRunning():
                thread.quit()
                if not thread.wait(_WORKER_JOIN_MS):
                    logger.warning("unload_thread_join_timeout ms=%s", _WORKER_JOIN_MS)
        except RuntimeError as exc:
            logger.warning("unload_thread_stop_failed error=%s reason=%s", type(exc).__name__, exc)
        self._active_task = None

    def unload(self):
        self._attach_timer.stop()
        self._disconnect_dock_visibility()
        self._stop_active_worker()
        self._busy_cleaners.clear()
        try:
            if self.msg_dock is not None:
                current_titlebar = self.msg_dock.titleBarWidget()
                self.msg_dock.setTitleBarWidget(self.original_titlebar)
                if current_titlebar and current_titlebar.objectName() == _TITLEBAR_OBJECT_NAME:
                    current_titlebar.deleteLater()
        except (RuntimeError, AttributeError) as exc:
            self._fallback_error("CleanLogs.unload", f"Failed: {type(exc).__name__}", str(exc))
        finally:
            self._dispose_clean_buttons()
            self._cleaners = []
            self.close_btn = None
            self.msg_dock = None
            self.original_titlebar = None
            self.titlebar_widget = None
            self._attach_attempts = 0

    def _disconnect_dock_visibility(self):
        if self._dock_visibility_conn is None or self.msg_dock is None:
            return
        try:
            self.msg_dock.visibilityChanged.disconnect(self._dock_visibility_conn)
        except (RuntimeError, TypeError, AttributeError) as exc:
            logger.debug("dock_visibility_disconnect_noop error=%s reason=%s", type(exc).__name__, exc)
        self._dock_visibility_conn = None

    def _fallback_error(self, source, cause, context=""):
        msg = f"[{source}] {cause}" + (f" | {context}" if context else "")
        try:
            message_bar = self.iface.messageBar()
            if message_bar:
                message_bar.pushMessage("Clean Log", msg, level=_WARNING_LEVEL, duration=4)
                logger.warning("fallback_error_displayed msg=%s", msg)
                return
        except (RuntimeError, AttributeError) as exc:
            logger.debug("message_bar_unavailable error=%s reason=%s", type(exc).__name__, exc)
        logger.warning("LogCleaner_CRITICAL %s", msg)
