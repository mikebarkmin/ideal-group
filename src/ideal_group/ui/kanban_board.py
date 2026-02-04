"""Kanban board widget for displaying groups and students."""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, Signal

from ..models import Project, Group
from ..translations import tr
from .group_column import GroupColumn


class UnassignedColumn(QFrame):
    """Column for unassigned students."""
    
    student_dropped = Signal(int, str, int)  # student_id, "unassigned", position
    
    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.project = project
        
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        self.setMinimumWidth(200)
        self.setMaximumWidth(250)
        self.setStyleSheet("background-color: #fafafa;")
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Header
        self.name_label = QLabel(tr("Unassigned"))
        self.name_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #666;")
        layout.addWidget(self.name_label)
        
        self.count_label = QLabel(f"0 {tr('students')}")
        self.count_label.setStyleSheet("color: #999; font-size: 11px;")
        layout.addWidget(self.count_label)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(separator)
        
        # Scrollable area for cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.cards_widget = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_widget)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(6)
        self.cards_layout.addStretch()
        
        scroll.setWidget(self.cards_widget)
        layout.addWidget(scroll)
    
    def refresh(self):
        """Refresh the unassigned students list."""
        from .student_card import StudentCard
        
        # Clear existing
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add unassigned students
        unassigned = self.project.get_unassigned_students()
        
        for student in unassigned:
            card = StudentCard(student)
            card.update_preferences(0, len(student.liked), 0, len(student.disliked))
            self.cards_layout.addWidget(card)
        
        self.cards_layout.addStretch()
        self.count_label.setText(f"{len(unassigned)} {tr('students')}")
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
            self.setStyleSheet("background-color: #fff3e0;")
    
    def dragLeaveEvent(self, event):
        self.setStyleSheet("background-color: #fafafa;")
    
    def dropEvent(self, event):
        self.setStyleSheet("background-color: #fafafa;")
        if event.mimeData().hasText():
            student_id = int(event.mimeData().text())
            self.student_dropped.emit(student_id, "unassigned", -1)
            event.acceptProposedAction()


class KanbanBoard(QWidget):
    """The main kanban board showing all groups as columns."""
    
    assignment_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.project: Project = None
        self.columns: dict[str, GroupColumn] = {}
        self.unassigned_column: UnassignedColumn = None
        
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Horizontal scroll for columns
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        self.board_widget = QWidget()
        self.board_layout = QHBoxLayout(self.board_widget)
        self.board_layout.setContentsMargins(8, 8, 8, 8)
        self.board_layout.setSpacing(12)
        
        scroll.setWidget(self.board_widget)
        main_layout.addWidget(scroll)
    
    def set_project(self, project: Project):
        """Set the project and rebuild the board."""
        self.project = project
        self.rebuild_board()
    
    def rebuild_board(self):
        """Rebuild all columns from the project."""
        # Clear existing columns
        for column in self.columns.values():
            column.deleteLater()
        self.columns.clear()
        
        if self.unassigned_column:
            self.unassigned_column.deleteLater()
            self.unassigned_column = None
        
        # Clear layout
        while self.board_layout.count():
            item = self.board_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not self.project:
            return
        
        # Add unassigned column first
        self.unassigned_column = UnassignedColumn(self.project)
        self.unassigned_column.student_dropped.connect(self.on_student_dropped)
        self.board_layout.addWidget(self.unassigned_column)
        
        # Add group columns
        for group in self.project.groups:
            column = GroupColumn(group, self.project)
            column.student_dropped.connect(self.on_student_dropped)
            column.student_pin_changed.connect(self.on_student_pin_changed)
            self.board_layout.addWidget(column)
            self.columns[group.name] = column
        
        self.board_layout.addStretch()
        
        self.refresh_all()
    
    def refresh_all(self):
        """Refresh all columns."""
        if self.unassigned_column:
            self.unassigned_column.refresh()
        
        for column in self.columns.values():
            column.refresh_students()
    
    def on_student_dropped(self, student_id: int, target_group_name: str, position: int = -1):
        """Handle a student being dropped into a group."""
        if not self.project:
            return
        
        source_group_name = None
        
        # Find and remove from current group (also unpin if moving to different group)
        for group in self.project.groups:
            if student_id in group.student_ids:
                source_group_name = group.name
                group.student_ids.remove(student_id)
                # Unpin if moving to a different group
                if group.name != target_group_name and student_id in group.pinned_student_ids:
                    group.pinned_student_ids.remove(student_id)
                break
        
        # Add to target group (if not unassigned)
        if target_group_name != "unassigned":
            for group in self.project.groups:
                if group.name == target_group_name:
                    if position >= 0 and position <= len(group.student_ids):
                        group.student_ids.insert(position, student_id)
                    else:
                        group.student_ids.append(student_id)
                    break
        
        # Refresh only affected columns
        columns_to_refresh = set()
        
        if source_group_name:
            columns_to_refresh.add(source_group_name)
        else:
            # Came from unassigned
            if self.unassigned_column:
                self.unassigned_column.refresh()
        
        if target_group_name == "unassigned":
            if self.unassigned_column:
                self.unassigned_column.refresh()
        else:
            columns_to_refresh.add(target_group_name)
        
        for col_name in columns_to_refresh:
            if col_name in self.columns:
                self.columns[col_name].refresh_students()
        
        self.assignment_changed.emit()
    
    def on_student_pin_changed(self, student_id: int, group_name: str, is_pinned: bool):
        """Handle a student's pin state being changed."""
        if not self.project:
            return
        
        for group in self.project.groups:
            if group.name == group_name:
                if is_pinned:
                    if student_id not in group.pinned_student_ids:
                        group.pinned_student_ids.append(student_id)
                else:
                    if student_id in group.pinned_student_ids:
                        group.pinned_student_ids.remove(student_id)
                break
        
        # Trigger score recalculation
        self.assignment_changed.emit()
