import logging
from functools import partial

from qgis.PyQt.QtCore import QObject, QTimer, QThread, Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from qgis.core import Qgis

from .core.base_cleaner import CleanResult
from .core.log_cleaner import find_message_log_dock, MessageLogCleaner
from .core.cache_cleaner import PluginCacheCleaner
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

    finished = pyqtSignal(object)

    def __init__(self, cleaner):
        super().__init__()
        self._cleaner = cleaner

    def run(self):
        try:
            result = self._cleaner.clean()
        except Exception as exc:
            result = CleanResult(
                success=False,
                message=f"Exception: {type(exc).__name__}: {exc}"
            )
        self.finished.emit(result)


class DockTitleBar(QWidget):
    """Titlebar personnalisée qui ne bloque pas le double-clic natif."""

    def mouseDoubleClickEvent(self, event):
        event.ignore()


class CleanLogs(QObject):
    """QGIS plugin for message log cleanup.

    Integrates an animated clear button directly into the Message Log dock title bar,
    providing quick access to log cleanup functionality for developers.
    """

    def __init__(self, iface_ref):
        """Initialize plugin instance."""
        super().__init__()
        self.iface = iface_ref
        self.msg_dock = None
        self._cleaners = []
        self._clean_buttons = []
        self._active_task = None  # (thread, worker) ou None
        self.close_btn = None
        self.original_titlebar = None
        self.titlebar_widget = None
        self._attach_attempts = 0
        self._attach_timer = QTimer(self)
        self._attach_timer.timeout.connect(self._retry_add_button)
        self._attach_timer.setInterval(_ATTACH_INTERVAL_MS)
        self._cleaning_in_progress = False
        self._button_slots = {}
        self._dock_visibility_conn = None

    def initGui(self):
        """Initialize plugin GUI components."""
        setup_logging()
        self._attach_attempts = 0
        self._setup_cleaners()
        self._retry_add_button()

    def _setup_cleaners(self):
        if self._cleaners:
            return
        mw = self.iface.mainWindow()
        if not mw:
            return
        self._cleaners = [
            MessageLogCleaner(mw),
            PluginCacheCleaner(),
        ]

    def _retry_add_button(self):
        if self._attach_attempts >= _MAX_ATTACH_ATTEMPTS:
            self._attach_timer.stop()
            self._fallback_error(
                "CleanLogs._add_button_to_dock",
                "Failed to add button after multiple attempts"
            )
            return
        attach_result = self._add_button_to_dock()
        if attach_result == _ATTACH_RESULT_ATTACHED:
            self._attach_timer.stop()
            return
        if attach_result == _ATTACH_RESULT_FAILED:
            self._attach_timer.stop()
            return
        self._attach_attempts += 1
        if not self._attach_timer.isActive():
            self._attach_timer.start()

    def _add_button_to_dock(self):
        """Add custom buttons to Message Log dock title bar."""
        try:
            self._setup_cleaners()
            if not self._cleaners:
                return _ATTACH_RESULT_RETRY

            mw = self.iface.mainWindow()
            if not mw:
                return _ATTACH_RESULT_RETRY

            dock = find_message_log_dock(mw)
            if not dock:
                return _ATTACH_RESULT_RETRY

            self.msg_dock = dock

            # Connect visibilityChanged for reinjection (C3 fix)
            if self._dock_visibility_conn is None:
                try:
                    self._dock_visibility_conn = dock.visibilityChanged.connect(
                        self._on_dock_visibility_changed
                    )
                except (RuntimeError, AttributeError) as exc:
                    logger.warning(
                        "dock_visibility_connect_failed error=%s reason=%s "
                        "consequence=titlebar_reinjection_disabled",
                        type(exc).__name__, exc
                    )

            # Save original titlebar for restoration
            self.original_titlebar = self._remove_plugin_titlebar()

            # Get dock title
            dock_title = self.msg_dock.windowTitle()

            # Create custom titlebar container
            titlebar_widget = self._build_titlebar(dock_title)

            # Apply custom titlebar
            self.titlebar_widget = titlebar_widget
            self.msg_dock.setTitleBarWidget(self.titlebar_widget)
            return _ATTACH_RESULT_ATTACHED

        except (RuntimeError, AttributeError) as e:
            self._fallback_error(
                "CleanLogs._add_button_to_dock",
                f"Failed to add button: {type(e).__name__}",
                str(e)
            )
            return _ATTACH_RESULT_FAILED

    def _on_dock_visibility_changed(self, visible):
        """Réinjecte le bouton si QGIS a restauré le titlebar natif (C3)."""
        if not visible:
            return
        if self.msg_dock is None:
            return
        try:
            current = self.msg_dock.titleBarWidget()
            if current is None or current.objectName() != _TITLEBAR_OBJECT_NAME:
                self._attach_attempts = 0
                self._retry_add_button()
        except (RuntimeError, AttributeError) as exc:
            logger.debug(
                "dock_visibility_check_skipped error=%s reason=%s",
                type(exc).__name__, exc
            )

    def _remove_plugin_titlebar(self):
        try:
            current_titlebar = self.msg_dock.titleBarWidget()
        except (RuntimeError, AttributeError) as exc:
            logger.debug(
                "titlebar_read_failed error=%s reason=%s",
                type(exc).__name__, exc
            )
            return None
        if current_titlebar and current_titlebar.objectName() == _TITLEBAR_OBJECT_NAME:
            self.msg_dock.setTitleBarWidget(None)
            current_titlebar.deleteLater()
            return None
        return current_titlebar

    def _build_titlebar(self, dock_title):
        for old_btn in self._clean_buttons:
            try:
                old_btn.clicked.disconnect()
            except TypeError as exc:
                logger.debug(
                    "button_disconnect_noop stage=titlebar_rebuild reason=%s", exc
                )
            old_btn.deleteLater()
        self._clean_buttons = []
        self._button_slots = {}
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
            if cleaner.icon_type == "trash":
                btn = AnimatedCleanButton(accent_color="#8CC63F")
            else:
                btn = AnimatedBroomButton(accent_color="#F5A623")
            btn.setToolTip(cleaner.tooltip)
            slot = partial(self._on_button_clicked, btn, cleaner)
            btn.clicked.connect(slot)
            self._button_slots[btn] = slot
            layout.addWidget(btn)
            self._clean_buttons.append(btn)
        self.close_btn = QPushButton("x")
        self.close_btn.setToolTip("Close panel")
        self.close_btn.setFlat(True)
        self.close_btn.setMaximumSize(24, 24)
        self.close_btn.setStyleSheet(
            "QPushButton { font-size: 14px; font-weight: bold; border: none; background: transparent; }"
            " QPushButton:hover { color: #3daee9; }"
        )
        self.close_btn.clicked.connect(self.msg_dock.hide)
        layout.addWidget(self.close_btn)
        return titlebar_widget

    def _on_button_clicked(self, button, cleaner, checked=False):
        """Slot découplé du lambda (évite fuite de référence circulaire)."""
        self._execute_clean(button, cleaner)

    def _execute_clean(self, button, cleaner):
        """Execute cleanup operation and trigger animation."""
        logger.debug(
            "_execute_clean START label=%s thread_safe=%s",
            cleaner.label, cleaner.thread_safe
        )
        if self._cleaning_in_progress:
            logger.debug("_execute_clean SKIP cleaning_in_progress")
            return
        self._cleaning_in_progress = True
        button.start_animation()
        if not cleaner.thread_safe:
            try:
                result = cleaner.clean()
            except Exception as exc:
                result = CleanResult(
                    success=False,
                    message=f"Exception: {type(exc).__name__}: {exc}"
                )
            self._on_clean_finished(button, cleaner, result)
            return

        thread = QThread()
        worker = CleanWorker(cleaner)
        worker.moveToThread(thread)

        thread.started.connect(worker.run, _QUEUED)
        worker.finished.connect(thread.quit, _QUEUED)
        worker.finished.connect(
            lambda result, b=button, c=cleaner: self._on_clean_finished(b, c, result),
            _QUEUED
        )
        thread.finished.connect(
            lambda t=thread, w=worker: self._cleanup_thread(t, w),
            _QUEUED
        )

        self._active_task = (thread, worker)
        thread.start()

    def _on_clean_finished(self, button, cleaner, result):
        """Appelé dans le GUI thread quand le nettoyage termine."""
        try:
            button.stop_animation()
            button.setEnabled(True)
        except RuntimeError as exc:
            logger.debug(
                "button_gone stage=clean_finished reason=%s", exc
            )
        if result.success:
            logger.debug(
                "_on_clean_finished label=%s success=%s elapsed_ms=%s",
                cleaner.label, result.success, result.elapsed_ms
            )
            status_bar = self.iface.statusBarIface()
            if status_bar:
                status_bar.showMessage(
                    f"{cleaner.label}: {result.message}", 3000
                )
            else:
                logger.warning("Status bar not available")
        else:
            logger.warning(
                "_on_clean_finished label=%s failed msg=%s elapsed_ms=%s",
                cleaner.label, result.message, result.elapsed_ms
            )
            self._fallback_error(
                "CleanLogs._execute_clean",
                f"{cleaner.label} cleanup failed: {result.message}"
            )
        self._cleaning_in_progress = False

    def _cleanup_thread(self, thread, worker):
        """Nettoie le thread et le worker après exécution (appelé depuis thread.finished)."""
        try:
            worker.deleteLater()
        except RuntimeError as exc:
            logger.debug("worker_already_deleted stage=cleanup_thread reason=%s", exc)
        try:
            thread.deleteLater()
        except RuntimeError as exc:
            logger.debug("thread_already_deleted stage=cleanup_thread reason=%s", exc)
        if self._active_task is not None:
            t, w = self._active_task
            if t is thread and w is worker:
                self._active_task = None

    def unload(self):
        """Clean up plugin resources on unload."""
        self._attach_timer.stop()

        # Disconnect dock visibility signal
        if self._dock_visibility_conn is not None and self.msg_dock is not None:
            try:
                self.msg_dock.visibilityChanged.disconnect(self._dock_visibility_conn)
            except (RuntimeError, TypeError, AttributeError) as exc:
                logger.debug(
                    "dock_visibility_disconnect_noop error=%s reason=%s",
                    type(exc).__name__, exc
                )
            self._dock_visibility_conn = None

        # Stop active worker gracefully
        if self._active_task is not None:
            thread, _ = self._active_task
            try:
                if thread.isRunning():
                    thread.quit()
                    if not thread.wait(_WORKER_JOIN_MS):
                        logger.warning("unload_thread_join_timeout ms=%s", _WORKER_JOIN_MS)
                        thread.terminate()
                        thread.wait(1000)
            except RuntimeError as exc:
                logger.warning(
                    "unload_thread_stop_failed error=%s reason=%s",
                    type(exc).__name__, exc
                )
            finally:
                try:
                    thread.deleteLater()
                except RuntimeError as exc:
                    logger.debug("thread_already_deleted stage=unload reason=%s", exc)
                self._active_task = None

        self._cleaning_in_progress = False

        try:
            if self.msg_dock is not None:
                current_titlebar = self.msg_dock.titleBarWidget()
                self.msg_dock.setTitleBarWidget(self.original_titlebar)
                if current_titlebar and current_titlebar.objectName() == _TITLEBAR_OBJECT_NAME:
                    current_titlebar.deleteLater()
        except (RuntimeError, AttributeError) as e:
            self._fallback_error(
                "CleanLogs.unload",
                f"Failed to restore title bar: {type(e).__name__}",
                str(e)
            )
        finally:
            for btn in self._clean_buttons:
                try:
                    btn.clicked.disconnect()
                except TypeError as exc:
                    logger.debug(
                        "button_disconnect_noop stage=unload reason=%s", exc
                    )
                btn.deleteLater()
            self._clean_buttons = []
            self._button_slots = {}
            self._cleaners = []
            self.close_btn = None
            self.msg_dock = None
            self.original_titlebar = None
            self.titlebar_widget = None
            self._attach_attempts = 0

    def _fallback_error(self, source, cause, context=""):
        """Display structured error message to user; never silent."""
        msg = f"[{source}] {cause}"
        if context:
            msg += f" | {context}"
        try:
            message_bar = self.iface.messageBar()
            if message_bar:
                message_bar.pushMessage(
                    "Clean Log",
                    msg,
                    level=_WARNING_LEVEL,
                    duration=4
                )
                logger.warning("fallback_error_displayed msg=%s", msg)
                return
        except (RuntimeError, AttributeError) as exc:
            logger.debug(
                "message_bar_unavailable error=%s reason=%s",
                type(exc).__name__, exc
            )
        # Fallback absolu
        logger.warning("LogCleaner_CRITICAL %s", msg)
