"""Info widget showing score breakdown."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QLabel, QTableWidget, 
    QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt

from ..models import Project
from ..algorithm import calculate_group_score, calculate_constraint_penalty_details
from ..translations import tr


class InfoWidget(QWidget):
    """Widget showing score breakdown and penalties."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.project: Project = None
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Score summary
        summary_group = QGroupBox(tr("Score Summary"))
        summary_layout = QVBoxLayout(summary_group)
        
        self.groups_score_label = QLabel(f"{tr('Groups Sum:')} 0.0")
        self.groups_score_label.setStyleSheet("font-size: 14px;")
        summary_layout.addWidget(self.groups_score_label)
        
        self.penalties_label = QLabel(f"{tr('Penalties:')} 0.0")
        self.penalties_label.setStyleSheet("font-size: 14px; color: #c62828;")
        summary_layout.addWidget(self.penalties_label)
        
        self.total_label = QLabel(f"{tr('Total Score:')} 0.0")
        self.total_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        summary_layout.addWidget(self.total_label)
        
        layout.addWidget(summary_group)
        
        # Group scores table
        groups_group = QGroupBox(tr("Group Scores"))
        groups_layout = QVBoxLayout(groups_group)
        
        self.groups_table = QTableWidget()
        self.groups_table.setColumnCount(2)
        self.groups_table.setHorizontalHeaderLabels([tr("Group"), tr("Score")])
        self.groups_table.horizontalHeader().setStretchLastSection(True)
        self.groups_table.verticalHeader().setVisible(False)
        groups_layout.addWidget(self.groups_table)
        
        layout.addWidget(groups_group)
        
        # Penalties table
        penalties_group = QGroupBox(tr("Penalty Details"))
        penalties_layout = QVBoxLayout(penalties_group)
        
        self.penalties_table = QTableWidget()
        self.penalties_table.setColumnCount(3)
        self.penalties_table.setHorizontalHeaderLabels([tr("Group"), tr("Penalty"), tr("Reason")])
        self.penalties_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.penalties_table.verticalHeader().setVisible(False)
        penalties_layout.addWidget(self.penalties_table)
        
        self.no_penalties_label = QLabel(f"✓ {tr('No constraint violations')}")
        self.no_penalties_label.setStyleSheet("color: #2e7d32; font-size: 14px;")
        self.no_penalties_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        penalties_layout.addWidget(self.no_penalties_label)
        
        layout.addWidget(penalties_group)
        
        layout.addStretch()
    
    def set_project(self, project: Project):
        self.project = project
        self.refresh()
    
    def refresh(self):
        """Refresh the info display."""
        if not self.project:
            return
        
        # Calculate group scores
        group_scores = []
        groups_sum = 0.0
        for group in self.project.groups:
            score = calculate_group_score(self.project, group)
            group_scores.append((group.name, score))
            groups_sum += score
        
        # Calculate penalties
        total_penalty, penalty_details = calculate_constraint_penalty_details(self.project)
        
        # Total score
        total_score = groups_sum - total_penalty
        
        # Update summary labels
        self.groups_score_label.setText(f"{tr('Groups Sum:')} {groups_sum:.1f}")
        self.penalties_label.setText(f"{tr('Penalties:')} -{total_penalty:.1f}")
        self.total_label.setText(f"{tr('Total Score:')} {total_score:.1f}")
        
        # Update groups table
        self.groups_table.setRowCount(len(group_scores))
        for i, (name, score) in enumerate(group_scores):
            self.groups_table.setItem(i, 0, QTableWidgetItem(name))
            score_item = QTableWidgetItem(f"{score:.1f}")
            score_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.groups_table.setItem(i, 1, score_item)
        
        # Update penalties table
        if penalty_details:
            self.penalties_table.setVisible(True)
            self.no_penalties_label.setVisible(False)
            self.penalties_table.setRowCount(len(penalty_details))
            for i, (group_name, penalty, reason) in enumerate(penalty_details):
                self.penalties_table.setItem(i, 0, QTableWidgetItem(group_name))
                penalty_item = QTableWidgetItem(f"-{penalty:.0f}")
                penalty_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                penalty_item.setForeground(Qt.GlobalColor.red)
                self.penalties_table.setItem(i, 1, penalty_item)
                self.penalties_table.setItem(i, 2, QTableWidgetItem(reason))
        else:
            self.penalties_table.setVisible(False)
            self.no_penalties_label.setVisible(True)
            self.penalties_table.setRowCount(0)
