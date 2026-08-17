from qgis.PyQt.QtWidgets import QToolButton
from qgis.PyQt.QtGui import QIcon, QPixmap, QPainter
from qgis.PyQt.QtCore import QTimer, Qt
import os
import math
import re

try:
    _TRANSPARENT = Qt.GlobalColor.transparent
except AttributeError:
    _TRANSPARENT = Qt.transparent

try:
    _ANTIALIAS = QPainter.RenderHint.Antialiasing
    _SMOOTH_TRANSFORM = QPainter.RenderHint.SmoothPixmapTransform
except AttributeError:
    _ANTIALIAS = QPainter.Antialiasing
    _SMOOTH_TRANSFORM = QPainter.SmoothPixmapTransform


class AnimatedBroomButton(QToolButton):
    """Bouton avec animation de balayage (rotation oscillante)."""

    def __init__(self, accent_color="#F5A623", parent=None):
        super().__init__(parent)

        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._update_icon)
        self.animation_timer.setInterval(40)

        self.current_frame = 0
        self.total_frames = 25
        self.is_animating = False

        base_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
        broom_path = os.path.join(base_dir, "broom.svg")

        self.broom_pixmap = QPixmap(broom_path)
        if self.broom_pixmap.isNull():
            fallback_dir = os.path.join(os.path.dirname(__file__), "assets")
            self.broom_pixmap = QPixmap(os.path.join(fallback_dir, "broom.svg"))

        if self.broom_pixmap.isNull():
            self.broom_pixmap = QPixmap(16, 16)
            self.broom_pixmap.fill(_TRANSPARENT)

        self.base_icon = self._create_frame(0)
        self.setIcon(self.base_icon)

        validated_color = self._validate_accent_color(accent_color)
        r = int(validated_color[1:3], 16)
        g = int(validated_color[3:5], 16)
        b = int(validated_color[5:7], 16)
        hover_bg = f"rgba({r}, {g}, {b}, 0.2)"

        self.setStyleSheet(f"""
            QToolButton {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 4px;
            }}
            QToolButton:hover {{
                background-color: {hover_bg};
                border: 1px solid {validated_color};
            }}
            QToolButton:disabled {{
                background-color: transparent;
                opacity: 0.5;
            }}
        """)

    @staticmethod
    def _validate_accent_color(value):
        """Valide et normalise une couleur hexadécimale."""
        if isinstance(value, str) and re.fullmatch(r"^#[0-9A-Fa-f]{6}$", value):
            return value
        return "#F5A623"

    def start_animation(self):
        """Démarre l'animation de balayage."""
        if self.is_animating:
            return

        self.is_animating = True
        self.setEnabled(False)
        self.current_frame = 0
        self.animation_timer.start()

    def _create_frame(self, angle):
        """Crée une frame avec le balai pivoté."""
        canvas = QPixmap(self.broom_pixmap.size())
        canvas.fill(_TRANSPARENT)

        painter = QPainter(canvas)
        painter.setRenderHint(_ANTIALIAS)
        painter.setRenderHint(_SMOOTH_TRANSFORM)

        cx = self.broom_pixmap.width() / 2
        cy = self.broom_pixmap.height() / 2

        painter.translate(cx, cy)
        painter.rotate(angle)
        painter.translate(-cx, -cy)

        painter.drawPixmap(0, 0, self.broom_pixmap)
        painter.end()
        return QIcon(canvas)

    def stop_animation(self):
        """Arrête l'animation et réinitialise l'icône sans toucher enabled."""
        if not self.is_animating:
            return
        self.animation_timer.stop()
        self.setIcon(self.base_icon)
        self.is_animating = False

    def _update_icon(self):
        """Met à jour l'icône pour simuler le balayage."""
        self.current_frame += 1

        if self.current_frame > self.total_frames:
            self.animation_timer.stop()
            self.setIcon(self.base_icon)
            self.is_animating = False
            return

        progress = self.current_frame / self.total_frames
        # Oscillation : -30 deg à +30 deg
        curve = math.sin(progress * math.pi * 2)
        angle = curve * 30

        self.setIcon(self._create_frame(angle))
