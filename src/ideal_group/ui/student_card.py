"""Student card widget for kanban board."""

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QToolTip, QApplication,
    QGraphicsOpacityEffect, QPushButton
)
from PySide6.QtCore import Qt, Signal, QMimeData, QPoint, QEvent
from PySide6.QtGui import QDrag, QMouseEvent, QPalette, QColor, QPixmap, QPainter

from ..models import Student
from ..translations import tr


def _palette_color(role: QPalette.ColorRole) -> str:
    """Get a hex color string from the current application palette."""
    return QApplication.palette().color(role).name()


class StudentCard(QFrame):
    """A draggable card representing a student."""

    drag_started = Signal(int)   # student_id
    pin_toggled = Signal(int, bool)  # student_id, is_pinned

    def __init__(self, student: Student, is_pinned: bool = False, parent=None):
        super().__init__(parent)
        self.student = student
        self.is_pinned = is_pinned
        self.likes_in_group = 0
        self.likes_total = 0
        self.dislikes_in_group = 0
        self.dislikes_total = 0
        self._drag_start_pos = None
        self._opacity_effect = None

        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(1)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setMinimumHeight(60)
        self.setMaximumHeight(80)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.setup_ui()
        self.update_style()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Top row: name + pin button
        top_layout = QHBoxLayout()
        top_layout.setSpacing(4)

        self.name_label = QLabel(self.student.name)
        self.name_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        self.name_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        top_layout.addWidget(self.name_label, 1)

        self.pin_button = QPushButton("📌" if self.is_pinned else "📍")
        self.pin_button.setFixedSize(20, 20)
        self.pin_button.setToolTip(tr("Unpin from group") if self.is_pinned else tr("Pin to group"))
        self.pin_button.clicked.connect(self._on_pin_clicked)
        top_layout.addWidget(self.pin_button)

        layout.addLayout(top_layout)

        # Characteristics row
        char_layout = QHBoxLayout()
        char_layout.setSpacing(4)

        self.char_labels = []
        for char_name, value in self.student.characteristics.items():
            if value is True:
                label = QLabel(char_name[:3].upper())
                label.setToolTip(char_name)
                char_layout.addWidget(label)
                self.char_labels.append(label)
            elif isinstance(value, bool):
                continue
            elif isinstance(value, (int, float)) and value is not None:
                label = QLabel(f"{char_name[:2]}:{value}")
                label.setStyleSheet("font-size: 9px;")
                char_layout.addWidget(label)

        char_layout.addStretch()
        layout.addLayout(char_layout)

        # Likes/dislikes row
        pref_layout = QHBoxLayout()
        pref_layout.setSpacing(8)

        self.likes_label = QLabel("👍 0/0")
        self.likes_label.setStyleSheet("font-size: 10px;")
        pref_layout.addWidget(self.likes_label)

        self.dislikes_label = QLabel("👎 0/0")
        self.dislikes_label.setStyleSheet("font-size: 10px;")
        pref_layout.addWidget(self.dislikes_label)

        pref_layout.addStretch()
        layout.addLayout(pref_layout)

        # Apply palette-derived styles to everything just built
        self._apply_sub_styles()

    # ------------------------------------------------------------------
    # Palette-aware styling
    # ------------------------------------------------------------------

    def _apply_sub_styles(self):
        """Style sub-widgets using the current palette."""
        placeholder = _palette_color(QPalette.ColorRole.PlaceholderText)
        mid = _palette_color(QPalette.ColorRole.Mid)
        base = _palette_color(QPalette.ColorRole.Base)
        midlight = _palette_color(QPalette.ColorRole.Midlight)

        # Pin button: transparent bg, palette-derived hover
        self.pin_button.setStyleSheet(f"""
            QPushButton {{
                border: none;
                background: transparent;
                font-size: 12px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background: {midlight};
                border-radius: 2px;
            }}
        """)

        # Boolean characteristic badge labels
        for label in self.char_labels:
            label.setStyleSheet(
                f"background-color: {midlight}; color: {placeholder};"
                f"padding: 1px 3px; border-radius: 2px; font-size: 9px;"
            )

        # Likes: derive a green from the palette.
        # Use a fixed semantic green/red but adjust lightness to match theme.
        text_lightness = QApplication.palette().color(QPalette.ColorRole.Text).lightness()
        is_dark = text_lightness > 128  # dark theme has light text

        likes_color = QColor(100, 200, 100) if is_dark else QColor(30, 120, 30)
        dislikes_color = QColor(220, 80, 80) if is_dark else QColor(160, 20, 20)

        self.likes_label.setStyleSheet(
            f"font-size: 10px; color: {likes_color.name()};"
        )
        self.dislikes_label.setStyleSheet(
            f"font-size: 10px; color: {dislikes_color.name()};"
        )

    def update_style(self):
        """Update card border/background based on pinned state and palette."""
        palette = QApplication.palette()
        base = palette.color(QPalette.ColorRole.Base).name()
        mid = palette.color(QPalette.ColorRole.Mid).name()
        highlight = palette.color(QPalette.ColorRole.Highlight).name()

        # For the pinned "warm" tint we derive from the palette rather than
        # hardcoding #fff8e1. We mix the base color toward yellow slightly.
        if self.is_pinned:
            base_color = palette.color(QPalette.ColorRole.Base)
            warm = QColor(
                min(255, base_color.red() + 30),
                min(255, base_color.green() + 20),
                max(0, base_color.blue() - 30),
            )
            self.setStyleSheet(f"""
                StudentCard {{
                    background-color: {warm.name()};
                    border: 2px solid {highlight};
                    border-radius: 4px;
                }}
                StudentCard:hover {{
                    border: 2px solid {palette.color(QPalette.ColorRole.Highlight).lighter(130).name()};
                }}
            """)
        else:
            self.setStyleSheet(f"""
                StudentCard {{
                    background-color: {base};
                    border: 1px solid {mid};
                    border-radius: 4px;
                }}
                StudentCard:hover {{
                    border: 2px solid {highlight};
                }}
            """)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _on_pin_clicked(self):
        self.is_pinned = not self.is_pinned
        self.pin_button.setText("📌" if self.is_pinned else "📍")
        self.pin_button.setToolTip(tr("Unpin from group") if self.is_pinned else tr("Pin to group"))
        self.update_style()
        self.pin_toggled.emit(self.student.id, self.is_pinned)

    def set_pinned(self, pinned: bool):
        self.is_pinned = pinned
        self.pin_button.setText("📌" if self.is_pinned else "📍")
        self.pin_button.setToolTip(tr("Unpin from group") if self.is_pinned else tr("Pin to group"))
        self.update_style()

    def update_preferences(self, likes_in_group: int, likes_total: int,
                           dislikes_in_group: int, dislikes_total: int):
        self.likes_in_group = likes_in_group
        self.likes_total = likes_total
        self.dislikes_in_group = dislikes_in_group
        self.dislikes_total = dislikes_total
        self.likes_label.setText(f"👍 {likes_in_group}/{likes_total}")
        self.dislikes_label.setText(f"👎 {dislikes_in_group}/{dislikes_total}")
        self.update_style()

    # ------------------------------------------------------------------
    # Drag and drop
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_start_pos = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if self._drag_start_pos is None:
            return

        distance = (event.pos() - self._drag_start_pos).manhattanLength()
        if distance < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(str(self.student.id))
        drag.setMimeData(mime_data)

        pixmap = QPixmap(self.size())
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        self.render(painter, QPoint())
        painter.end()

        transparent_pixmap = QPixmap(pixmap.size())
        transparent_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(transparent_pixmap)
        painter.setOpacity(0.7)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()

        drag.setPixmap(transparent_pixmap)
        drag.setHotSpot(event.pos())

        self._set_dragging(True)
        self.drag_started.emit(self.student.id)
        drag.exec(Qt.DropAction.MoveAction)
        self._set_dragging(False)

        self._drag_start_pos = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def _set_dragging(self, dragging: bool):
        if dragging:
            self._opacity_effect = QGraphicsOpacityEffect()
            self._opacity_effect.setOpacity(0.25)
            self.setGraphicsEffect(self._opacity_effect)
        else:
            self.setGraphicsEffect(None)
            self._opacity_effect = None
