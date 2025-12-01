from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtWidgets import (
    QDockWidget, QTabWidget, QPushButton, QWidget, 
    QHBoxLayout, QLabel, QTextEdit, QListWidget, QTreeWidget
)
from qgis.PyQt.QtGui import QIcon
from qgis.utils import iface
from qgis.core import Qgis
import os


class MessageLogCleaner:
    """Business logic for QGIS message log cleanup operations."""
    
    @staticmethod
    def find_message_log_dock():
        """Locate the QGIS Message Log dock widget.
        
        Searches for the dock by objectName first, then falls back to 
        widget type inspection for robustness across QGIS locales.
        
        Returns:
            QDockWidget: The Message Log dock if found, None otherwise.
        """
        main_window = iface.mainWindow()
        for dock in main_window.findChildren(QDockWidget):
            # Primary: recognition by objectName
            obj_name = dock.objectName()
            if obj_name in ("MessageLog", "MessageLogDock"):
                return dock
            
            # Fallback: check if dock contains MessageLog TabWidget
            if dock.findChild(QTabWidget, "MessageLog"):
                return dock
        return None
    
    @staticmethod
    def find_message_log_widget():
        """Locate the Message Log TabWidget by objectName or parent relationship.
        
        Uses objectName as primary method, with fallback to finding TabWidget
        inside the MessageLog dock for robustness.
        
        Returns:
            QTabWidget: The Message Log TabWidget if found, None otherwise.
        """
        main_window = iface.mainWindow()
        
        # Primary: direct search by objectName
        for widget in main_window.findChildren(QTabWidget):
            if widget.objectName() == "MessageLog":
                return widget
        
        # Fallback: find TabWidget inside MessageLog dock
        dock = MessageLogCleaner.find_message_log_dock()
        if dock:
            tab_widget = dock.findChild(QTabWidget)
            if tab_widget:
                return tab_widget
        
        return None
    
    @staticmethod
    def clear_widget_content(widget):
        """Clear content from a widget using available methods.
        
        Attempts to clear via clear() or clearMessages() methods,
        then falls back to clearing child widgets.
        
        Args:
            widget: Qt widget to clear content from.
        """
        if hasattr(widget, 'clear'):
            widget.clear()
        elif hasattr(widget, 'clearMessages'):
            widget.clearMessages()
        else:
            # Fallback: search children
            for child in widget.findChildren((QTextEdit, QListWidget, QTreeWidget)):
                if hasattr(child, 'clear'):
                    child.clear()


class CleanLogs(QObject):
    """QGIS plugin for message log cleanup.
    
    Integrates a clear button directly into the Message Log dock title bar,
    providing quick access to log cleanup functionality for developers.
    """
    
    def __init__(self, iface_ref):
        """Initialize plugin instance.
        
        Args:
            iface_ref: QGIS interface reference.
        """
        super().__init__()
        self.iface = iface_ref
        self.msg_dock = None
        self.custom_btn = None
        self.close_btn = None
        self.original_titlebar = None

    def initGui(self):
        """Initialize plugin GUI components."""
        self._add_button_to_dock()

    def _add_button_to_dock(self):
        """Add custom buttons to Message Log dock title bar.
        
        Creates a custom title bar widget containing the dock title,
        a clear button, and a close button.
        """
        try:
            # Locate dock
            self.msg_dock = MessageLogCleaner.find_message_log_dock()
            if not self.msg_dock:
                self._fallback_error(
                    "CleanLogs._add_button_to_dock", 
                    "MessageLog dock not found"
                )
                return
            
            # Save original titlebar for restoration
            self.original_titlebar = self.msg_dock.titleBarWidget()
            
            # Get dock title
            dock_title = self.msg_dock.windowTitle()
            
            # Create custom titlebar container
            titlebar_widget = QWidget()
            layout = QHBoxLayout(titlebar_widget)
            layout.setContentsMargins(4, 2, 4, 2)
            layout.setSpacing(4)
            
            # Title label
            title_label = QLabel(dock_title)
            title_label.setStyleSheet("font-weight: bold;")
            layout.addWidget(title_label)
            
            # Elastic spacer
            layout.addStretch()
            
            # Clear button
            icon_path = os.path.join(os.path.dirname(__file__), "clean.png")
            self.custom_btn = QPushButton()
            self.custom_btn.setIcon(QIcon(icon_path))
            self.custom_btn.setToolTip("Clear message log")
            self.custom_btn.setFlat(True)
            self.custom_btn.setMaximumSize(24, 24)
            self.custom_btn.clicked.connect(self.clear_log)
            layout.addWidget(self.custom_btn)
            
            # Close button
            self.close_btn = QPushButton("✕")
            self.close_btn.setToolTip("Close panel")
            self.close_btn.setFlat(True)
            self.close_btn.setMaximumSize(24, 24)
            self.close_btn.setStyleSheet("QPushButton { font-size: 16px; font-weight: bold; }")
            self.close_btn.clicked.connect(self.msg_dock.hide)
            layout.addWidget(self.close_btn)
            
            # Apply custom titlebar
            self.msg_dock.setTitleBarWidget(titlebar_widget)
            
        except (RuntimeError, AttributeError) as e:
            self._fallback_error(
                "CleanLogs._add_button_to_dock", 
                f"Failed to add button: {type(e).__name__}", 
                str(e)
            )

    def unload(self):
        """Clean up plugin resources on unload.
        
        Restores original dock title bar and releases all Qt widget references.
        """
        try:
            if self.msg_dock is not None and self.original_titlebar is not None:
                # Restore original titlebar
                self.msg_dock.setTitleBarWidget(self.original_titlebar)
            
        except (RuntimeError, AttributeError):
            # Intentional: cleanup must not raise during plugin unload
            pass
        finally:
            # Release references
            self.custom_btn = None
            self.close_btn = None
            self.msg_dock = None
            self.original_titlebar = None
    
    def clear_log(self):
        """Execute message log cleanup operation.
        
        Clears all tabs in the Message Log widget and displays
        a status bar confirmation message.
        """
        try:
            # Locate widget
            msg_widget = MessageLogCleaner.find_message_log_widget()
            if not msg_widget:
                return
            
            # Clear all tabs
            for i in range(msg_widget.count()):
                tab_widget = msg_widget.widget(i)
                if tab_widget:
                    MessageLogCleaner.clear_widget_content(tab_widget)
            
            # Status feedback
            self.iface.statusBarIface().showMessage("Log cleared", 2000)
                
        except (RuntimeError, AttributeError) as e:
            self._fallback_error(
                "CleanLogs.clear_log", 
                f"Cleanup failed: {type(e).__name__}", 
                str(e)
            )
    
    def _fallback_error(self, source, cause, context=""):
        """Display structured error message to user.
        
        Args:
            source: Module and function where error occurred.
            cause: Brief description of the error cause.
            context: Optional additional context or exception details.
        """
        msg = f"[{source}] {cause}"
        if context:
            msg += f" | {context}"
        self.iface.messageBar().pushMessage(
            "Clean Log", 
            msg,
            level=Qgis.Warning, 
            duration=4
        )
