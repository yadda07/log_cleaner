import time

from qgis.PyQt.QtWidgets import (
    QWidget, QDockWidget, QTabWidget, QTextEdit, QListWidget, QTreeWidget,
    QAbstractItemView, QApplication, QPlainTextEdit
)

from .base_cleaner import Cleaner, CleanResult


try:
    from qgis.gui import QgsMessageLogViewer
except Exception:
    QgsMessageLogViewer = None


def find_message_log_dock(main_window):
    """Locate the QGIS Message Log dock widget, including when floating."""
    if not main_window:
        return None

    for name in ("MessageLog", "MessageLogDock"):
        message_log_dock = main_window.findChild(QDockWidget, name)
        if message_log_dock:
            return message_log_dock

    for dock in main_window.findChildren(QDockWidget):
        if dock.findChild(QTabWidget, "MessageLog"):
            return dock
        if QgsMessageLogViewer is not None:
            if dock.findChild(QgsMessageLogViewer):
                return dock

    # Fallback : dock flottant (plus enfant de mainWindow)
    app = QApplication.instance()
    if app:
        for top_widget in app.topLevelWidgets():
            if not isinstance(top_widget, QDockWidget):
                continue
            if top_widget.objectName() in ("MessageLog", "MessageLogDock"):
                return top_widget
            if top_widget.findChild(QTabWidget, "MessageLog"):
                return top_widget
            if QgsMessageLogViewer is not None:
                if top_widget.findChild(QgsMessageLogViewer):
                    return top_widget

    return None


def find_message_log_widget(main_window):
    """Locate the Message Log content widget."""
    if not main_window:
        return None

    # 1. Par nom exact QTabWidget
    for name in ("MessageLog", "MessageLogDock"):
        w = main_window.findChild(QTabWidget, name)
        if w:
            return w

    dock = find_message_log_dock(main_window)
    if not dock:
        return None

    # 2. Par type QgsMessageLogViewer si disponible
    if QgsMessageLogViewer is not None:
        viewer = dock.findChild(QgsMessageLogViewer)
        if viewer:
            return viewer

    # 3. Par nom exact dans le dock
    for w in dock.findChildren(QTabWidget):
        if w.objectName() == "MessageLog":
            return w

    # 4. Par nom partiel (QGIS 4 peut avoir renommé)
    for w in dock.findChildren(QWidget):
        obj_name = w.objectName() or ""
        if "MessageLog" in obj_name or "messageLog" in obj_name:
            return w

    # 5. Par duck typing : méthode clearMessages
    for w in dock.findChildren(QWidget):
        if hasattr(w, 'clearMessages') and callable(getattr(w, 'clearMessages')):
            return w

    # 6. Dernier recours : QTextEdit / QPlainTextEdit dans le dock
    # (le Message Log est souvent un QTextEdit sous-jacent)
    for cls in (QTextEdit, QPlainTextEdit, QListWidget, QTreeWidget):
        candidates = dock.findChildren(cls)
        if candidates:
            return candidates[0]

    return None


def _clear_widget_content(widget):
    """Clear content from a widget using available methods.

    Returns True if at least one clear operation was attempted.
    """
    cleared = False
    if isinstance(widget, QTabWidget):
        for index in range(widget.count()):
            tab_widget = widget.widget(index)
            if tab_widget:
                cleared = _clear_widget_content(tab_widget) or cleared
        return cleared

    if hasattr(widget, 'clearMessages') and callable(getattr(widget, 'clearMessages')):
        widget.clearMessages()
        return True

    if hasattr(widget, 'clear') and callable(getattr(widget, 'clear')):
        widget.clear()
        return True

    for child in widget.findChildren(
        (QTextEdit, QPlainTextEdit, QListWidget, QTreeWidget, QAbstractItemView)
    ):
        if hasattr(child, 'clear') and callable(getattr(child, 'clear')):
            child.clear()
            cleared = True
            continue
        if isinstance(child, QAbstractItemView):
            model = child.model()
            if model is not None:
                if hasattr(model, 'clear') and callable(getattr(model, 'clear')):
                    model.clear()
                    cleared = True
                elif (
                    hasattr(model, 'removeRows') and
                    callable(getattr(model, 'removeRows')) and
                    hasattr(model, 'rowCount') and
                    callable(getattr(model, 'rowCount'))
                ):
                    model.removeRows(0, model.rowCount())
                    cleared = True

    # Fallback : tout descendant avec clear() callable
    if not cleared:
        for child in widget.findChildren(QWidget):
            if child is widget:
                continue
            if hasattr(child, 'clear') and callable(getattr(child, 'clear')):
                child.clear()
                cleared = True

    return cleared


class MessageLogCleaner(Cleaner):
    """Nettoyeur du panneau Message Log."""

    @property
    def label(self):
        return "Log"

    @property
    def tooltip(self):
        return "Clear message log"

    @property
    def icon_type(self):
        return "trash"

    @property
    def thread_safe(self):
        return False

    def __init__(self, main_window):
        self._main_window = main_window

    def clean(self):
        t0 = time.perf_counter()
        widget = find_message_log_widget(self._main_window)
        if not widget:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return CleanResult(
                success=False,
                message="Log: not found",
                elapsed_ms=round(elapsed_ms, 2)
            )
        cleared = _clear_widget_content(widget)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return CleanResult(
            success=cleared,
            removed=1 if cleared else 0,
            message="Log: cleared" if cleared else "Log: nothing to clear",
            elapsed_ms=round(elapsed_ms, 2)
        )
