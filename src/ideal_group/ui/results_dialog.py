"""Dialog for selecting from multiple optimization results."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QGroupBox, QSplitter
)
from PySide6.QtCore import Qt

from ..models import Project
from ..algorithm import calculate_total_score, calculate_group_score
from ..translations import tr


def _group_scores(result: Project) -> list[float]:
    return [calculate_group_score(result, g) for g in result.groups]


def _std_dev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5


class ResultsDialog(QDialog):
    """Dialog for listing and selecting optimization results."""

    def __init__(self, results: list[Project], parent=None):
        super().__init__(parent)
        self.results = results
        self.selected_result: Project = None

        self.setWindowTitle(tr("Select Optimization Result"))
        self.setMinimumSize(800, 500)
        self.setup_ui()
        self.populate_results()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        instructions = QLabel(tr("Select a result to apply. Results are sorted by total score (best first)."))
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Left: results list ---
        results_group = QGroupBox(tr("Results"))
        results_layout = QVBoxLayout(results_group)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(["#", tr("Total Score"), tr("Group σ")])
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setToolTip(
            tr("Group σ: standard deviation of per-group scores. Lower = more balanced groups.")
        )
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.results_table.itemSelectionChanged.connect(self.on_selection_changed)
        results_layout.addWidget(self.results_table)

        splitter.addWidget(results_group)

        # --- Right: group scores detail ---
        details_group = QGroupBox(tr("Group Scores"))
        details_layout = QVBoxLayout(details_group)

        self.total_label = QLabel(f"{tr('Total Score:')} --")
        self.total_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        details_layout.addWidget(self.total_label)

        self.groups_table = QTableWidget()
        self.groups_table.setColumnCount(2)
        self.groups_table.setHorizontalHeaderLabels([tr("Group"), tr("Score")])
        self.groups_table.horizontalHeader().setStretchLastSection(True)
        self.groups_table.verticalHeader().setVisible(False)
        details_layout.addWidget(self.groups_table)

        splitter.addWidget(details_group)
        splitter.setSizes([300, 500])
        layout.addWidget(splitter)

        # --- Buttons ---
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton(tr("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        self.apply_btn = QPushButton(tr("Apply Selected"))
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.apply_btn)

        layout.addLayout(button_layout)

    def populate_results(self):
        """Populate the results table."""
        self.results_table.setRowCount(len(self.results))

        for i, result in enumerate(self.results):
            score = calculate_total_score(result)
            std = _std_dev(_group_scores(result))

            # Result number
            num_item = QTableWidgetItem(f"{i + 1}")
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.results_table.setItem(i, 0, num_item)

            # Total score
            score_item = QTableWidgetItem(f"{score:.1f}" + (" ★" if i == 0 else ""))
            score_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if i == 0:
                score_item.setForeground(Qt.GlobalColor.darkGreen)
            self.results_table.setItem(i, 1, score_item)

            # Group std dev
            std_item = QTableWidgetItem(f"{std:.2f}")
            std_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.results_table.setItem(i, 2, std_item)

        if self.results:
            self.results_table.selectRow(0)

    def on_selection_changed(self):
        selected = self.results_table.selectedItems()
        if not selected:
            self.apply_btn.setEnabled(False)
            self.clear_details()
            return

        row = selected[0].row()
        self.selected_result = self.results[row]
        self.apply_btn.setEnabled(True)
        self.update_details()

    def clear_details(self):
        self.total_label.setText(f"{tr('Total Score:')} --")
        self.groups_table.setRowCount(0)

    def update_details(self):
        if not self.selected_result:
            return

        total_score = calculate_total_score(self.selected_result)
        self.total_label.setText(f"{tr('Total Score:')} {total_score:.1f}")

        groups = self.selected_result.groups
        scores = _group_scores(self.selected_result)
        std = _std_dev(scores)

        # Groups + 2 summary rows (Mean, σ)
        self.groups_table.setRowCount(len(groups) + 2)

        for i, (group, score) in enumerate(zip(groups, scores)):
            self.groups_table.setItem(i, 0, QTableWidgetItem(group.name))
            score_item = QTableWidgetItem(f"{score:.1f}")
            score_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.groups_table.setItem(i, 1, score_item)

        # Separator-style Mean row
        mean_val = sum(scores) / len(scores) if scores else 0.0
        mean_label = QTableWidgetItem(tr("Mean"))
        mean_label.setForeground(Qt.GlobalColor.darkGray)
        mean_score = QTableWidgetItem(f"{mean_val:.1f}")
        mean_score.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        mean_score.setForeground(Qt.GlobalColor.darkGray)
        self.groups_table.setItem(len(groups), 0, mean_label)
        self.groups_table.setItem(len(groups), 1, mean_score)

        # σ row — colour-coded: green if low, red if high (relative to mean)
        std_label = QTableWidgetItem(tr("Std Dev (σ)"))
        std_label.setForeground(Qt.GlobalColor.darkGray)
        std_score = QTableWidgetItem(f"{std:.2f}")
        std_score.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if mean_val != 0:
            ratio = std / abs(mean_val)
            if ratio < 0.2:
                std_score.setForeground(Qt.GlobalColor.darkGreen)
            elif ratio > 0.5:
                std_score.setForeground(Qt.GlobalColor.red)
            else:
                std_score.setForeground(Qt.GlobalColor.darkGray)
        self.groups_table.setItem(len(groups) + 1, 0, std_label)
        self.groups_table.setItem(len(groups) + 1, 1, std_score)

    def get_selected_result(self) -> Project | None:
        return self.selected_result
