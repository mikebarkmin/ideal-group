"""Graph visualization of student like/dislike relationships."""

import math
import random
from PySide6.QtWidgets import (
    QMainWindow, QVBoxLayout, QGraphicsView, QGraphicsScene,
    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsTextItem, QWidget,
    QApplication
)
from PySide6.QtCore import Qt, QPointF, QTimer, QEvent
from PySide6.QtGui import QPen, QBrush, QColor, QFont, QPalette

from ..models import Project
from ..translations import tr


def _palette_color(role: QPalette.ColorRole) -> QColor:
    """Get a QColor from the current application palette."""
    return QApplication.palette().color(role)


def _is_dark_theme() -> bool:
    """Return True if the current palette is a dark theme."""
    return _palette_color(QPalette.ColorRole.Text).lightness() > 128


# Fixed semantic colors that adapt luminance to the active theme
def _like_color() -> QColor:
    return QColor(100, 220, 100) if _is_dark_theme() else QColor(34, 197, 94)

def _dislike_color() -> QColor:
    return QColor(255, 100, 100) if _is_dark_theme() else QColor(239, 68, 68)

def _selected_color() -> QColor:
    return QColor(251, 191, 36)  # Yellow works on both themes

def _unassigned_color() -> QColor:
    return QColor(160, 160, 160) if _is_dark_theme() else QColor(107, 114, 128)

def _info_panel_bg() -> QColor:
    color = _palette_color(QPalette.ColorRole.Base)
    color.setAlpha(230)
    return color

def _info_panel_border() -> QColor:
    return _palette_color(QPalette.ColorRole.Mid)

def _info_text_secondary() -> QColor:
    return _palette_color(QPalette.ColorRole.PlaceholderText)

def _legend_text_color() -> QColor:
    return _palette_color(QPalette.ColorRole.Text)


# Group colors — two sets, picked based on theme brightness
_GROUP_COLORS_LIGHT = [
    QColor(59, 130, 246),   # Blue
    QColor(16, 185, 129),   # Green
    QColor(245, 158, 11),   # Amber
    QColor(139, 92, 246),   # Purple
    QColor(236, 72, 153),   # Pink
    QColor(6, 182, 212),    # Cyan
    QColor(249, 115, 22),   # Orange
    QColor(132, 204, 22),   # Lime
]
_GROUP_COLORS_DARK = [
    QColor(96, 165, 250),   # Lighter Blue
    QColor(52, 211, 153),   # Lighter Green
    QColor(251, 191, 36),   # Lighter Amber
    QColor(167, 139, 250),  # Lighter Purple
    QColor(244, 114, 182),  # Lighter Pink
    QColor(34, 211, 238),   # Lighter Cyan
    QColor(251, 146, 60),   # Lighter Orange
    QColor(163, 230, 53),   # Lighter Lime
]

def _group_colors() -> list[QColor]:
    return _GROUP_COLORS_DARK if _is_dark_theme() else _GROUP_COLORS_LIGHT


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
        self.node_items = {}        # student_id -> StudentNodeItem
        self.edge_items = []        # List of (line_items, from_id, to_id, edge_type)
        self.info_items = []        # Items for the info panel

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

    # ------------------------------------------------------------------
    # Resize / rebuild
    # ------------------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_timer.start(300)

    def _do_rebuild(self):
        self.build_graph()

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def on_node_clicked(self, student_id):
        if self.selected_student_id == student_id:
            self.selected_student_id = None
        else:
            self.selected_student_id = student_id
        self._update_highlight()
        self._update_info_panel()

    def _update_highlight(self):
        selected_id = self.selected_student_id

        connected_ids = set()
        if selected_id is not None:
            student = self.project.get_student_by_id(selected_id)
            if student:
                connected_ids.update(student.liked)
                connected_ids.update(student.disliked)
                for s in self.project.students:
                    if selected_id in s.liked or selected_id in s.disliked:
                        connected_ids.add(s.id)

        for sid, node in self.node_items.items():
            original_color = node.data(0)
            if original_color is None:
                original_color = _group_colors()[0]

            if selected_id is None:
                node.setBrush(QBrush(original_color))
                node.setOpacity(1.0)
            elif sid == selected_id:
                node.setBrush(QBrush(_selected_color()))
                node.setOpacity(1.0)
            elif sid in connected_ids:
                node.setBrush(QBrush(original_color))
                node.setOpacity(1.0)
            else:
                node.setBrush(QBrush(original_color))
                node.setOpacity(0.2)

        for line_items, from_id, to_id, edge_type in self.edge_items:
            is_connected = (
                selected_id is None or
                from_id == selected_id or
                to_id == selected_id
            )
            opacity = 1.0 if is_connected else 0.1
            for item in line_items:
                item.setOpacity(opacity)

    # ------------------------------------------------------------------
    # Graph building
    # ------------------------------------------------------------------

    def build_graph(self):
        self.scene.clear()
        self.node_items.clear()
        self.edge_items.clear()

        students = self.project.students
        if not students:
            return

        view_rect = self.view.viewport().rect()
        width = max(600, view_rect.width() - 40)
        height = max(400, view_rect.height() - 40)

        positions = self._force_directed_layout(students, width, height)

        # Build student-to-group mapping
        student_group = {}
        for group in self.project.groups:
            for sid in group.student_ids:
                student_group[sid] = group.name

        # Map group name -> color using theme-appropriate palette
        colors = _group_colors()
        group_colors = {
            group.name: colors[i % len(colors)]
            for i, group in enumerate(self.project.groups)
        }

        # Draw edges first
        like_pen = QPen(_like_color(), 2)
        dislike_pen = QPen(_dislike_color(), 2)

        for student in students:
            start_pos = positions[student.id]
            for liked_id in student.liked:
                if liked_id in positions:
                    items = self._draw_arrow(start_pos, positions[liked_id], like_pen)
                    if items:
                        self.edge_items.append((items, student.id, liked_id, 'like'))
            for disliked_id in student.disliked:
                if disliked_id in positions:
                    items = self._draw_arrow(start_pos, positions[disliked_id], dislike_pen)
                    if items:
                        self.edge_items.append((items, student.id, disliked_id, 'dislike'))

        # Draw nodes
        node_radius = 25
        font = QFont()
        font.setPointSize(8)

        for student in students:
            pos = positions[student.id]

            group_name = student_group.get(student.id)
            node_color = group_colors.get(group_name, _unassigned_color()) if group_name else _unassigned_color()

            ellipse = StudentNodeItem(student.id, pos.x(), pos.y(), node_radius, self)
            ellipse.setBrush(QBrush(node_color))
            ellipse.setPen(QPen(node_color.darker(150), 2))
            ellipse.setData(0, node_color)
            self.scene.addItem(ellipse)
            self.node_items[student.id] = ellipse

            name = student.name if len(student.name) <= 10 else student.name[:9] + "…"
            text = QGraphicsTextItem(name)
            text.setFont(font)
            # White text is readable on all the saturated node colors
            text.setDefaultTextColor(Qt.GlobalColor.white)
            text_rect = text.boundingRect()
            text.setPos(
                pos.x() - text_rect.width() / 2,
                pos.y() - text_rect.height() / 2
            )
            self.scene.addItem(text)

        self._add_legend(group_colors)

        # Lock the scene rect so adding info panel items never expands it
        self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-20, -20, 20, 20))

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

        start_adj = QPointF(start.x() + dx * node_radius, start.y() + dy * node_radius)
        end_adj = QPointF(end.x() - dx * node_radius, end.y() - dy * node_radius)

        items = []

        line = QGraphicsLineItem(start_adj.x(), start_adj.y(), end_adj.x(), end_adj.y())
        line.setPen(pen)
        self.scene.addItem(line)
        items.append(line)

        arrow_size = 10
        angle = math.atan2(dy, dx)

        for sign in (+1, -1):
            a = QPointF(
                end_adj.x() - arrow_size * math.cos(angle - sign * math.pi / 6),
                end_adj.y() - arrow_size * math.sin(angle - sign * math.pi / 6)
            )
            wing = QGraphicsLineItem(end_adj.x(), end_adj.y(), a.x(), a.y())
            wing.setPen(pen)
            self.scene.addItem(wing)
            items.append(wing)

        return items

    def _force_directed_layout(self, students, width, height, iterations=100):
        """Fruchterman-Reingold force-directed layout."""
        n = len(students)
        if n == 0:
            return {}

        area = width * height
        k = math.sqrt(area / n) * 1.8

        student_group = {}
        for group in self.project.groups:
            for sid in group.student_ids:
                student_group[sid] = group.name

        edges = {(s.id, lid) for s in students for lid in s.liked}
        group_edges = {
            (sid1, sid2)
            for group in self.project.groups
            for i, sid1 in enumerate(group.student_ids)
            for sid2 in group.student_ids[i + 1:]
        }

        num_groups = len(self.project.groups) + 1
        group_centers = {}
        for i, group in enumerate(self.project.groups):
            angle = 2 * math.pi * i / max(num_groups, 1)
            group_centers[group.name] = (
                width / 2 + (width / 2.5) * math.cos(angle),
                height / 2 + (height / 2.5) * math.sin(angle)
            )

        ua = 2 * math.pi * len(self.project.groups) / max(num_groups, 1)
        unassigned_center = (
            width / 2 + (width / 2.5) * math.cos(ua),
            height / 2 + (height / 2.5) * math.sin(ua)
        )

        positions = {}
        for student in students:
            gn = student_group.get(student.id)
            cx, cy = group_centers.get(gn, unassigned_center) if gn else unassigned_center
            positions[student.id] = [cx + random.uniform(-80, 80), cy + random.uniform(-80, 80)]

        temp = width / 8

        for _ in range(iterations):
            displacements = {s.id: [0.0, 0.0] for s in students}

            for i, s1 in enumerate(students):
                for s2 in students[i + 1:]:
                    dx = positions[s1.id][0] - positions[s2.id][0]
                    dy = positions[s1.id][1] - positions[s2.id][1]
                    dist = max(math.sqrt(dx * dx + dy * dy), 0.01)
                    force = (k * k) / dist
                    fx, fy = (dx / dist) * force, (dy / dist) * force
                    displacements[s1.id][0] += fx
                    displacements[s1.id][1] += fy
                    displacements[s2.id][0] -= fx
                    displacements[s2.id][1] -= fy

            for (id1, id2), strength in [(e, 1.0) for e in edges] + [(e, 0.8) for e in group_edges]:
                if id1 not in positions or id2 not in positions:
                    continue
                dx = positions[id1][0] - positions[id2][0]
                dy = positions[id1][1] - positions[id2][1]
                dist = max(math.sqrt(dx * dx + dy * dy), 0.01)
                force = (dist * dist) / k * strength
                fx, fy = (dx / dist) * force, (dy / dist) * force
                displacements[id1][0] -= fx
                displacements[id1][1] -= fy
                displacements[id2][0] += fx
                displacements[id2][1] += fy

            for student in students:
                dx, dy = displacements[student.id]
                dist = max(math.sqrt(dx * dx + dy * dy), 0.01)
                d = min(dist, temp)
                positions[student.id][0] = max(50, min(width - 50, positions[student.id][0] + (dx / dist) * d))
                positions[student.id][1] = max(50, min(height - 50, positions[student.id][1] + (dy / dist) * d))

            temp *= 0.95

        return {sid: QPointF(pos[0], pos[1]) for sid, pos in positions.items()}

    # ------------------------------------------------------------------
    # Legend
    # ------------------------------------------------------------------

    def _add_legend(self, group_colors: dict):
        x, y = 10, 10
        text_color = _legend_text_color()

        for label, color in [(tr("Likes"), _like_color()), (tr("Dislikes"), _dislike_color())]:
            line = QGraphicsLineItem(x, y + 7, x + 30, y + 7)
            line.setPen(QPen(color, 2))
            self.scene.addItem(line)
            text = QGraphicsTextItem(label)
            text.setDefaultTextColor(text_color)
            text.setPos(x + 35, y - 3)
            self.scene.addItem(text)
            y += 25

        y += 5
        colors = _group_colors()
        for i, group in enumerate(self.project.groups):
            color = colors[i % len(colors)]
            circle = QGraphicsEllipseItem(x, y, 14, 14)
            circle.setBrush(QBrush(color))
            circle.setPen(QPen(color.darker(150), 1))
            self.scene.addItem(circle)
            text = QGraphicsTextItem(group.name)
            text.setDefaultTextColor(text_color)
            text.setPos(x + 20, y - 3)
            self.scene.addItem(text)
            y += 22

        if self.project.groups:
            uc = _unassigned_color()
            circle = QGraphicsEllipseItem(x, y, 14, 14)
            circle.setBrush(QBrush(uc))
            circle.setPen(QPen(uc.darker(150), 1))
            self.scene.addItem(circle)
            text = QGraphicsTextItem(tr("Unassigned"))
            text.setDefaultTextColor(text_color)
            text.setPos(x + 20, y - 3)
            self.scene.addItem(text)

    # ------------------------------------------------------------------
    # Info panel
    # ------------------------------------------------------------------

    def _update_info_panel(self):
        for item in self.info_items:
            self.scene.removeItem(item)
        self.info_items.clear()

        if self.selected_student_id is None:
            return

        student = self.project.get_student_by_id(self.selected_student_id)
        if not student:
            return

        group_name = tr("Unassigned")
        for group in self.project.groups:
            if student.id in group.student_ids:
                group_name = group.name
                break

        num_characteristics = len(student.characteristics)
        panel_height = 50 + num_characteristics * 18

        # Use the locked scene rect — never the viewport mapping, which
        # would place items outside the scene bounds and cause the view to shift
        scene_rect = self.scene.sceneRect()

        x = scene_rect.left() + 10
        y = scene_rect.bottom() - panel_height - 10

        bg_rect = self.scene.addRect(
            x - 5, y - 5, 220, panel_height,
            QPen(_info_panel_border()),
            QBrush(_info_panel_bg())
        )
        self.info_items.append(bg_rect)

        font_bold = QFont()
        font_bold.setPointSize(10)
        font_bold.setBold(True)

        text_color = _legend_text_color()
        secondary_color = _info_text_secondary()

        name_text = QGraphicsTextItem(student.name)
        name_text.setFont(font_bold)
        name_text.setDefaultTextColor(text_color)
        name_text.setPos(x, y)
        self.scene.addItem(name_text)
        self.info_items.append(name_text)

        font_normal = QFont()
        font_normal.setPointSize(9)

        y += 22
        group_text = QGraphicsTextItem(f"{tr('Group')}: {group_name}")
        group_text.setFont(font_normal)
        group_text.setDefaultTextColor(text_color)
        group_text.setPos(x, y)
        self.scene.addItem(group_text)
        self.info_items.append(group_text)

        y += 20
        for char_name, char_value in student.characteristics.items():
            char_text = QGraphicsTextItem(f"{char_name}: {char_value}")
            char_text.setFont(font_normal)
            char_text.setDefaultTextColor(secondary_color)
            char_text.setPos(x, y)
            self.scene.addItem(char_text)
            self.info_items.append(char_text)
            y += 18
