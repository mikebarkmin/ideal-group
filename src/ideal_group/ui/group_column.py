"""Group column widget for kanban board."""

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QWidget, 
    QSpacerItem, QSizePolicy, QPushButton, QMenu
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QDragMoveEvent, QAction

from ..models import Group, Student, Project
from ..algorithm import calculate_group_score, get_student_score_in_group
from ..translations import tr
from .student_card import StudentCard


class DropPlaceholder(QFrame):
    """Visual placeholder showing where a card will be dropped."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(70)
        self.setMinimumHeight(70)
        self.setMaximumHeight(70)
        self.setStyleSheet("""
            background-color: #e3f2fd;
            border: 2px dashed #1976d2;
            border-radius: 4px;
            margin: 0px;
        """)


class GroupColumn(QFrame):
    """A column in the kanban board representing a group."""
    
    # Signal emitted when a student is dropped into this group (student_id, group_name, position)
    student_dropped = Signal(int, str, int)
    # Signal emitted when a student's pin state changes
    student_pin_changed = Signal(int, str, bool)  # student_id, group_name, is_pinned
    
    def __init__(self, group: Group, project: Project, parent=None):
        super().__init__(parent)
        self.group = group
        self.project = project
        self.student_cards: dict[int, StudentCard] = {}
        self._drop_index = -1
        self._placeholder = None
        self._dragging_student_id = None
        self._sort_key = None  # None, 'likes', 'dislikes', or characteristic name
        self._sort_ascending = True
        
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        self.setMinimumWidth(200)
        self.setMaximumWidth(280)
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Header
        header_layout = QVBoxLayout()
        header_layout.setSpacing(2)
        
        # Group name and count
        title_layout = QHBoxLayout()
        self.name_label = QLabel(self.group.name)
        self.name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        title_layout.addWidget(self.name_label)
        
        self.count_label = QLabel("0/0")
        self.count_label.setStyleSheet("color: #666; font-size: 12px;")
        title_layout.addWidget(self.count_label)
        title_layout.addStretch()
        
        # Sort button
        self.sort_button = QPushButton("↕")
        self.sort_button.setFixedSize(24, 24)
        self.sort_button.setToolTip(tr("Sort"))
        self.sort_button.setStyleSheet("""
            QPushButton {
                border: 1px solid #ccc;
                border-radius: 4px;
                background: #f5f5f5;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #e0e0e0;
            }
        """)
        self.sort_button.clicked.connect(self._show_sort_menu)
        title_layout.addWidget(self.sort_button)
        
        header_layout.addLayout(title_layout)
        
        # Score
        self.score_label = QLabel("Score: 0")
        self.score_label.setStyleSheet("color: #1976d2; font-size: 11px;")
        header_layout.addWidget(self.score_label)
        
        # Constraints summary
        self.constraints_label = QLabel("")
        self.constraints_label.setStyleSheet("color: #666; font-size: 10px;")
        self.constraints_label.setWordWrap(True)
        header_layout.addWidget(self.constraints_label)
        
        layout.addLayout(header_layout)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("color: #e0e0e0;")
        layout.addWidget(separator)
        
        # Scrollable area for student cards
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.scroll.setAcceptDrops(True)
        
        self.cards_widget = QWidget()
        self.cards_widget.setAcceptDrops(True)
        self.cards_layout = QVBoxLayout(self.cards_widget)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(6)
        
        self.cards_layout.addStretch()
        
        self.scroll.setWidget(self.cards_widget)
        layout.addWidget(self.scroll)
        
        self.update_header()
    
    def update_header(self):
        """Update the header with current group info."""
        count = len(self.group.student_ids)
        self.count_label.setText(f"{count}/{self.group.max_size}")
        
        # Update count color based on capacity
        if count > self.group.max_size:
            self.count_label.setStyleSheet("color: #c62828; font-size: 12px; font-weight: bold;")
        elif count == self.group.max_size:
            self.count_label.setStyleSheet("color: #f57c00; font-size: 12px;")
        else:
            self.count_label.setStyleSheet("color: #666; font-size: 12px;")
        
        # Calculate and display score
        score = calculate_group_score(self.project, self.group)
        self.score_label.setText(f"{tr('Score:')} {score:.1f}")
        
        # Calculate averages for numerical characteristics
        averages = self._calculate_numerical_averages()
        
        # Update constraints display
        constraints_parts = []
        if self.group.constraints:
            for c in self.group.constraints:
                constraints_parts.append(
                    f"{c.characteristic}: {c.constraint_type.value}" + 
                    (f"({c.value})" if c.value else "")
                )
        
        # Add averages
        for char_name, avg in averages.items():
            constraints_parts.append(f"⌀ {char_name}: {avg:.2f}")
        
        if constraints_parts:
            self.constraints_label.setText(", ".join(constraints_parts))
        else:
            self.constraints_label.setText(tr("No constraints"))
    
    def _calculate_numerical_averages(self) -> dict[str, float]:
        """Calculate averages for numerical characteristics in this group."""
        if not self.group.student_ids:
            return {}
        
        # Collect numerical values per characteristic
        char_values: dict[str, list[float]] = {}
        
        for student_id in self.group.student_ids:
            student = self.project.get_student_by_id(student_id)
            if student:
                for char_name, value in student.characteristics.items():
                    # Skip booleans (bool is subclass of int in Python)
                    if isinstance(value, bool):
                        continue
                    if isinstance(value, (int, float)) and value is not None:
                        if char_name not in char_values:
                            char_values[char_name] = []
                        char_values[char_name].append(float(value))
        
        # Calculate averages
        averages = {}
        for char_name, values in char_values.items():
            if values:
                averages[char_name] = sum(values) / len(values)
        
        return averages
    
    def _show_sort_menu(self):
        """Show sorting options menu."""
        menu = QMenu(self)
        
        # No sort option
        no_sort_action = menu.addAction(tr("No sorting"))
        no_sort_action.setCheckable(True)
        no_sort_action.setChecked(self._sort_key is None)
        no_sort_action.triggered.connect(lambda: self._set_sort(None))
        
        menu.addSeparator()
        
        # Likes/dislikes
        likes_action = menu.addAction(tr("Likes") + " ↓")
        likes_action.triggered.connect(lambda: self._set_sort("likes", ascending=False))
        
        dislikes_action = menu.addAction(tr("Dislikes") + " ↑")
        dislikes_action.triggered.connect(lambda: self._set_sort("dislikes", ascending=True))
        
        # Get characteristics from students
        char_names = set()
        for student_id in self.group.student_ids:
            student = self.project.get_student_by_id(student_id)
            if student:
                char_names.update(student.characteristics.keys())
        
        if char_names:
            menu.addSeparator()
            for char_name in sorted(char_names):
                # Check if numerical
                is_numerical = False
                for student_id in self.group.student_ids:
                    student = self.project.get_student_by_id(student_id)
                    if student and char_name in student.characteristics:
                        val = student.characteristics[char_name]
                        if isinstance(val, bool):
                            break
                        if isinstance(val, (int, float)):
                            is_numerical = True
                        break
                
                if is_numerical:
                    asc_action = menu.addAction(f"{char_name} ↑")
                    asc_action.triggered.connect(lambda checked, c=char_name: self._set_sort(c, ascending=True))
                    desc_action = menu.addAction(f"{char_name} ↓")
                    desc_action.triggered.connect(lambda checked, c=char_name: self._set_sort(c, ascending=False))
                else:
                    # Boolean - just show true first
                    action = menu.addAction(f"{char_name}")
                    action.triggered.connect(lambda checked, c=char_name: self._set_sort(c, ascending=False))
        
        menu.exec(self.sort_button.mapToGlobal(self.sort_button.rect().bottomLeft()))
    
    def _set_sort(self, key, ascending=True):
        """Set sort key and refresh."""
        self._sort_key = key
        self._sort_ascending = ascending
        self.refresh_students()
    
    def _get_sorted_student_ids(self) -> list[int]:
        """Get student IDs sorted according to current sort settings."""
        if self._sort_key is None:
            return list(self.group.student_ids)
        
        def get_sort_value(student_id):
            student = self.project.get_student_by_id(student_id)
            if not student:
                return (1, 0)  # Sort missing students last
            
            if self._sort_key == "likes":
                score_info = get_student_score_in_group(student, self.group, self.project)
                return (0, score_info["likes_satisfied"])
            elif self._sort_key == "dislikes":
                score_info = get_student_score_in_group(student, self.group, self.project)
                return (0, score_info["dislikes_in_group"])
            else:
                # Characteristic
                val = student.characteristics.get(self._sort_key)
                if val is None:
                    return (1, 0)
                if isinstance(val, bool):
                    return (0, 1 if val else 0)
                return (0, val)
        
        sorted_ids = sorted(self.group.student_ids, key=get_sort_value, reverse=not self._sort_ascending)
        return sorted_ids
    
    def refresh_students(self):
        """Refresh all student cards in this column."""
        # Clear existing cards
        for card in self.student_cards.values():
            card.deleteLater()
        self.student_cards.clear()
        
        # Remove stretch
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Get sorted student IDs
        sorted_student_ids = self._get_sorted_student_ids()
        pinned_ids = set(self.group.pinned_student_ids)
        
        # Add student cards
        for student_id in sorted_student_ids:
            student = self.project.get_student_by_id(student_id)
            if student:
                is_pinned = student_id in pinned_ids
                card = StudentCard(student, is_pinned=is_pinned)
                
                # Connect pin signal
                card.pin_toggled.connect(self._on_student_pin_toggled)
                
                # Calculate preferences
                score_info = get_student_score_in_group(student, self.group, self.project)
                card.update_preferences(
                    score_info["likes_satisfied"],
                    score_info["likes_total"],
                    score_info["dislikes_in_group"],
                    score_info["dislikes_total"]
                )
                
                self.cards_layout.addWidget(card)
                self.student_cards[student_id] = card
        
        # Add stretch at end
        self.cards_layout.addStretch()
        
        self.update_header()
    
    def _on_student_pin_toggled(self, student_id: int, is_pinned: bool):
        """Handle pin toggle from a student card."""
        self.student_pin_changed.emit(student_id, self.group.name, is_pinned)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasText():
            self._dragging_student_id = int(event.mimeData().text())
            event.acceptProposedAction()
            self.setStyleSheet("QFrame { background-color: #e3f2fd; }")
    
    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.mimeData().hasText():
            event.acceptProposedAction()
            self._update_placeholder(event.position().toPoint())
    
    def dragLeaveEvent(self, event):
        self.setStyleSheet("")
        self._remove_placeholder()
    
    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet("")
        drop_position = self._drop_index
        self._remove_placeholder()
        if event.mimeData().hasText():
            student_id = int(event.mimeData().text())
            self.student_dropped.emit(student_id, self.group.name, drop_position)
            event.acceptProposedAction()
    
    def _update_placeholder(self, pos):
        """Update placeholder position based on mouse position."""
        cards_pos = self.cards_widget.mapFrom(self, pos)
        y = cards_pos.y()
        
        # Check if dragging from this same column
        dragging_from_this_column = self._dragging_student_id in self.group.student_ids
        
        # Build list of visible cards (excluding the one being dragged)
        visible_cards = []
        for i, student_id in enumerate(self.group.student_ids):
            if student_id in self.student_cards and student_id != self._dragging_student_id:
                visible_cards.append((i, student_id, self.student_cards[student_id]))
        
        # Find insertion index based on card positions
        new_drop_index = 0
        insert_at_layout_index = 0
        
        for i, (orig_idx, student_id, card) in enumerate(visible_cards):
            card_y = card.y()
            card_height = card.height()
            card_mid = card_y + card_height // 2
            
            if y > card_mid:
                new_drop_index = orig_idx + 1
                insert_at_layout_index = i + 1
            else:
                break
        
        # Adjust if dragging from same group and from before the drop position
        if dragging_from_this_column:
            current_idx = self.group.student_ids.index(self._dragging_student_id)
            if current_idx < new_drop_index:
                new_drop_index -= 1
        
        # Only update if position changed
        if new_drop_index == self._drop_index and self._placeholder is not None:
            return
        
        self._drop_index = new_drop_index
        
        # Don't show placeholder when dragging within same column to same position
        if dragging_from_this_column:
            current_idx = self.group.student_ids.index(self._dragging_student_id)
            # If dropping at same position or adjacent, no placeholder needed
            if new_drop_index == current_idx:
                self._remove_placeholder()
                return
        
        # Create placeholder if it doesn't exist
        if self._placeholder is None:
            self._placeholder = DropPlaceholder()
            self.cards_layout.insertWidget(insert_at_layout_index, self._placeholder)
        else:
            # Move existing placeholder
            current_index = self.cards_layout.indexOf(self._placeholder)
            if current_index != insert_at_layout_index:
                self.cards_layout.removeWidget(self._placeholder)
                self.cards_layout.insertWidget(insert_at_layout_index, self._placeholder)
    
    def _remove_placeholder(self):
        """Remove the placeholder."""
        if self._placeholder is not None:
            self.cards_layout.removeWidget(self._placeholder)
            self._placeholder.deleteLater()
            self._placeholder = None
        self._drop_index = -1
        self._dragging_student_id = None
