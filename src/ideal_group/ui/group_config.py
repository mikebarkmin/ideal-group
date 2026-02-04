"""Group configuration widget."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox, QDialog, QFormLayout, QDialogButtonBox,
    QMessageBox
)
from PySide6.QtCore import Signal, Qt

from ..models import Group, Constraint, ConstraintType
from ..translations import tr


class ConstraintDialog(QDialog):
    """Dialog for adding/editing a constraint."""
    
    def __init__(self, parent=None, characteristics: list[str] = None, constraint: Constraint = None):
        super().__init__(parent)
        self.characteristics = characteristics or []
        self.constraint = constraint
        
        self.setWindowTitle(tr("Add Constraint") if constraint is None else tr("Edit Constraint"))
        self.setup_ui()
        
        if constraint:
            self.load_constraint(constraint)
    
    def setup_ui(self):
        layout = QFormLayout(self)
        
        self.char_combo = QComboBox()
        self.char_combo.addItems(self.characteristics)
        layout.addRow(tr("Characteristic:"), self.char_combo)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems([tr("ALL - All must be in group"), 
                                   tr("SOME - Some should be in group"),
                                   tr("MAX - Maximum count in group")])
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        layout.addRow(tr("Constraint Type:"), self.type_combo)
        
        self.value_spin = QSpinBox()
        self.value_spin.setRange(1, 100)
        self.value_spin.setValue(3)
        self.value_label = QLabel(tr("Maximum count:"))
        layout.addRow(self.value_label, self.value_spin)
        
        self.on_type_changed(0)
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
    
    def on_type_changed(self, index):
        # Show value only for MAX and SOME constraints
        show_value = index >= 1  # SOME or MAX
        self.value_spin.setVisible(show_value)
        self.value_label.setVisible(show_value)
        if index == 1:  # SOME
            self.value_label.setText(tr("Target count:"))
        else:
            self.value_label.setText(tr("Maximum count:"))
    
    def load_constraint(self, constraint: Constraint):
        if constraint.characteristic in self.characteristics:
            self.char_combo.setCurrentText(constraint.characteristic)
        
        type_map = {
            ConstraintType.ALL: 0,
            ConstraintType.SOME: 1,
            ConstraintType.MAX: 2
        }
        self.type_combo.setCurrentIndex(type_map.get(constraint.constraint_type, 0))
        
        if constraint.value:
            self.value_spin.setValue(constraint.value)
    
    def get_constraint(self) -> Constraint:
        type_map = {
            0: ConstraintType.ALL,
            1: ConstraintType.SOME,
            2: ConstraintType.MAX
        }
        
        return Constraint(
            characteristic=self.char_combo.currentText(),
            constraint_type=type_map[self.type_combo.currentIndex()],
            value=self.value_spin.value() if self.type_combo.currentIndex() >= 1 else None
        )


class GroupConfigWidget(QWidget):
    """Widget for configuring groups and their constraints."""
    
    groups_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.groups: list[Group] = []
        self.characteristics: list[str] = []
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Groups table
        group_box = QGroupBox(tr("Groups"))
        group_layout = QVBoxLayout(group_box)
        
        self.groups_table = QTableWidget()
        self.groups_table.setColumnCount(3)
        self.groups_table.setHorizontalHeaderLabels([tr("Name"), tr("Max Size"), tr("Constraints")])
        self.groups_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.groups_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.groups_table.itemSelectionChanged.connect(self.on_selection_changed)
        self.groups_table.cellChanged.connect(self.on_cell_changed)
        group_layout.addWidget(self.groups_table)
        
        # Group buttons
        btn_layout = QHBoxLayout()
        self.add_group_btn = QPushButton(tr("Add Group"))
        self.add_group_btn.clicked.connect(self.add_group)
        self.remove_group_btn = QPushButton(tr("Remove Group"))
        self.remove_group_btn.clicked.connect(self.remove_group)
        self.remove_group_btn.setEnabled(False)
        btn_layout.addWidget(self.add_group_btn)
        btn_layout.addWidget(self.remove_group_btn)
        btn_layout.addStretch()
        group_layout.addLayout(btn_layout)
        
        layout.addWidget(group_box)
        
        # Constraints for selected group
        constraint_box = QGroupBox(tr("Constraints for Selected Group"))
        constraint_layout = QVBoxLayout(constraint_box)
        
        self.constraints_table = QTableWidget()
        self.constraints_table.setColumnCount(3)
        self.constraints_table.setHorizontalHeaderLabels([tr("Characteristic"), tr("Type"), tr("Value")])
        self.constraints_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        constraint_layout.addWidget(self.constraints_table)
        
        # Constraint buttons
        const_btn_layout = QHBoxLayout()
        self.add_const_btn = QPushButton(tr("Add Constraint"))
        self.add_const_btn.clicked.connect(self.add_constraint)
        self.add_const_btn.setEnabled(False)
        self.remove_const_btn = QPushButton(tr("Remove Constraint"))
        self.remove_const_btn.clicked.connect(self.remove_constraint)
        self.remove_const_btn.setEnabled(False)
        const_btn_layout.addWidget(self.add_const_btn)
        const_btn_layout.addWidget(self.remove_const_btn)
        const_btn_layout.addStretch()
        constraint_layout.addLayout(const_btn_layout)
        
        layout.addWidget(constraint_box)
    
    def set_characteristics(self, characteristics: list[str]):
        """Set available characteristics for constraints."""
        self.characteristics = characteristics
    
    def set_groups(self, groups: list[Group]):
        """Set the groups to display."""
        self.groups = groups
        self.refresh_groups_table()
    
    def get_groups(self) -> list[Group]:
        """Get the current groups."""
        return self.groups
    
    def refresh_groups_table(self):
        """Refresh the groups table."""
        # Block signals to prevent recursion
        self.groups_table.blockSignals(True)
        
        self.groups_table.setRowCount(len(self.groups))
        
        for i, group in enumerate(self.groups):
            # Name (editable)
            name_item = QTableWidgetItem(group.name)
            self.groups_table.setItem(i, 0, name_item)
            
            # Max size (use spin box)
            size_item = QTableWidgetItem(str(group.max_size))
            self.groups_table.setItem(i, 1, size_item)
            
            # Constraints summary
            constraints_str = ", ".join(
                f"{c.characteristic}({c.constraint_type.value})"
                for c in group.constraints
            )
            const_item = QTableWidgetItem(constraints_str)
            const_item.setFlags(const_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.groups_table.setItem(i, 2, const_item)
        
        self.groups_table.blockSignals(False)
    
    def on_cell_changed(self, row, col):
        """Handle cell edits in the groups table."""
        if row >= len(self.groups):
            return
        
        item = self.groups_table.item(row, col)
        if not item:
            return
        
        if col == 0:  # Name
            self.groups[row].name = item.text()
        elif col == 1:  # Max size
            try:
                self.groups[row].max_size = int(item.text())
            except ValueError:
                item.setText(str(self.groups[row].max_size))
        
        self.groups_changed.emit()
    
    def on_selection_changed(self):
        """Handle selection change in groups table."""
        selected = self.groups_table.selectedItems()
        has_selection = len(selected) > 0
        
        self.remove_group_btn.setEnabled(has_selection)
        self.add_const_btn.setEnabled(has_selection)
        
        if has_selection:
            row = self.groups_table.currentRow()
            self.refresh_constraints_table(row)
        else:
            self.constraints_table.setRowCount(0)
    
    def refresh_constraints_table(self, group_index: int):
        """Refresh constraints table for selected group."""
        if group_index < 0 or group_index >= len(self.groups):
            return
        
        group = self.groups[group_index]
        self.constraints_table.setRowCount(len(group.constraints))
        
        for i, constraint in enumerate(group.constraints):
            self.constraints_table.setItem(i, 0, QTableWidgetItem(constraint.characteristic))
            self.constraints_table.setItem(i, 1, QTableWidgetItem(constraint.constraint_type.value))
            self.constraints_table.setItem(i, 2, QTableWidgetItem(
                str(constraint.value) if constraint.value else "-"
            ))
        
        self.remove_const_btn.setEnabled(len(group.constraints) > 0)
    
    def add_group(self):
        """Add a new group."""
        name = f"Group {chr(65 + len(self.groups))}"  # A, B, C, ...
        group = Group(name=name, max_size=30)
        self.groups.append(group)
        self.refresh_groups_table()
        self.groups_changed.emit()
    
    def remove_group(self):
        """Remove selected group."""
        row = self.groups_table.currentRow()
        if 0 <= row < len(self.groups):
            del self.groups[row]
            self.refresh_groups_table()
            self.groups_changed.emit()
    
    def add_constraint(self):
        """Add constraint to selected group."""
        row = self.groups_table.currentRow()
        if row < 0 or row >= len(self.groups):
            return
        
        if not self.characteristics:
            QMessageBox.warning(self, tr("No Characteristics"),
                              tr("Import data first to define characteristics."))
            return
        
        dialog = ConstraintDialog(self, self.characteristics)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            constraint = dialog.get_constraint()
            self.groups[row].constraints.append(constraint)
            self.refresh_constraints_table(row)
            self.refresh_groups_table()
            self.groups_changed.emit()
    
    def remove_constraint(self):
        """Remove selected constraint."""
        group_row = self.groups_table.currentRow()
        const_row = self.constraints_table.currentRow()
        
        if (0 <= group_row < len(self.groups) and 
            0 <= const_row < len(self.groups[group_row].constraints)):
            del self.groups[group_row].constraints[const_row]
            self.refresh_constraints_table(group_row)
            self.refresh_groups_table()
            self.groups_changed.emit()
