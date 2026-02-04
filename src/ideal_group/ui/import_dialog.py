"""Import dialog for Excel column mapping."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QTableWidget, QTableWidgetItem, QGroupBox,
    QFormLayout, QListWidget, QListWidgetItem, QCheckBox,
    QFileDialog, QMessageBox, QRadioButton, QButtonGroup, QWidget
)
from PySide6.QtCore import Qt

from ..excel_import import read_excel_columns, read_excel_preview
from ..models import ColumnMapping
from ..translations import tr


class ImportDialog(QDialog):
    """Dialog for importing Excel file and mapping columns."""
    
    def __init__(self, parent=None, excel_path: str = None):
        super().__init__(parent)
        self.excel_path = excel_path
        self.columns = []
        self.column_mapping = ColumnMapping()
        
        self.setWindowTitle("Import Excel File")
        self.setMinimumSize(700, 500)
        self.setup_ui()
        
        if excel_path:
            self.load_excel(excel_path)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # File selection
        file_layout = QHBoxLayout()
        self.file_label = QLabel(tr("No file selected"))
        self.browse_btn = QPushButton(tr("Browse..."))
        self.browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(self.browse_btn)
        layout.addLayout(file_layout)
        
        # Preview table
        preview_group = QGroupBox(tr("Preview"))
        preview_layout = QVBoxLayout(preview_group)
        self.preview_table = QTableWidget()
        self.preview_table.setMaximumHeight(150)
        preview_layout.addWidget(self.preview_table)
        layout.addWidget(preview_group)
        
        # Column mapping
        mapping_group = QGroupBox(tr("Column Mapping"))
        mapping_layout = QFormLayout(mapping_group)
        
        self.id_combo = QComboBox()
        mapping_layout.addRow(tr("ID Column:"), self.id_combo)
        
        # Name column options
        name_widget = QWidget()
        name_layout = QVBoxLayout(name_widget)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(4)
        
        # Radio buttons for name mode
        self.name_mode_group = QButtonGroup(self)
        self.single_name_radio = QRadioButton(tr("Single column"))
        self.separate_name_radio = QRadioButton(tr("Firstname + Lastname"))
        self.name_mode_group.addButton(self.single_name_radio, 0)
        self.name_mode_group.addButton(self.separate_name_radio, 1)
        self.single_name_radio.setChecked(True)
        
        radio_layout = QHBoxLayout()
        radio_layout.addWidget(self.single_name_radio)
        radio_layout.addWidget(self.separate_name_radio)
        radio_layout.addStretch()
        name_layout.addLayout(radio_layout)
        
        # Single name combo
        self.name_combo = QComboBox()
        self.single_name_widget = QWidget()
        single_layout = QHBoxLayout(self.single_name_widget)
        single_layout.setContentsMargins(0, 0, 0, 0)
        single_layout.addWidget(QLabel(tr("Name:")))
        single_layout.addWidget(self.name_combo, 1)
        name_layout.addWidget(self.single_name_widget)
        
        # Separate name combos
        self.separate_name_widget = QWidget()
        separate_layout = QHBoxLayout(self.separate_name_widget)
        separate_layout.setContentsMargins(0, 0, 0, 0)
        self.firstname_combo = QComboBox()
        self.lastname_combo = QComboBox()
        separate_layout.addWidget(QLabel(tr("Firstname:")))
        separate_layout.addWidget(self.firstname_combo, 1)
        separate_layout.addWidget(QLabel(tr("Lastname:")))
        separate_layout.addWidget(self.lastname_combo, 1)
        name_layout.addWidget(self.separate_name_widget)
        self.separate_name_widget.hide()
        
        # Connect radio buttons
        self.single_name_radio.toggled.connect(self._on_name_mode_changed)
        
        mapping_layout.addRow(tr("Name Column:"), name_widget)
        
        self.liked_combo = QComboBox()
        self.disliked_combo = QComboBox()
        
        mapping_layout.addRow(tr("Liked Column:"), self.liked_combo)
        mapping_layout.addRow(tr("Disliked Column:"), self.disliked_combo)
        layout.addWidget(mapping_group)
        
        # Characteristics selection
        char_group = QGroupBox(tr("Characteristics (select columns to use)"))
        char_layout = QVBoxLayout(char_group)
        self.char_list = QListWidget()
        char_layout.addWidget(self.char_list)
        layout.addWidget(char_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.cancel_btn = QPushButton(tr("Cancel"))
        self.cancel_btn.clicked.connect(self.reject)
        self.import_btn = QPushButton(tr("Import"))
        self.import_btn.clicked.connect(self.accept_import)
        self.import_btn.setEnabled(False)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.import_btn)
        layout.addLayout(btn_layout)
    
    def _on_name_mode_changed(self, checked):
        """Toggle between single and separate name columns."""
        if checked:  # Single name mode
            self.single_name_widget.show()
            self.separate_name_widget.hide()
        else:  # Separate name mode
            self.single_name_widget.hide()
            self.separate_name_widget.show()
    
    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Excel File", "",
            "Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        if path:
            self.load_excel(path)
    
    def load_excel(self, path: str):
        try:
            self.excel_path = path
            self.file_label.setText(path)
            
            # Read columns
            self.columns = read_excel_columns(path)
            
            # Update combos
            for combo in [self.id_combo, self.name_combo, self.firstname_combo,
                         self.lastname_combo, self.liked_combo, self.disliked_combo]:
                combo.clear()
                combo.addItems(self.columns)
            
            # Auto-detect common column names
            self.auto_detect_columns()
            
            # Update preview
            preview = read_excel_preview(path, 5)
            self.preview_table.setColumnCount(len(preview.columns))
            self.preview_table.setRowCount(len(preview))
            self.preview_table.setHorizontalHeaderLabels(list(preview.columns))
            
            for i, row in preview.iterrows():
                for j, val in enumerate(row):
                    self.preview_table.setItem(i, j, QTableWidgetItem(str(val)))
            
            # Update characteristics list
            self.char_list.clear()
            for col in self.columns:
                item = QListWidgetItem(col)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                self.char_list.addItem(item)
            
            # Auto-check likely characteristics
            self.auto_detect_characteristics()
            
            self.import_btn.setEnabled(True)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file: {e}")
    
    def auto_detect_columns(self):
        """Try to auto-detect column mappings based on common names."""
        lower_cols = {c.lower(): c for c in self.columns}
        
        # ID detection
        for name in ['id', 'student_id', 'studentid', 'nr', 'nummer']:
            if name in lower_cols:
                self.id_combo.setCurrentText(lower_cols[name])
                break
        
        # Check for separate firstname/lastname columns
        has_firstname = False
        has_lastname = False
        for name in ['firstname', 'vorname', 'first_name', 'first']:
            if name in lower_cols:
                self.firstname_combo.setCurrentText(lower_cols[name])
                has_firstname = True
                break
        for name in ['lastname', 'nachname', 'last_name', 'last', 'surname']:
            if name in lower_cols:
                self.lastname_combo.setCurrentText(lower_cols[name])
                has_lastname = True
                break
        
        if has_firstname and has_lastname:
            self.separate_name_radio.setChecked(True)
        else:
            # Single name detection
            for name in ['name', 'student', 'schüler', 'schueler']:
                if name in lower_cols:
                    self.name_combo.setCurrentText(lower_cols[name])
                    break
        
        # Liked detection
        for name in ['liked', 'likes', 'freunde', 'friends', 'wunsch']:
            if name in lower_cols:
                self.liked_combo.setCurrentText(lower_cols[name])
                break
        
        # Disliked detection
        for name in ['disliked', 'dislikes', 'avoid', 'meiden']:
            if name in lower_cols:
                self.disliked_combo.setCurrentText(lower_cols[name])
                break
    
    def auto_detect_characteristics(self):
        """Auto-check columns that look like characteristics."""
        mapped = {
            self.id_combo.currentText(),
            self.name_combo.currentText(),
            self.firstname_combo.currentText(),
            self.lastname_combo.currentText(),
            self.liked_combo.currentText(),
            self.disliked_combo.currentText()
        }
        
        for i in range(self.char_list.count()):
            item = self.char_list.item(i)
            col_name = item.text()
            # Check if not a mapped column and looks like a characteristic
            if col_name not in mapped:
                lower = col_name.lower()
                if any(kw in lower for kw in ['inklusion', 'nawi', 'bläser', 'blaeser', 
                                               'schnitt', 'note', 'klasse']):
                    item.setCheckState(Qt.CheckState.Checked)
    
    def accept_import(self):
        """Validate and accept the import."""
        # Build column mapping
        self.column_mapping.id_column = self.id_combo.currentText()
        self.column_mapping.use_separate_name_columns = self.separate_name_radio.isChecked()
        
        if self.column_mapping.use_separate_name_columns:
            self.column_mapping.firstname_column = self.firstname_combo.currentText()
            self.column_mapping.lastname_column = self.lastname_combo.currentText()
            self.column_mapping.name_column = ""
        else:
            self.column_mapping.name_column = self.name_combo.currentText()
            self.column_mapping.firstname_column = ""
            self.column_mapping.lastname_column = ""
        
        self.column_mapping.liked_column = self.liked_combo.currentText()
        self.column_mapping.disliked_column = self.disliked_combo.currentText()
        
        # Get selected characteristics
        self.column_mapping.characteristic_columns = {}
        for i in range(self.char_list.count()):
            item = self.char_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                col_name = item.text()
                self.column_mapping.characteristic_columns[col_name] = col_name
        
        self.accept()
    
    def get_mapping(self) -> ColumnMapping:
        return self.column_mapping
    
    def get_excel_path(self) -> str:
        return self.excel_path
