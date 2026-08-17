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


class AnimatedCleanButton(QToolButton):
    """Bouton QToolButton avec animation de nettoyage (poubelle)."""

    def __init__(self, accent_color="#8CC63F", parent=None):
        super().__init__(parent)

        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._update_icon)
        self.animation_timer.setInterval(40)

        self.current_frame = 0
        self.total_frames = 25
        self.is_animating = False

        base_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
        self.base_path = os.path.join(base_dir, "trash_base.svg")
        self.lid_path = os.path.join(base_dir, "trash_lid.svg")

        self.base_pixmap = QPixmap(self.base_path)
        self.lid_pixmap = QPixmap(self.lid_path)

        if self.base_pixmap.isNull():
            base_dir = os.path.join(os.path.dirname(__file__), "assets")
            self.base_path = os.path.join(base_dir, "trash_base.svg")
            self.lid_path = os.path.join(base_dir, "trash_lid.svg")
            self.base_pixmap = QPixmap(self.base_path)
            self.lid_pixmap = QPixmap(self.lid_path)

        if self.base_pixmap.isNull() or self.lid_pixmap.isNull():
            self.base_pixmap = QPixmap(16, 16)
            self.base_pixmap.fill(_TRANSPARENT)
            self.lid_pixmap = QPixmap(16, 16)
            self.lid_pixmap.fill(_TRANSPARENT)

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
        """Valide et normalise une couleur hexadÃ©cimale."""
        if isinstance(value, str) and re.fullmatch(r"^#[0-9A-Fa-f]{6}$", value):
            return value
        return "#8CC63F"

    def start_animation(self):
        """DÃ©marre l'animation de poubelle."""
        if self.is_animating:
            return

        self.is_animating = True
        self.setEnabled(False)  # Bloquer le clic pendant l'animation
        self.current_frame = 0
        self.animation_timer.start()

    def _create_frame(self, angle):
        """Superpose le corps et le couvercle avec une rotation."""
        canvas = QPixmap(self.base_pixmap.size())
        canvas.fill(_TRANSPARENT)

        painter = QPainter(canvas)
        painter.setRenderHint(_ANTIALIAS)
        painter.setRenderHint(_SMOOTH_TRANSFORM)

        # Dessiner le corps (fixe)
        painter.drawPixmap(0, 0, self.base_pixmap)

        # Point de pivot pour le couvercle (en haut Ã  droite pour donner l'effet d'ouverture)
        pivot_x = self.lid_pixmap.width() * 0.8
        pivot_y = self.lid_pixmap.height() * 0.2

        painter.translate(pivot_x, pivot_y)
        painter.rotate(angle)
        painter.translate(-pivot_x, -pivot_y)

        # Dessiner le couvercle (animÃ©)
        painter.drawPixmap(0, 0, self.lid_pixmap)

        painter.end()
        return QIcon(canvas)

    def stop_animation(self):
        """ArrÃªte l'animation et rÃ©initialise l'icÃ´ne sans toucher enabled."""
        if not self.is_animating:
            return
        self.animation_timer.stop()
        self.setIcon(self.base_icon)
        self.is_animating = False

    def _update_icon(self):
        """Met Ã  jour l'icÃ´ne pour simuler l'ouverture/fermeture du couvercle."""
        self.current_frame += 1

        if self.current_frame > self.total_frames:
            self.animation_timer.stop()
            self.setIcon(self.base_icon)
            self.is_animating = False
            return

        # Calcul de l'angle (Ouverture jusqu'Ã  45 degrÃ©s, puis fermeture)
        progress = self.current_frame / self.total_frames

        # Une courbe sinusoÃ¯dale : commence Ã  0, monte Ã  1 Ã  mi-chemin, redescend Ã  0
        curve = math.sin(progress * math.pi)
        angle = curve * 45  # Le couvercle s'ouvre Ã  45 degrÃ©s max

        self.setIcon(self._create_frame(angle))

