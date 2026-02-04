"""Weights configuration widget."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox,
    QGroupBox, QFormLayout, QScrollArea, QFrame
)
from PySide6.QtCore import Signal, Qt

from ..models import Weights
from ..translations import tr


class WeightsWidget(QWidget):
    """Widget for configuring algorithm weights."""
    
    weights_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.weights = Weights()
        self.characteristic_spins: dict[str, QDoubleSpinBox] = {}
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Base weights
        base_group = QGroupBox(tr("Base Weights"))
        base_layout = QFormLayout(base_group)
        
        self.likes_spin = QDoubleSpinBox()
        self.likes_spin.setRange(0, 10)
        self.likes_spin.setSingleStep(0.1)
        self.likes_spin.setValue(1.0)
        self.likes_spin.valueChanged.connect(self.on_weights_changed)
        base_layout.addRow(tr("Likes Weight:"), self.likes_spin)
        
        self.dislikes_spin = QDoubleSpinBox()
        self.dislikes_spin.setRange(0, 10)
        self.dislikes_spin.setSingleStep(0.1)
        self.dislikes_spin.setValue(2.0)
        self.dislikes_spin.valueChanged.connect(self.on_weights_changed)
        base_layout.addRow(tr("Dislikes Weight:"), self.dislikes_spin)
        
        layout.addWidget(base_group)
        
        # Characteristic weights
        self.char_group = QGroupBox(tr("Characteristic Weights"))
        self.char_layout = QFormLayout(self.char_group)
        layout.addWidget(self.char_group)
        
        layout.addStretch()
        
        # Formula display
        formula_group = QGroupBox(tr("Score Formula"))
        formula_layout = QVBoxLayout(formula_group)
        
        self.formula_label = QLabel()
        self.formula_label.setWordWrap(True)
        self.formula_label.setTextFormat(Qt.TextFormat.RichText)
        self.formula_label.setStyleSheet("font-family: monospace; font-size: 11px; padding: 8px; background-color: #f5f5f5; border-radius: 4px;")
        formula_layout.addWidget(self.formula_label)
        
        explanation = QLabel(
            f"<b>{tr('Where:')}</b><br>"
            f"• likes = {tr('likes = number of liked students in same group')}<br>"
            f"• dislikes = {tr('dislikes = number of disliked students in same group')}<br>"
            f"• {tr('Constraint violations add penalties (50-100 points each)')}"
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("font-size: 10px; color: #666;")
        formula_layout.addWidget(explanation)
        
        layout.addWidget(formula_group)
        
        self._update_formula()
    
    def set_characteristics(self, characteristics: list[str]):
        """Set available characteristics and create weight inputs."""
        # Clear existing
        for spin in self.characteristic_spins.values():
            spin.deleteLater()
        self.characteristic_spins.clear()
        
        # Clear layout
        while self.char_layout.count():
            item = self.char_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add new
        for char in characteristics:
            spin = QDoubleSpinBox()
            spin.setRange(0, 10)
            spin.setSingleStep(0.1)
            spin.setValue(self.weights.characteristic_weights.get(char, 1.0))
            spin.valueChanged.connect(self.on_weights_changed)
            self.char_layout.addRow(f"{char}:", spin)
            self.characteristic_spins[char] = spin
        
        self._update_formula()
    
    def set_weights(self, weights: Weights):
        """Set weights to display."""
        self.weights = weights
        self.likes_spin.setValue(weights.likes_weight)
        self.dislikes_spin.setValue(weights.dislikes_weight)
        
        for char, spin in self.characteristic_spins.items():
            spin.setValue(weights.characteristic_weights.get(char, 1.0))
        
        self._update_formula()
    
    def get_weights(self) -> Weights:
        """Get current weights."""
        self.weights.likes_weight = self.likes_spin.value()
        self.weights.dislikes_weight = self.dislikes_spin.value()
        
        self.weights.characteristic_weights = {
            char: spin.value()
            for char, spin in self.characteristic_spins.items()
        }
        
        return self.weights
    
    def on_weights_changed(self):
        self._update_formula()
        self.weights_changed.emit()
    
    def _update_formula(self):
        """Update the formula display with current weights."""
        likes_w = self.likes_spin.value()
        dislikes_w = self.dislikes_spin.value()
        
        terms = []
        
        if likes_w > 0:
            terms.append(f"(likes × {likes_w})")
        
        if dislikes_w > 0:
            if terms:
                terms.append(f"− (dislikes × {dislikes_w})")
            else:
                terms.append(f"−(dislikes × {dislikes_w})")
        
        # Add characteristic terms
        for char_name, spin in self.characteristic_spins.items():
            weight = spin.value()
            if weight > 0:
                short_name = char_name[:10]
                terms.append(f"+ ({short_name} × {weight})")
        
        if terms:
            formula = "<b>Score</b> = " + " ".join(terms)
        else:
            formula = "<b>Score</b> = 0"
        
        self.formula_label.setText(formula)
