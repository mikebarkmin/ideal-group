"""Graph visualization of student like/dislike relationships."""

import math
import random
from PySide6.QtWidgets import (
    QMainWindow, QVBoxLayout, QGraphicsView, QGraphicsScene,
    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsTextItem, QWidget
)
from PySide6.QtCore import Qt, QPointF, QTimer
from PySide6.QtGui import QPen, QBrush, QColor, QFont

from ..models import Project
from ..translations import tr


class StudentNodeItem(QGraphicsEllipseItem):
    """Clickable student node."""
    
    def __init__(self, student_id, x, y, radius, graph_window):
        super().__init__(x - radius, y - radius, radius * 2, radius * 2)
        self.student_id = student_id
        self.graph_window = graph_window
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def mousePressEvent(self, event):
        self.graph_window.on_node_clicked(self.student_id)
        event.accept()


class RelationshipGraphWindow(QMainWindow):
    """Window showing a graph of student relationships."""
    
    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.project = project
        self.selected_student_id = None
        self.node_items = {}  # student_id -> StudentNodeItem
        self.edge_items = []  # List of (line_items, from_id, to_id, edge_type)
        self.info_items = []  # Items for the info panel
        
        self.setWindowTitle(tr("Student Relationships"))
        self.setMinimumSize(800, 600)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(self.view.renderHints().Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        layout.addWidget(self.view)
        
        # Debounce timer for resize
        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self._do_rebuild)
        
        self.build_graph()
    
    def resizeEvent(self, event):
        """Handle window resize with debounce."""
        super().resizeEvent(event)
        self.resize_timer.start(300)  # 300ms debounce
    
    def _do_rebuild(self):
        """Rebuild graph after resize debounce."""
        self.build_graph()
    
    def on_node_clicked(self, student_id):
        """Handle click on a student node."""
        if self.selected_student_id == student_id:
            # Deselect if clicking same node
            self.selected_student_id = None
        else:
            self.selected_student_id = student_id
        self._update_highlight()
        self._update_info_panel()
    
    def _update_highlight(self):
        """Update visual highlighting based on selection."""
        selected_id = self.selected_student_id
        
        # Get connected student IDs
        connected_ids = set()
        if selected_id is not None:
            student = self.project.get_student_by_id(selected_id)
            if student:
                connected_ids.update(student.liked)
                connected_ids.update(student.disliked)
                # Also include students who like/dislike the selected student
                for s in self.project.students:
                    if selected_id in s.liked or selected_id in s.disliked:
                        connected_ids.add(s.id)
        
        # Update node appearances
        for sid, node in self.node_items.items():
            original_color = node.data(0)
            if original_color is None:
                original_color = QColor(59, 130, 246)
            
            if selected_id is None:
                # No selection - all nodes normal with their group color
                node.setBrush(QBrush(original_color))
                node.setOpacity(1.0)
            elif sid == selected_id:
                # Selected node - highlighted yellow
                node.setBrush(QBrush(QColor(251, 191, 36)))
                node.setOpacity(1.0)
            elif sid in connected_ids:
                # Connected node - normal with group color
                node.setBrush(QBrush(original_color))
                node.setOpacity(1.0)
            else:
                # Unconnected node - dimmed with group color
                node.setBrush(QBrush(original_color))
                node.setOpacity(0.2)
        
        # Update edge appearances
        for line_items, from_id, to_id, edge_type in self.edge_items:
            is_connected = (
                selected_id is None or
                from_id == selected_id or
                to_id == selected_id
            )
            opacity = 1.0 if is_connected else 0.1
            for item in line_items:
                item.setOpacity(opacity)
    
    def build_graph(self):
        """Build the graph visualization."""
        self.scene.clear()
        self.node_items.clear()
        self.edge_items.clear()
        
        students = self.project.students
        if not students:
            return
        
        # Get current view size for layout
        view_rect = self.view.viewport().rect()
        width = max(600, view_rect.width() - 40)
        height = max(400, view_rect.height() - 40)
        
        # Calculate positions using force-directed layout
        positions = self._force_directed_layout(students, width, height)
        
        # Build student-to-group mapping for colors
        student_group = {}
        for group in self.project.groups:
            for sid in group.student_ids:
                student_group[sid] = group.name
        
        # Generate colors for each group
        group_colors = {}
        base_colors = [
            QColor(59, 130, 246),   # Blue
            QColor(16, 185, 129),   # Green
            QColor(245, 158, 11),   # Amber
            QColor(139, 92, 246),   # Purple
            QColor(236, 72, 153),   # Pink
            QColor(6, 182, 212),    # Cyan
            QColor(249, 115, 22),   # Orange
            QColor(132, 204, 22),   # Lime
        ]
        for i, group in enumerate(self.project.groups):
            group_colors[group.name] = base_colors[i % len(base_colors)]
        unassigned_color = QColor(107, 114, 128)  # Gray
        
        # Draw edges first (so nodes appear on top)
        green_pen = QPen(QColor(34, 197, 94), 2)
        red_pen = QPen(QColor(239, 68, 68), 2)
        
        for student in students:
            start_pos = positions[student.id]
            
            # Draw liked edges
            for liked_id in student.liked:
                if liked_id in positions:
                    end_pos = positions[liked_id]
                    items = self._draw_arrow(start_pos, end_pos, green_pen)
                    if items:
                        self.edge_items.append((items, student.id, liked_id, 'like'))
            
            # Draw disliked edges
            for disliked_id in student.disliked:
                if disliked_id in positions:
                    end_pos = positions[disliked_id]
                    items = self._draw_arrow(start_pos, end_pos, red_pen)
                    if items:
                        self.edge_items.append((items, student.id, disliked_id, 'dislike'))
        
        # Draw nodes
        node_radius = 25
        font = QFont()
        font.setPointSize(8)
        
        for student in students:
            pos = positions[student.id]
            
            # Get group color for this student
            group_name = student_group.get(student.id)
            if group_name and group_name in group_colors:
                node_color = group_colors[group_name]
            else:
                node_color = unassigned_color
            
            node_brush = QBrush(node_color)
            node_pen = QPen(node_color.darker(150), 2)
            
            # Node circle (clickable)
            ellipse = StudentNodeItem(student.id, pos.x(), pos.y(), node_radius, self)
            ellipse.setBrush(node_brush)
            ellipse.setPen(node_pen)
            ellipse.setData(0, node_color)  # Store original color
            self.scene.addItem(ellipse)
            self.node_items[student.id] = ellipse
            
            # Student name label
            name = student.name
            if len(name) > 10:
                name = name[:9] + "…"
            
            text = QGraphicsTextItem(name)
            text.setFont(font)
            text.setDefaultTextColor(Qt.GlobalColor.white)
            
            text_rect = text.boundingRect()
            text.setPos(
                pos.x() - text_rect.width() / 2,
                pos.y() - text_rect.height() / 2
            )
            self.scene.addItem(text)
        
        # Add legend
        self._add_legend()
        
        # Restore highlight if a student was selected
        if self.selected_student_id is not None:
            self._update_highlight()
    
    def _draw_arrow(self, start: QPointF, end: QPointF, pen: QPen):
        """Draw an arrow from start to end. Returns list of created items."""
        node_radius = 25
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.sqrt(dx * dx + dy * dy)
        
        if length < node_radius * 2:
            return []
        
        dx /= length
        dy /= length
        
        start_adjusted = QPointF(
            start.x() + dx * node_radius,
            start.y() + dy * node_radius
        )
        end_adjusted = QPointF(
            end.x() - dx * node_radius,
            end.y() - dy * node_radius
        )
        
        items = []
        
        # Main line
        line = QGraphicsLineItem(
            start_adjusted.x(), start_adjusted.y(),
            end_adjusted.x(), end_adjusted.y()
        )
        line.setPen(pen)
        self.scene.addItem(line)
        items.append(line)
        
        # Arrowhead
        arrow_size = 10
        angle = math.atan2(dy, dx)
        
        arrow_p1 = QPointF(
            end_adjusted.x() - arrow_size * math.cos(angle - math.pi / 6),
            end_adjusted.y() - arrow_size * math.sin(angle - math.pi / 6)
        )
        arrow_p2 = QPointF(
            end_adjusted.x() - arrow_size * math.cos(angle + math.pi / 6),
            end_adjusted.y() - arrow_size * math.sin(angle + math.pi / 6)
        )
        
        line1 = QGraphicsLineItem(
            end_adjusted.x(), end_adjusted.y(),
            arrow_p1.x(), arrow_p1.y()
        )
        line1.setPen(pen)
        self.scene.addItem(line1)
        items.append(line1)
        
        line2 = QGraphicsLineItem(
            end_adjusted.x(), end_adjusted.y(),
            arrow_p2.x(), arrow_p2.y()
        )
        line2.setPen(pen)
        self.scene.addItem(line2)
        items.append(line2)
        
        return items
    
    def _force_directed_layout(self, students, width, height, iterations=100):
        """Calculate node positions using Fruchterman-Reingold force-directed algorithm."""
        n = len(students)
        if n == 0:
            return {}
        
        area = width * height
        k = math.sqrt(area / n) * 1.8  # Increased spacing factor
        
        # Build student-to-group mapping
        student_group = {}
        for group in self.project.groups:
            for sid in group.student_ids:
                student_group[sid] = group.name
        
        # Build adjacency for attraction (likes create attraction)
        edges = set()
        for student in students:
            for liked_id in student.liked:
                edges.add((student.id, liked_id))
        
        # Build group edges (students in same group attract each other)
        group_edges = set()
        for group in self.project.groups:
            sids = group.student_ids
            for i, sid1 in enumerate(sids):
                for sid2 in sids[i + 1:]:
                    group_edges.add((sid1, sid2))
        
        # Initialize positions - cluster by group
        positions = {}
        group_centers = {}
        num_groups = len(self.project.groups) + 1  # +1 for unassigned
        
        # Calculate group center positions in a circle with more spread
        for i, group in enumerate(self.project.groups):
            angle = 2 * math.pi * i / max(num_groups, 1)
            cx = width / 2 + (width / 2.5) * math.cos(angle)
            cy = height / 2 + (height / 2.5) * math.sin(angle)
            group_centers[group.name] = (cx, cy)
        
        # Unassigned center
        unassigned_angle = 2 * math.pi * len(self.project.groups) / max(num_groups, 1)
        unassigned_center = (
            width / 2 + (width / 2.5) * math.cos(unassigned_angle),
            height / 2 + (height / 2.5) * math.sin(unassigned_angle)
        )
        
        # Initialize positions near group centers with more spread
        for student in students:
            group_name = student_group.get(student.id)
            if group_name and group_name in group_centers:
                cx, cy = group_centers[group_name]
            else:
                cx, cy = unassigned_center
            
            positions[student.id] = [
                cx + random.uniform(-80, 80),
                cy + random.uniform(-80, 80)
            ]
        
        temp = width / 8
        
        for iteration in range(iterations):
            displacements = {s.id: [0.0, 0.0] for s in students}
            
            for i, s1 in enumerate(students):
                for s2 in students[i + 1:]:
                    dx = positions[s1.id][0] - positions[s2.id][0]
                    dy = positions[s1.id][1] - positions[s2.id][1]
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist < 0.01:
                        dist = 0.01
                    
                    force = (k * k) / dist
                    fx = (dx / dist) * force
                    fy = (dy / dist) * force
                    
                    displacements[s1.id][0] += fx
                    displacements[s1.id][1] += fy
                    displacements[s2.id][0] -= fx
                    displacements[s2.id][1] -= fy
            
            # Attractive forces for likes
            for (id1, id2) in edges:
                if id1 not in positions or id2 not in positions:
                    continue
                dx = positions[id1][0] - positions[id2][0]
                dy = positions[id1][1] - positions[id2][1]
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < 0.01:
                    dist = 0.01
                
                force = (dist * dist) / k
                fx = (dx / dist) * force
                fy = (dy / dist) * force
                
                displacements[id1][0] -= fx
                displacements[id1][1] -= fy
                displacements[id2][0] += fx
                displacements[id2][1] += fy
            
            # Attractive forces for same-group students
            for (id1, id2) in group_edges:
                if id1 not in positions or id2 not in positions:
                    continue
                dx = positions[id1][0] - positions[id2][0]
                dy = positions[id1][1] - positions[id2][1]
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < 0.01:
                    dist = 0.01
                
                # Moderate attraction for group members
                force = (dist * dist) / k * 0.8
                fx = (dx / dist) * force
                fy = (dy / dist) * force
                
                displacements[id1][0] -= fx
                displacements[id1][1] -= fy
                displacements[id2][0] += fx
                displacements[id2][1] += fy
            
            for student in students:
                dx = displacements[student.id][0]
                dy = displacements[student.id][1]
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > 0:
                    d = min(dist, temp)
                    positions[student.id][0] += (dx / dist) * d
                    positions[student.id][1] += (dy / dist) * d
                
                positions[student.id][0] = max(50, min(width - 50, positions[student.id][0]))
                positions[student.id][1] = max(50, min(height - 50, positions[student.id][1]))
            
            temp *= 0.95
        
        return {sid: QPointF(pos[0], pos[1]) for sid, pos in positions.items()}
    
    def _add_legend(self):
        """Add a legend to the graph."""
        x, y = 10, 10
        
        # Edge legend
        green_pen = QPen(QColor(34, 197, 94), 2)
        line = QGraphicsLineItem(x, y + 7, x + 30, y + 7)
        line.setPen(green_pen)
        self.scene.addItem(line)
        
        text = QGraphicsTextItem(tr("Likes"))
        text.setPos(x + 35, y - 3)
        self.scene.addItem(text)
        
        y += 25
        red_pen = QPen(QColor(239, 68, 68), 2)
        line = QGraphicsLineItem(x, y + 7, x + 30, y + 7)
        line.setPen(red_pen)
        self.scene.addItem(line)
        
        text = QGraphicsTextItem(tr("Dislikes"))
        text.setPos(x + 35, y - 3)
        self.scene.addItem(text)
        
        # Group color legend
        y += 30
        base_colors = [
            QColor(59, 130, 246),   # Blue
            QColor(16, 185, 129),   # Green
            QColor(245, 158, 11),   # Amber
            QColor(139, 92, 246),   # Purple
            QColor(236, 72, 153),   # Pink
            QColor(6, 182, 212),    # Cyan
            QColor(249, 115, 22),   # Orange
            QColor(132, 204, 22),   # Lime
        ]
        
        for i, group in enumerate(self.project.groups):
            color = base_colors[i % len(base_colors)]
            
            circle = QGraphicsEllipseItem(x, y, 14, 14)
            circle.setBrush(QBrush(color))
            circle.setPen(QPen(color.darker(150), 1))
            self.scene.addItem(circle)
            
            text = QGraphicsTextItem(group.name)
            text.setPos(x + 20, y - 3)
            self.scene.addItem(text)
            
            y += 22
        
        # Unassigned
        if self.project.groups:
            unassigned_color = QColor(107, 114, 128)
            circle = QGraphicsEllipseItem(x, y, 14, 14)
            circle.setBrush(QBrush(unassigned_color))
            circle.setPen(QPen(unassigned_color.darker(150), 1))
            self.scene.addItem(circle)
            
            text = QGraphicsTextItem(tr("Unassigned"))
            text.setPos(x + 20, y - 3)
            self.scene.addItem(text)
    
    def _update_info_panel(self):
        """Update the student info panel in bottom-left corner."""
        # Remove old info items
        for item in self.info_items:
            self.scene.removeItem(item)
        self.info_items.clear()
        
        if self.selected_student_id is None:
            return
        
        student = self.project.get_student_by_id(self.selected_student_id)
        if not student:
            return
        
        # Find which group the student is in
        group_name = tr("Unassigned")
        for group in self.project.groups:
            if student.id in group.student_ids:
                group_name = group.name
                break
        
        # Calculate panel height based on characteristics count
        num_characteristics = len(student.characteristics)
        panel_height = 50 + num_characteristics * 18
        
        # Get view dimensions for positioning
        view_rect = self.view.viewport().rect()
        scene_rect = self.view.mapToScene(view_rect).boundingRect()
        
        # Position in bottom-left
        x = scene_rect.left() + 10
        y = scene_rect.bottom() - panel_height - 10
        
        # Background rectangle
        bg_rect = self.scene.addRect(
            x - 5, y - 5, 220, panel_height,
            QPen(QColor(200, 200, 200)),
            QBrush(QColor(255, 255, 255, 230))
        )
        self.info_items.append(bg_rect)
        
        # Student name (bold)
        font_bold = QFont()
        font_bold.setPointSize(10)
        font_bold.setBold(True)
        
        name_text = QGraphicsTextItem(student.name)
        name_text.setFont(font_bold)
        name_text.setPos(x, y)
        self.scene.addItem(name_text)
        self.info_items.append(name_text)
        
        font_normal = QFont()
        font_normal.setPointSize(9)
        
        y += 22
        
        # Group
        group_text = QGraphicsTextItem(f"{tr('Group')}: {group_name}")
        group_text.setFont(font_normal)
        group_text.setPos(x, y)
        self.scene.addItem(group_text)
        self.info_items.append(group_text)
        
        y += 20
        
        # Characteristics
        for char_name, char_value in student.characteristics.items():
            char_text = QGraphicsTextItem(f"{char_name}: {char_value}")
            char_text.setFont(font_normal)
            char_text.setDefaultTextColor(QColor(80, 80, 80))
            char_text.setPos(x, y)
            self.scene.addItem(char_text)
            self.info_items.append(char_text)
            y += 18
