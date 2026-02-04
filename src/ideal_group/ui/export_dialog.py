"""Export dialog for Excel export."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QFormLayout, QFileDialog, QMessageBox,
    QCheckBox
)
from PySide6.QtCore import Qt

from ..models import Project
from ..translations import tr


class ExportDialog(QDialog):
    """Dialog for configuring Excel export."""
    
    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.project = project
        self.export_path = None
        
        self.setWindowTitle(tr("Export to Excel"))
        self.setMinimumWidth(400)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Column names configuration
        columns_group = QGroupBox(tr("Column Names"))
        columns_layout = QFormLayout(columns_group)
        
        self.id_name_edit = QLineEdit("id")
        columns_layout.addRow(tr("ID Column:"), self.id_name_edit)
        
        # Name options
        self.use_separate_names = QCheckBox(tr("Use separate firstname/lastname columns"))
        self.use_separate_names.toggled.connect(self._on_name_mode_changed)
        columns_layout.addRow("", self.use_separate_names)
        
        self.name_edit = QLineEdit("name")
        self.name_label = QLabel(tr("Name Column:"))
        columns_layout.addRow(self.name_label, self.name_edit)
        
        self.firstname_edit = QLineEdit("firstname")
        self.firstname_label = QLabel(tr("Firstname Column:"))
        columns_layout.addRow(self.firstname_label, self.firstname_edit)
        self.firstname_label.hide()
        self.firstname_edit.hide()
        
        self.lastname_edit = QLineEdit("lastname")
        self.lastname_label = QLabel(tr("Lastname Column:"))
        columns_layout.addRow(self.lastname_label, self.lastname_edit)
        self.lastname_label.hide()
        self.lastname_edit.hide()
        
        self.group_edit = QLineEdit("group")
        columns_layout.addRow(tr("Group Column:"), self.group_edit)
        
        layout.addWidget(columns_group)
        
        # File selection
        file_group = QGroupBox(tr("Output File"))
        file_layout = QHBoxLayout(file_group)
        
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText(tr("Select output file..."))
        file_layout.addWidget(self.file_edit)
        
        browse_btn = QPushButton(tr("Browse..."))
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)
        
        layout.addWidget(file_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton(tr("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        export_btn = QPushButton(tr("Export"))
        export_btn.clicked.connect(self._do_export)
        btn_layout.addWidget(export_btn)
        
        layout.addLayout(btn_layout)
    
    def _on_name_mode_changed(self, checked):
        """Toggle between single and separate name columns."""
        if checked:
            self.name_label.hide()
            self.name_edit.hide()
            self.firstname_label.show()
            self.firstname_edit.show()
            self.lastname_label.show()
            self.lastname_edit.show()
        else:
            self.name_label.show()
            self.name_edit.show()
            self.firstname_label.hide()
            self.firstname_edit.hide()
            self.lastname_label.hide()
            self.lastname_edit.hide()
    
    def _browse_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, tr("Export to Excel"), "",
            "Excel Files (*.xlsx);;All Files (*)"
        )
        if path:
            if not path.endswith('.xlsx'):
                path += '.xlsx'
            self.file_edit.setText(path)
    
    def _do_export(self):
        """Perform the export."""
        path = self.file_edit.text().strip()
        if not path:
            QMessageBox.warning(self, tr("Error"), tr("Please select an output file."))
            return
        
        try:
            import pandas as pd
            
            # Build data
            rows = []
            
            # Create group lookup
            student_groups = {}
            for group in self.project.groups:
                for sid in group.student_ids:
                    student_groups[sid] = group.name
            
            for student in self.project.students:
                group_name = student_groups.get(student.id, "")
                
                if self.use_separate_names.isChecked():
                    # Split name into first/last
                    name_parts = student.name.split(None, 1)
                    firstname = name_parts[0] if name_parts else ""
                    lastname = name_parts[1] if len(name_parts) > 1 else ""
                    
                    rows.append({
                        self.id_name_edit.text(): student.id,
                        self.firstname_edit.text(): firstname,
                        self.lastname_edit.text(): lastname,
                        self.group_edit.text(): group_name
                    })
                else:
                    rows.append({
                        self.id_name_edit.text(): student.id,
                        self.name_edit.text(): student.name,
                        self.group_edit.text(): group_name
                    })
            
            df = pd.DataFrame(rows)
            df.to_excel(path, index=False)
            
            self.export_path = path
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, tr("Error"), f"{tr('Export failed:')} {e}")
    
    def get_export_path(self) -> str:
        return self.export_path
