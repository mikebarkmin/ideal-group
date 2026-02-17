"""Main application window."""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QMenuBar, QMenu, QToolBar, QPushButton, QFileDialog,
    QMessageBox, QStatusBar, QProgressDialog, QTabWidget, QComboBox, QLabel,
    QInputDialog, QDialog
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction

from ..models import Project, Group, ConstraintType, Constraint
from ..config import save_project, load_project
from ..excel_import import import_students
from ..algorithm import optimize_with_restarts, check_hard_constraints, calculate_total_score, calculate_constraint_penalty_details, calculate_group_score
from ..translations import tr, set_language, get_language, available_languages

from .import_dialog import ImportDialog
from .group_config import GroupConfigWidget
from .weights_widget import WeightsWidget
from .kanban_board import KanbanBoard
from .info_widget import InfoWidget
from .export_dialog import ExportDialog
from .relationship_graph import RelationshipGraphWindow
from .results_dialog import ResultsDialog

MAX_ITERATIONS_PER_RESTART = 25000


class OptimizationThread(QThread):
    """Thread for running the optimization algorithm."""
    
    progress = Signal(int, float, float, int)  # iteration, temperature, score, restart_num
    finished_signal = Signal(object)  # list of optimized projects
    
    def __init__(self, project: Project, num_restarts: int = 10):
        super().__init__()
        self.project = project
        self.num_restarts = num_restarts
    
    def run(self):
        def progress_callback(iteration, temperature, score, restart_num):
            self.progress.emit(iteration, temperature, score, restart_num)
        
        results = optimize_with_restarts(
            self.project,
            num_restarts=self.num_restarts,
            max_iterations=MAX_ITERATIONS_PER_RESTART,
            progress_callback=progress_callback,
            return_all_results=True
        )
        
        self.finished_signal.emit(results)


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.project = Project()
        self.project_path: str = None
        self.optimization_thread: OptimizationThread = None
        self.optimization_results: list[Project] = []  # Store results for switching
        
        self.setWindowTitle(tr("Ideal Group - Student Grouping Optimizer"))
        self.setMinimumSize(1200, 700)
        
        self.setup_ui()
        self.setup_menu()
        self.setup_toolbar()
        self.setup_statusbar()
    
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - Configuration
        left_panel = QTabWidget()
        left_panel.setMinimumWidth(300)
        left_panel.setMaximumWidth(400)
        
        # Groups tab
        self.group_config = GroupConfigWidget()
        self.group_config.groups_changed.connect(self.on_groups_changed)
        left_panel.addTab(self.group_config, tr("Groups"))
        
        # Weights tab
        self.weights_widget = WeightsWidget()
        self.weights_widget.weights_changed.connect(self.on_weights_changed)
        left_panel.addTab(self.weights_widget, tr("Weights"))
        
        # Info tab
        self.info_widget = InfoWidget()
        left_panel.addTab(self.info_widget, tr("Info"))
        
        splitter.addWidget(left_panel)
        
        # Right panel - Kanban board
        self.kanban_board = KanbanBoard()
        self.kanban_board.assignment_changed.connect(self.on_assignment_changed)
        splitter.addWidget(self.kanban_board)
        
        # Set splitter sizes
        splitter.setSizes([350, 850])
        
        layout.addWidget(splitter)
    
    def setup_menu(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu(tr("File"))
        
        new_action = QAction(tr("New Project"), self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_project)
        file_menu.addAction(new_action)
        
        open_action = QAction(tr("Open Project..."), self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_project)
        file_menu.addAction(open_action)
        
        save_action = QAction(tr("Save Project"), self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_current_project)
        file_menu.addAction(save_action)
        
        save_as_action = QAction(tr("Save Project As..."), self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.save_project_as)
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        import_action = QAction(tr("Import Excel..."), self)
        import_action.setShortcut("Ctrl+I")
        import_action.triggered.connect(self.import_excel)
        file_menu.addAction(import_action)
        
        export_action = QAction(tr("Export Excel..."), self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self.export_excel)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        quit_action = QAction(tr("Quit"), self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)
        
        # Algorithm menu
        algo_menu = menubar.addMenu(tr("Algorithm"))
        
        run_action = QAction(tr("Run Optimization"), self)
        run_action.setShortcut("F5")
        run_action.triggered.connect(self.run_optimization)
        algo_menu.addAction(run_action)
        
        self.switch_result_action = QAction(tr("Switch Result..."), self)
        self.switch_result_action.setShortcut("F6")
        self.switch_result_action.triggered.connect(self.switch_result)
        self.switch_result_action.setEnabled(False)
        algo_menu.addAction(self.switch_result_action)
        
        check_action = QAction(tr("Check Constraints"), self)
        check_action.triggered.connect(self.check_constraints)
        algo_menu.addAction(check_action)
        
        # View menu
        view_menu = menubar.addMenu(tr("View"))
        
        graph_action = QAction(tr("Relationship Graph"), self)
        graph_action.setShortcut("Ctrl+G")
        graph_action.triggered.connect(self.show_relationship_graph)
        view_menu.addAction(graph_action)
        
        # Language menu
        lang_menu = menubar.addMenu("🌐")
        for code, name in available_languages():
            action = QAction(name, self)
            action.setData(code)
            action.triggered.connect(lambda checked, c=code: self.change_language(c))
            lang_menu.addAction(action)
    
    def setup_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        self.import_btn = QPushButton(tr("📂 Import Excel"))
        self.import_btn.clicked.connect(self.import_excel)
        toolbar.addWidget(self.import_btn)
        
        toolbar.addSeparator()
        
        self.run_btn = QPushButton(tr("▶️ Run Optimization"))
        self.run_btn.clicked.connect(self.run_optimization)
        toolbar.addWidget(self.run_btn)
        
        self.check_btn = QPushButton(tr("✓ Check Constraints"))
        self.check_btn.clicked.connect(self.check_constraints)
        toolbar.addWidget(self.check_btn)
        
        toolbar.addSeparator()
        
        self.graph_btn = QPushButton(tr("🔗 Relationship Graph"))
        self.graph_btn.clicked.connect(self.show_relationship_graph)
        toolbar.addWidget(self.graph_btn)
    
    def setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage(tr("Ready"))
    
    def change_language(self, lang_code: str):
        """Change the application language and refresh UI."""
        set_language(lang_code)
        # Notify user that restart is needed for full effect
        QMessageBox.information(
            self, 
            "Language Changed", 
            "Language changed. Please restart the application for full effect."
        )
    
    def new_project(self):
        self.project = Project()
        self.project_path = None
        self.refresh_ui()
        self.statusbar.showMessage(tr("New project created"))
    
    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "",
            "Ideal Group Project (*.igp);;JSON Files (*.json);;All Files (*)"
        )
        if path:
            try:
                self.project = load_project(path)
                self.project_path = path
                self.refresh_ui()
                self.statusbar.showMessage(f"Opened: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open project: {e}")
    
    def save_current_project(self):
        if self.project_path:
            self.save_to_path(self.project_path)
        else:
            self.save_project_as()
    
    def save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "",
            "Ideal Group Project (*.igp);;JSON Files (*.json);;All Files (*)"
        )
        if path:
            if not path.endswith(('.igp', '.json')):
                path += '.igp'
            self.save_to_path(path)
    
    def save_to_path(self, path: str):
        try:
            # Update project from UI
            self.project.groups = self.group_config.get_groups()
            self.project.weights = self.weights_widget.get_weights()
            
            save_project(self.project, path)
            self.project_path = path
            self.statusbar.showMessage(f"Saved: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save project: {e}")
    
    def import_excel(self):
        dialog = ImportDialog(self)
        if dialog.exec():
            try:
                path = dialog.get_excel_path()
                mapping = dialog.get_mapping()
                
                students = import_students(path, mapping)
                
                self.project.excel_path = path
                self.project.column_mapping = mapping
                self.project.students = students
                
                # Update characteristics in config widgets
                characteristics = list(mapping.characteristic_columns.keys())
                self.group_config.set_characteristics(characteristics)
                self.weights_widget.set_characteristics(characteristics)
                
                self.refresh_ui()
                self.statusbar.showMessage(f"Imported {len(students)} students from {path}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import: {e}")
    
    def export_excel(self):
        """Export current assignments to Excel."""
        if not self.project.students:
            QMessageBox.warning(self, tr("No Data"), tr("Please import student data first."))
            return
        
        dialog = ExportDialog(self.project, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            path = dialog.get_export_path()
            if path:
                self.statusbar.showMessage(f"{tr('Exported to:')} {path}")
    
    def run_optimization(self):
        if not self.project.students:
            QMessageBox.warning(self, tr("No Data"), tr("Please import student data first."))
            return
        
        if not self.project.groups:
            QMessageBox.warning(self, tr("No Groups"), tr("Please create groups first."))
            return
        
        # Ask user for number of runs
        num_restarts, ok = QInputDialog.getInt(
            self, 
            tr("Optimization Runs"),
            tr("Number of optimization runs (more = better results, slower):"),
            value=10,
            minValue=1,
            maxValue=30
        )
        if not ok:
            return
        
        # Update project from UI
        self.project.groups = self.group_config.get_groups()
        self.project.weights = self.weights_widget.get_weights()
        
        # Store current score to compare later
        self._score_before_optimization = calculate_total_score(self.project)
        
        # Store for progress callback
        self._num_restarts = num_restarts
        
        # Total iterations across all restarts
        total_iterations = num_restarts * MAX_ITERATIONS_PER_RESTART
        
        # Create progress dialog as instance variable to prevent garbage collection
        self.progress_dialog = QProgressDialog(
            tr("Optimizing group assignments...") + f" ({tr('Run')} 1/{num_restarts})", 
            tr("Cancel"), 0, total_iterations, self
        )
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.show()
        
        # Run optimization in thread
        self.optimization_thread = OptimizationThread(self.project, num_restarts)
        self.optimization_thread.progress.connect(self.on_optimization_progress)
        self.optimization_thread.finished_signal.connect(self.on_optimization_finished)
        self.progress_dialog.canceled.connect(self.on_optimization_canceled)
        
        self.optimization_thread.start()
    
    def on_optimization_progress(self, iteration, temperature, score, restart_num):
        dialog = getattr(self, 'progress_dialog', None)
        num_restarts = getattr(self, '_num_restarts', 5)
        if dialog is not None:
            dialog.setValue(iteration)
            dialog.setLabelText(
                f"{tr('Run')} {restart_num}/{num_restarts} - {tr('Score')}: {score:.1f}"
            )
    
    def on_optimization_finished(self, results: list):
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
        
        if not results:
            self.statusbar.showMessage(tr("Optimization produced no results"))
            return
        
        # Store results for later switching
        self.optimization_results = results
        self.switch_result_action.setEnabled(True)
        
        old_score = getattr(self, '_score_before_optimization', float('-inf'))
        
        # Show results selection dialog
        self._apply_selected_result(old_score)
    
    def switch_result(self):
        """Show the results dialog to switch to a different result."""
        if not self.optimization_results:
            QMessageBox.information(self, tr("No Results"), tr("Run optimization first to generate results."))
            return
        
        old_score = calculate_total_score(self.project)
        self._apply_selected_result(old_score)
    
    def _apply_selected_result(self, old_score: float):
        """Show results dialog and apply selected result."""
        dialog = ResultsDialog(self.optimization_results, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected = dialog.get_selected_result()
            if selected:
                new_score = calculate_total_score(selected)
                self.project = selected
                self.group_config.set_groups(self.project.groups)
                self.refresh_ui()
                self.statusbar.showMessage(
                    f"{tr('Score')}: {old_score:.1f} -> {new_score:.1f} ({new_score - old_score:+.1f})"
                )
    
    def on_optimization_canceled(self):
        if self.optimization_thread and self.optimization_thread.isRunning():
            self.optimization_thread.terminate()
            self.optimization_thread.wait()
        self.progress_dialog = None
        self.statusbar.showMessage("Optimization canceled")
    
    def check_constraints(self):
        valid, violations = check_hard_constraints(self.project)
        
        if valid:
            QMessageBox.information(self, "Constraints Check", 
                                   "✓ All constraints are satisfied!")
        else:
            msg = "Constraint violations:\n\n" + "\n".join(f"• {v}" for v in violations)
            QMessageBox.warning(self, "Constraints Check", msg)
    
    def show_relationship_graph(self):
        """Show the student relationship graph."""
        if not self.project.students:
            QMessageBox.warning(self, tr("No Data"), tr("Please import student data first."))
            return
        
        graph_window = RelationshipGraphWindow(self.project, self)
        graph_window.show()
    
    def on_groups_changed(self):
        self.project.groups = self.group_config.get_groups()
        self.kanban_board.rebuild_board()
    
    def on_weights_changed(self):
        self.project.weights = self.weights_widget.get_weights()
        self.kanban_board.refresh_all()
    
    def on_assignment_changed(self):
        # Sync weights from UI before calculating score
        self.project.weights = self.weights_widget.get_weights()
        
        # Update info widget
        self.info_widget.set_project(self.project)
        self.info_widget.refresh()
        
        # Calculate scores for status bar
        groups_sum = sum(calculate_group_score(self.project, g) for g in self.project.groups)
        total_penalty, _ = calculate_constraint_penalty_details(self.project)
        total_score = groups_sum - total_penalty
        
        # Check for violations
        valid, violations = check_hard_constraints(self.project)
        if valid:
            self.statusbar.showMessage(f"{tr('Total:')} {total_score:.1f} ({tr('Groups:')} {groups_sum:.1f})")
        else:
            self.statusbar.showMessage(f"{tr('Total:')} {total_score:.1f} ({tr('Groups:')} {groups_sum:.1f} - {tr('Penalties:')} {total_penalty:.0f}) ⚠️ {len(violations)} {tr('constraint violations')}")
    
    def refresh_ui(self):
        """Refresh all UI components from the project."""
        characteristics = list(self.project.column_mapping.characteristic_columns.keys())
        
        self.group_config.set_characteristics(characteristics)
        self.group_config.set_groups(self.project.groups)
        
        # Set weights before characteristics so spin boxes use correct values
        self.weights_widget.weights = self.project.weights
        self.weights_widget.set_characteristics(characteristics)
        self.weights_widget.set_weights(self.project.weights)
        
        self.info_widget.set_project(self.project)
        
        self.kanban_board.set_project(self.project)
