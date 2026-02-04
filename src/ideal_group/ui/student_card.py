"""Student card widget for kanban board."""

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QToolTip, QApplication, 
    QGraphicsOpacityEffect, QPushButton
)
from PySide6.QtCore import Qt, Signal, QMimeData, QPoint
from PySide6.QtGui import QDrag, QMouseEvent, QPalette, QColor, QPixmap, QPainter

from ..models import Student
from ..translations import tr


class StudentCard(QFrame):
    """A draggable card representing a student."""
    
    # Signal emitted when drag starts
    drag_started = Signal(int)  # student_id
    # Signal emitted when pin state changes
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
        
        # Prevent text selection
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        self.setup_ui()
        self.update_style()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)
        
        # Top row with name and pin button
        top_layout = QHBoxLayout()
        top_layout.setSpacing(4)
        
        # Name label (no text selection)
        self.name_label = QLabel(self.student.name)
        self.name_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        self.name_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        top_layout.addWidget(self.name_label, 1)
        
        # Pin button
        self.pin_button = QPushButton("📌" if self.is_pinned else "📍")
        self.pin_button.setFixedSize(20, 20)
        self.pin_button.setToolTip(tr("Unpin from group") if self.is_pinned else tr("Pin to group"))
        self.pin_button.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                font-size: 12px;
                padding: 0px;
            }
            QPushButton:hover {
                background: #e0e0e0;
                border-radius: 2px;
            }
        """)
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
                label.setStyleSheet(
                    "background-color: #e0e0e0; padding: 1px 3px; "
                    "border-radius: 2px; font-size: 9px;"
                )
                label.setToolTip(char_name)
                char_layout.addWidget(label)
                self.char_labels.append(label)
            elif isinstance(value, bool):
                # Skip False booleans
                continue
            elif isinstance(value, (int, float)) and value is not None:
                label = QLabel(f"{char_name[:2]}:{value}")
                label.setStyleSheet("font-size: 9px; color: #666;")
                char_layout.addWidget(label)
        
        char_layout.addStretch()
        layout.addLayout(char_layout)
        
        # Likes/Dislikes row
        pref_layout = QHBoxLayout()
        pref_layout.setSpacing(8)
        
        self.likes_label = QLabel("👍 0/0")
        self.likes_label.setStyleSheet("font-size: 10px; color: #2e7d32;")
        pref_layout.addWidget(self.likes_label)
        
        self.dislikes_label = QLabel("👎 0/0")
        self.dislikes_label.setStyleSheet("font-size: 10px; color: #c62828;")
        pref_layout.addWidget(self.dislikes_label)
        
        pref_layout.addStretch()
        layout.addLayout(pref_layout)
    
    def _on_pin_clicked(self):
        """Handle pin button click."""
        self.is_pinned = not self.is_pinned
        self.pin_button.setText("📌" if self.is_pinned else "📍")
        self.pin_button.setToolTip(tr("Unpin from group") if self.is_pinned else tr("Pin to group"))
        self.update_style()
        self.pin_toggled.emit(self.student.id, self.is_pinned)
    
    def set_pinned(self, pinned: bool):
        """Set the pinned state."""
        self.is_pinned = pinned
        self.pin_button.setText("📌" if self.is_pinned else "📍")
        self.pin_button.setToolTip(tr("Unpin from group") if self.is_pinned else tr("Pin to group"))
        self.update_style()
    
    def update_preferences(self, likes_in_group: int, likes_total: int,
                          dislikes_in_group: int, dislikes_total: int):
        """Update the likes/dislikes display."""
        self.likes_in_group = likes_in_group
        self.likes_total = likes_total
        self.dislikes_in_group = dislikes_in_group
        self.dislikes_total = dislikes_total
        
        self.likes_label.setText(f"👍 {likes_in_group}/{likes_total}")
        self.dislikes_label.setText(f"👎 {dislikes_in_group}/{dislikes_total}")
        
        self.update_style()
    
    def update_style(self):
        """Update card style."""
        if self.is_pinned:
            self.setStyleSheet("""
                StudentCard {
                    background-color: #fff8e1;
                    border: 2px solid #ffc107;
                    border-radius: 4px;
                }
                StudentCard:hover {
                    border: 2px solid #ff9800;
                }
            """)
        else:
            self.setStyleSheet("""
                StudentCard {
                    background-color: #ffffff;
                    border: 1px solid #e0e0e0;
                    border-radius: 4px;
                }
                StudentCard:hover {
                    border: 2px solid #1976d2;
                }
            """)
    
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
        
        # Check if we've moved enough to start a drag
        distance = (event.pos() - self._drag_start_pos).manhattanLength()
        if distance < QApplication.startDragDistance():
            return
        
        # Create drag with visual preview
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(str(self.student.id))
        drag.setMimeData(mime_data)
        
        # Create pixmap of the card for drag preview
        pixmap = QPixmap(self.size())
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        self.render(painter, QPoint())
        painter.end()
        
        # Make it semi-transparent
        transparent_pixmap = QPixmap(pixmap.size())
        transparent_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(transparent_pixmap)
        painter.setOpacity(0.7)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()
        
        drag.setPixmap(transparent_pixmap)
        drag.setHotSpot(event.pos())
        
        # Make the original card transparent while dragging
        self._set_dragging(True)
        
        self.drag_started.emit(self.student.id)
        drag.exec(Qt.DropAction.MoveAction)
        
        # Restore opacity after drag
        self._set_dragging(False)
        self._drag_start_pos = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
    
    def _set_dragging(self, dragging: bool):
        """Set the card's visual state while being dragged."""
        if dragging:
            # Make card semi-transparent but keep its size
            self._opacity_effect = QGraphicsOpacityEffect()
            self._opacity_effect.setOpacity(0.25)
            self.setGraphicsEffect(self._opacity_effect)
        else:
            self.setGraphicsEffect(None)
            self._opacity_effect = None
