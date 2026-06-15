import json
import math
import os
import sys

from cad_core import (
    APP_TITLE,
    LAYER_BY_TOOL,
    THEMES,
    TOOL_LABELS,
    CadDocument,
    bounds as core_bounds,
    distance,
    export_dxf_text,
    export_svg_text,
    extend_item_end,
    item_distance,
    item_info,
    item_segments,
    make_item,
    move_item,
    normalize_item,
    offset_points,
    polygon_area,
    quantity_report,
    segment_intersection,
    template_drainage,
    template_footing,
    template_road_section,
    trim_item_end,
)

try:
    from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
    from PySide6.QtGui import QAction, QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QTransform
    from PySide6.QtWidgets import (
        QApplication,
        QButtonGroup,
        QColorDialog,
        QComboBox,
        QDockWidget,
        QFileDialog,
        QFormLayout,
        QGraphicsPathItem,
        QGraphicsRectItem,
        QGraphicsScene,
        QGraphicsTextItem,
        QGraphicsView,
        QHBoxLayout,
        QInputDialog,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QRadioButton,
        QScrollArea,
        QSlider,
        QSplashScreen,
        QTextEdit,
        QToolBar,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:  # pragma: no cover - runtime dependency guard
    raise SystemExit(
        "PySide6 is required for the new GUI. Install it with: python -m pip install PySide6"
    ) from exc

from theme.manager import ThemeManager
from units.manager import UnitManager


class CadGraphicsView(QGraphicsView):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setMouseTracking(True)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self._panning = False
        self._pan_start = None

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 0.87
        self.window.zoom_view(factor)

    def mousePressEvent(self, event):
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            self._panning = True
            self._pan_start = event.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
            return
        if event.button() == Qt.LeftButton:
            self.window.on_canvas_press(self.mapToScene(event.position().toPoint()))
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning and self._pan_start is not None:
            delta = event.position().toPoint() - self._pan_start
            self._pan_start = event.position().toPoint()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            return
        self.window.on_canvas_move(self.mapToScene(event.position().toPoint()))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            self._panning = False
            self._pan_start = None
            self.setCursor(Qt.ArrowCursor)
            return
        if event.button() == Qt.LeftButton:
            self.window.on_canvas_release(self.mapToScene(event.position().toPoint()))
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.window.on_canvas_double_click(self.mapToScene(event.position().toPoint()))
            return
        super().mouseDoubleClickEvent(event)


class CivilCAD(QMainWindow):
    def __init__(self):
        super().__init__()
        self.document = CadDocument()
        self.file_path = None
        self.theme_manager = ThemeManager(parent=self)
        self.unit_manager = UnitManager(parent=self)
        self.theme_manager.theme_changed.connect(self.on_theme_changed)
        self.unit_manager.unit_changed.connect(self.on_unit_changed)
        self.current_tool = "select"
        self.current_layer = "راه"
        self.grid_visible = True
        self.snap_grid = True
        self.snap_endpoint = True
        self.snap_midpoint = True
        self.snap_intersection = True
        self.ortho = False
        self.grid_size = 25
        self.selected = None
        self.clipboard = None
        self.start = None
        self.preview = None
        self.poly_points = []
        self.area_points = []
        self.measure_points = []
        self.snap_marker = None
        self.drag_last = None
        self.drag_snapshot = None
        self.scale_factor = 1.0
        self.last_saved_snapshot = self.save_snapshot()

        self.setWindowTitle(APP_TITLE)
        self.resize(1520, 900)
        self.setMinimumSize(1180, 720)
        self.setLayoutDirection(Qt.RightToLeft)
        QApplication.instance().setLayoutDirection(Qt.RightToLeft)
        QApplication.instance().setFont(QFont("Segoe UI", 10))

        self.build_actions()
        self.build_menu()
        self.build_main_layout()
        self.update_window_title()
        self.apply_theme()
        self.refresh_layers()
        self.update_properties()
        self.redraw()

    @property
    def items(self):
        return self.document.items

    @property
    def layers(self):
        return self.document.layers

    @property
    def theme_name(self):
        return self.theme_manager.active_name

    @property
    def theme(self):
        return self.theme_manager.active_theme

    @property
    def unit(self):
        return self.unit_manager.active_unit

    def build_actions(self):
        self.actions = {
            "new": QAction("نقشه جدید", self, shortcut="Ctrl+N", triggered=self.new_file),
            "open": QAction("باز کردن", self, shortcut="Ctrl+O", triggered=self.open_file),
            "save": QAction("ذخیره", self, shortcut="Ctrl+S", triggered=self.save_file),
            "save_as": QAction("ذخیره با نام", self, shortcut="Ctrl+Shift+S", triggered=self.save_as),
            "svg": QAction("خروجی SVG", self, triggered=self.export_svg),
            "dxf": QAction("خروجی DXF ساده", self, triggered=self.export_dxf),
            "exit": QAction("خروج", self, triggered=self.close),
            "undo": QAction("Undo", self, shortcut="Ctrl+Z", triggered=self.undo),
            "redo": QAction("Redo", self, shortcut="Ctrl+Y", triggered=self.redo),
            "copy": QAction("کپی", self, shortcut="Ctrl+C", triggered=self.copy_selected),
            "paste": QAction("جایگذاری", self, shortcut="Ctrl+V", triggered=self.paste_item),
            "delete": QAction("حذف", self, shortcut="Del", triggered=self.delete_selected),
            "offset": QAction("Offset", self, triggered=self.offset_selected),
            "trim": QAction("Trim تقریبی", self, triggered=self.trim_selected),
            "extend": QAction("Extend تقریبی", self, triggered=self.extend_selected),
            "zoom_fit": QAction("Zoom to Fit", self, shortcut="F2", triggered=self.zoom_to_fit),
            "zoom_in": QAction("Zoom In", self, shortcut="Ctrl++", triggered=lambda: self.zoom_view(1.2)),
            "zoom_out": QAction("Zoom Out", self, shortcut="Ctrl+-", triggered=lambda: self.zoom_view(1 / 1.2)),
            "zoom_reset": QAction("Zoom 100%", self, shortcut="Ctrl+0", triggered=self.zoom_reset),
            "report": QAction("گزارش متره", self, triggered=self.quantity_report),
            "road": QAction("مقطع راه", self, triggered=self.template_road_section),
            "footing": QAction("فونداسیون منفرد", self, triggered=self.template_footing),
            "drainage": QAction("پلان زهکشی ساده", self, triggered=self.template_drainage),
        }

    def build_menu(self):
        file_menu = self.menuBar().addMenu("فایل")
        for key in ("new", "open", "save", "save_as"):
            file_menu.addAction(self.actions[key])
        file_menu.addSeparator()
        for key in ("svg", "dxf"):
            file_menu.addAction(self.actions[key])
        file_menu.addSeparator()
        file_menu.addAction(self.actions["exit"])

        edit_menu = self.menuBar().addMenu("ویرایش")
        for key in ("undo", "redo", "copy", "paste", "delete"):
            edit_menu.addAction(self.actions[key])

        tools_menu = self.menuBar().addMenu("ابزار")
        for key in ("offset", "trim", "extend", "zoom_fit", "zoom_in", "zoom_out", "zoom_reset", "report"):
            tools_menu.addAction(self.actions[key])

        template_menu = self.menuBar().addMenu("قالب‌ها")
        for key in ("road", "footing", "drainage"):
            template_menu.addAction(self.actions[key])

    def build_toolbar(self):
        toolbar = QToolBar("ابزارهای سریع", self)
        toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, toolbar)
        self.populate_toolbar(toolbar)

    def build_main_layout(self):
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.toolbar = QToolBar("ابزارهای سریع", self)
        self.toolbar.setMovable(True)
        self.toolbar.setFloatable(False)
        self.populate_toolbar(self.toolbar)
        root_layout.addWidget(self.toolbar)

        self.scene = QGraphicsScene(self)
        self.view = CadGraphicsView(self)
        self.view.setScene(self.scene)
        self.view.setObjectName("cadCanvas")
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        root_layout.addWidget(self.view, 1)

        self.footer = QWidget()
        self.footer.setObjectName("footerBar")
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(12, 6, 12, 6)
        footer_layout.setSpacing(8)
        self.stats_label = QLabel("آیتمی وجود ندارد.")
        self.stats_label.setObjectName("footerStats")
        self.stats_label.setWordWrap(False)
        self.stats_label.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        self.status = QLabel("آماده")
        self.status.setObjectName("footerStatus")
        self.status.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        footer_layout.addWidget(self.stats_label, 1)
        footer_layout.addWidget(self.status, 0)
        root_layout.addWidget(self.footer)

        self.setCentralWidget(root)

        self.left_sidebar = self.make_sidebar("leftSidebar")
        self.build_tool_panel(self.left_sidebar)
        self.create_sidebar_dock("ابزارهای ترسیم", self.left_sidebar, Qt.LeftDockWidgetArea)

        self.right_sidebar = self.make_sidebar("rightSidebar")
        self.build_properties_panel(self.right_sidebar)
        self.create_sidebar_dock("لایه‌ها و مشخصات", self.right_sidebar, Qt.RightDockWidgetArea)

    def create_sidebar_dock(self, title, panel, area):
        dock = QDockWidget(title, self)
        dock.setObjectName(title.replace(" ", "_"))
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        dock.setWidget(self.wrap_sidebar(panel))
        self.addDockWidget(area, dock)
        return dock

    def populate_toolbar(self, toolbar):
        for key in ("new", "open", "save", "undo", "redo", "copy", "paste", "delete"):
            toolbar.addAction(self.actions[key])
        toolbar.addSeparator()
        for key in ("offset", "trim", "extend", "zoom_fit", "zoom_in", "zoom_out", "report", "svg", "dxf"):
            toolbar.addAction(self.actions[key])
        toolbar.addSeparator()

        toolbar.addWidget(QLabel("تم:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(self.theme_manager.names)
        self.theme_combo.setCurrentText(self.theme_name)
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        toolbar.addWidget(self.theme_combo)

        toolbar.addWidget(QLabel("واحد:"))
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(self.unit_manager.units)
        self.unit_combo.setCurrentText(self.unit)
        self.unit_combo.currentTextChanged.connect(self.change_unit)
        toolbar.addWidget(self.unit_combo)

    def make_sidebar(self, object_name):
        panel = QWidget()
        panel.setObjectName(object_name)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        return panel

    def wrap_sidebar(self, panel):
        scroll_area = QScrollArea()
        scroll_area.setObjectName("sidebarScroll")
        scroll_area.setWidget(panel)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setMinimumWidth(260)
        scroll_area.setMaximumWidth(340)
        return scroll_area

    def build_tool_panel(self, panel):
        layout = panel.layout()

        title = QLabel("ابزارهای ترسیم عمرانی")
        title.setObjectName("panelTitle")
        layout.addWidget(title)
        self.tool_group = QButtonGroup(self)
        groups = [
            ("عمومی", ["select", "line", "polyline", "arc", "text"]),
            ("سازه و معماری", ["beam", "column", "wall", "footing", "rebar"]),
            ("سایت و نقشه", ["drain", "contour", "dimension", "measure", "area"]),
        ]
        for group_name, keys in groups:
            group_label = QLabel(group_name)
            group_label.setObjectName("sectionTitle")
            layout.addWidget(group_label)
            for key in keys:
                radio = QRadioButton(TOOL_LABELS[key])
                radio.setLayoutDirection(Qt.RightToLeft)
                radio.setProperty("tool", key)
                radio.toggled.connect(self.on_tool_toggled)
                self.tool_group.addButton(radio)
                layout.addWidget(radio)
                if key == "select":
                    radio.setChecked(True)

        settings = QLabel("تنظیمات دقت ترسیم")
        settings.setObjectName("sectionTitle")
        layout.addWidget(settings)
        self.grid_button = self.make_toggle("نمایش شبکه", self.grid_visible, self.toggle_grid)
        self.snap_grid_button = self.make_toggle("Snap شبکه", self.snap_grid, self.toggle_snap_grid)
        self.snap_endpoint_button = self.make_toggle("Snap انتهای خط", self.snap_endpoint, self.toggle_snap_endpoint)
        self.snap_midpoint_button = self.make_toggle("Snap وسط خط", self.snap_midpoint, self.toggle_snap_midpoint)
        self.snap_intersection_button = self.make_toggle("Snap تقاطع", self.snap_intersection, self.toggle_snap_intersection)
        self.ortho_button = self.make_toggle("Ortho 90°", self.ortho, self.toggle_ortho)
        for button in (self.grid_button, self.snap_grid_button, self.snap_endpoint_button, self.snap_midpoint_button, self.snap_intersection_button, self.ortho_button):
            layout.addWidget(button)
        layout.addWidget(QLabel("اندازه شبکه"))
        self.grid_slider = QSlider(Qt.Horizontal)
        self.grid_slider.setRange(5, 200)
        self.grid_slider.setValue(self.grid_size)
        self.grid_slider.valueChanged.connect(self.change_grid_size)
        layout.addWidget(self.grid_slider)
        help_label = QLabel("راهنما:\n• کلیک چپ: شروع/انتخاب\n• درگ چپ: جابه‌جایی یا پیش‌نمایش\n• دابل‌کلیک: پایان پلی‌لاین/مساحت\n• راست/وسط موس: Pan\n• چرخ موس: Zoom\n• Ctrl+0: زوم ۱۰۰٪\n• Esc: لغو ابزار فعال")
        help_label.setObjectName("helpBox")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        layout.addStretch()

    def build_properties_panel(self, panel):
        layout = panel.layout()

        layout.addWidget(QLabel("مدیریت لایه‌ها"))
        layer_split = QHBoxLayout()
        layer_split.setSpacing(8)
        self.layer_list = QListWidget()
        self.layer_list.setMinimumHeight(140)
        self.layer_list.currentRowChanged.connect(self.on_layer_selected)
        layer_split.addWidget(self.layer_list, 1)
        layer_buttons = QVBoxLayout()
        layer_buttons.setSpacing(6)
        for text, callback in [
            ("+", self.add_layer),
            ("نام", self.rename_layer),
            ("رنگ", self.change_layer_color),
            ("👁", self.toggle_layer_visible),
            ("🔒", self.toggle_layer_lock),
        ]:
            button = QPushButton(text)
            button.clicked.connect(callback)
            layer_buttons.addWidget(button)
        layer_buttons.addStretch()
        layer_split.addLayout(layer_buttons)
        layout.addLayout(layer_split)

        layout.addWidget(QLabel("مشخصات آیتم انتخاب‌شده"))
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignRight)
        self.type_label = QLabel("-")
        self.layer_combo = QComboBox()
        self.width_edit = QLineEdit()
        self.color_edit = QLineEdit()
        self.text_edit = QLineEdit()
        form.addRow("نوع", self.type_label)
        form.addRow("لایه", self.layer_combo)
        form.addRow("ضخامت", self.width_edit)
        form.addRow("رنگ", self.color_edit)
        form.addRow("متن/برچسب", self.text_edit)
        layout.addWidget(form_widget)
        apply_button = QPushButton("اعمال مشخصات")
        apply_button.clicked.connect(self.apply_properties)
        color_button = QPushButton("انتخاب رنگ آیتم")
        color_button.clicked.connect(self.choose_item_color)
        layout.addWidget(apply_button)
        layout.addWidget(color_button)

        layout.addWidget(QLabel("خلاصه انتخاب"))
        self.info_box = QTextEdit()
        self.info_box.setReadOnly(True)
        self.info_box.setMinimumHeight(160)
        layout.addWidget(self.info_box, 1)

    def build_stats_dock(self):
        dock = QDockWidget("آمار نقشه", self)
        dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 8, 10, 8)
        self.stats_label = QLabel("آیتمی وجود ندارد.")
        self.stats_label.setWordWrap(True)
        layout.addWidget(self.stats_label)
        dock.setWidget(panel)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)

    def make_toggle(self, text, checked, callback):
        button = QPushButton(text)
        button.setCheckable(True)
        button.setChecked(checked)
        button.toggled.connect(callback)
        return button

    def apply_theme(self, name=None, theme=None):
        theme = theme or self.theme
        self.view.setBackgroundBrush(QBrush(QColor(theme["bg"])))
        self.setStyleSheet(f"""
            QMainWindow, QMenuBar, QMenu, QDockWidget, QWidget {{
                background: {theme['panel']};
                color: {theme['text']};
                font-family: 'Segoe UI';
            }}
            QGraphicsView {{ background: {theme['bg']}; border: 1px solid {theme['axis']}; }}
            QToolBar {{ background: {theme['panel2']}; spacing: 6px; padding: 6px; }}
            QDockWidget::title {{ background: {theme['panel2']}; padding: 6px; text-align: right; }}
            QWidget#footerBar {{ background: {theme['panel2']}; border-top: 1px solid {theme['axis']}; }}
            QWidget#leftSidebar, QWidget#rightSidebar {{ background: {theme['panel']}; }}
            QPushButton, QToolButton {{
                background: {theme['button']};
                color: {theme['button_text']};
                border: 1px solid {theme['axis']};
                border-radius: 5px;
                padding: 5px 8px;
            }}
            QPushButton:checked {{ background: {theme['accent']}; color: #020617; }}
            QLineEdit, QTextEdit, QListWidget, QComboBox {{
                background: {theme['entry']};
                color: {theme['text']};
                border: 1px solid {theme['axis']};
                border-radius: 4px;
                padding: 4px;
            }}
            QLabel#panelTitle {{ color: {theme['accent']}; font-weight: 700; font-size: 14px; }}
            QLabel#sectionTitle {{ background: {theme['panel2']}; padding: 5px; border-radius: 4px; }}
            QLabel#helpBox {{ background: {theme['panel2']}; color: {theme['muted']}; padding: 8px; border-radius: 6px; }}
            QStatusBar {{ background: {theme['panel2']}; color: {theme['text']}; }}
        """)

    def change_theme(self, name):
        self.theme_manager.set_theme(name)

    def on_theme_changed(self, name, theme):
        if hasattr(self, "theme_combo") and self.theme_combo.currentText() != name:
            self.theme_combo.blockSignals(True)
            self.theme_combo.setCurrentText(name)
            self.theme_combo.blockSignals(False)
        self.apply_theme(name, theme)
        self.redraw()
        self.update_window_title()

    def change_unit(self, unit):
        self.unit_manager.set_unit(unit)

    def on_unit_changed(self, unit):
        if hasattr(self, "unit_combo") and self.unit_combo.currentText() != unit:
            self.unit_combo.blockSignals(True)
            self.unit_combo.setCurrentText(unit)
            self.unit_combo.blockSignals(False)
        self.update_properties()
        self.redraw()
        self.update_window_title()

    def set_status(self, message):
        if hasattr(self, "status"):
            self.status.setText(message)

    def on_tool_toggled(self, checked):
        if not checked:
            return
        button = self.sender()
        self.current_tool = button.property("tool")
        preferred_layer = LAYER_BY_TOOL.get(self.current_tool)
        if preferred_layer in self.layers:
            self.current_layer = preferred_layer
            self.refresh_layers()
        self.cancel()

    def toggle_grid(self, checked):
        self.grid_visible = checked
        self.redraw()

    def toggle_snap_grid(self, checked):
        self.snap_grid = checked

    def toggle_snap_endpoint(self, checked):
        self.snap_endpoint = checked

    def toggle_snap_midpoint(self, checked):
        self.snap_midpoint = checked

    def toggle_snap_intersection(self, checked):
        self.snap_intersection = checked

    def toggle_ortho(self, checked):
        self.ortho = checked

    def change_grid_size(self, value):
        self.grid_size = value
        self.redraw()

    def scene_point(self, point):
        return (point.x(), point.y())

    def snap_point(self, point):
        candidates = []
        visible = self.visible_items()
        if self.snap_grid:
            size = self.grid_size
            candidates.append((round(point[0] / size) * size, round(point[1] / size) * size, "شبکه"))
        if self.snap_endpoint or self.snap_midpoint:
            for item in visible:
                pts = item.get("points", [])
                if self.snap_endpoint:
                    for p in pts:
                        candidates.append((p[0], p[1], "انتهای خط"))
                if self.snap_midpoint:
                    for a, b in item_segments(item):
                        candidates.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, "وسط خط"))
        if self.snap_intersection:
            segments = []
            for item in visible:
                segments.extend(item_segments(item))
            for index, first in enumerate(segments):
                for second in segments[index + 1:]:
                    intersection = segment_intersection(first[0], first[1], second[0], second[1])
                    if intersection is not None:
                        candidates.append((intersection[0], intersection[1], "تقاطع"))
        if not candidates:
            self.snap_marker = None
            return point
        scale = max(self.view.transform().m11(), 0.01)
        best = min(candidates, key=lambda c: distance(point, c[:2]))
        if distance(point, best[:2]) <= 12 / scale:
            self.snap_marker = (best[0], best[1], best[2])
            return best[:2]
        self.snap_marker = None
        return point

    def ortho_point(self, start, point):
        if not self.ortho or not start:
            return point
        dx, dy = point[0] - start[0], point[1] - start[1]
        return (point[0], start[1]) if abs(dx) >= abs(dy) else (start[0], point[1])

    def on_canvas_press(self, qpoint):
        point = self.snap_point(self.scene_point(qpoint))
        tool = self.current_tool
        if tool == "select":
            self.selected = self.hit_test(point)
            self.drag_last = point
            self.drag_snapshot = self.document.snapshot() if self.selected is not None else None
            self.update_properties()
            self.redraw()
            return
        if tool == "text":
            text, ok = QInputDialog.getText(self, "متن", "متن موردنظر را وارد کنید:")
            if ok and text:
                self.add_item(make_item([point], "text", self.current_layer, self.layers, {"text": text}))
            return
        if tool == "polyline":
            self.poly_points.append(point)
            self.preview = make_item(self.poly_points, "polyline", self.current_layer, self.layers) if len(self.poly_points) > 1 else None
            self.redraw()
            return
        if tool == "area":
            self.area_points.append(point)
            self.preview = make_item(self.area_points, "area", self.current_layer, self.layers) if len(self.area_points) > 1 else None
            self.redraw()
            return
        if tool == "measure":
            self.measure_points.append(point)
            if len(self.measure_points) == 2:
                self.show_measure(self.measure_points[0], self.measure_points[1])
                self.measure_points = []
            self.redraw()
            return
        self.start = point
        self.preview = None

    def on_canvas_move(self, qpoint):
        raw = self.scene_point(qpoint)
        point = self.snap_point(raw)
        if self.current_tool == "select" and self.selected is not None and self.drag_last:
            if self.layer_locked(self.items[self.selected].get("layer")):
                return
            dx, dy = point[0] - self.drag_last[0], point[1] - self.drag_last[1]
            move_item(self.items[self.selected], dx, dy)
            self.drag_last = point
            self.redraw()
        elif self.start:
            point = self.ortho_point(self.start, point)
            self.preview = self.make_current_item([self.start, point])
            self.redraw()
        elif self.poly_points and self.current_tool == "polyline":
            self.preview = make_item(self.poly_points + [point], "polyline", self.current_layer, self.layers)
            self.redraw()
        elif self.area_points and self.current_tool == "area":
            self.preview = make_item(self.area_points + [point], "area", self.current_layer, self.layers)
            self.redraw()
        snap = f" | Snap: {self.snap_marker[2]}" if self.snap_marker else ""
        zoom = self.view.transform().m11()
        self.set_status(f"X: {self.unit_manager.format_length(point[0])}   Y: {self.unit_manager.format_length(point[1])}   مقیاس: {zoom:.2f}x   آیتم‌ها: {len(self.items)}{snap}")

    def on_canvas_release(self, qpoint):
        if self.current_tool == "select":
            self.drag_last = None
            if self.drag_snapshot and self.document.snapshot() != self.drag_snapshot:
                self.document.undo_stack.append(self.drag_snapshot)
                self.document.redo_stack.clear()
                self.update_window_title()
            self.drag_snapshot = None
            return
        if not self.start:
            return
        point = self.ortho_point(self.start, self.snap_point(self.scene_point(qpoint)))
        item = self.make_current_item([self.start, point])
        if distance(self.start, point) > 0.5:
            self.add_item(item)
        self.start = None
        self.preview = None
        self.redraw()

    def on_canvas_double_click(self, qpoint):
        if self.current_tool == "polyline" and len(self.poly_points) > 1:
            self.add_item(make_item(self.poly_points, "polyline", self.current_layer, self.layers))
            self.poly_points = []
            self.preview = None
        elif self.current_tool == "area" and len(self.area_points) > 2:
            self.add_item(make_item(self.area_points, "area", self.current_layer, self.layers))
            QMessageBox.information(self, "مساحت", f"مساحت: {self.unit_manager.format_area(polygon_area(self.area_points))}")
            self.area_points = []
            self.preview = None
        self.redraw()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.cancel()
            return
        super().keyPressEvent(event)

    def make_current_item(self, points):
        metadata = {}
        if self.current_tool == "contour":
            value, ok = QInputDialog.getDouble(self, "خط تراز", "ارتفاع خط تراز:", 0.0)
            metadata["elevation"] = value if ok else 0.0
        return make_item(points, self.current_tool, self.current_layer, self.layers, metadata)

    def add_item(self, item):
        self.selected = self.document.add_item(item)
        self.refresh_layers()
        self.update_properties()
        self.redraw()
        self.update_window_title()

    def redraw(self):
        self.scene.clear()
        drawing_bounds = core_bounds(self.items) or (-500, -350, 500, 350)
        min_x, min_y, max_x, max_y = drawing_bounds
        self.scene.setSceneRect(QRectF(min_x - 300, min_y - 300, max_x - min_x + 600, max_y - min_y + 600))
        if self.grid_visible:
            self.draw_grid()
        for index, item in enumerate(self.items):
            if self.layer_visible(item.get("layer")):
                self.draw_item(item, selected=index == self.selected)
        if self.preview:
            self.draw_item(self.preview, selected=True, preview=True)
        if self.snap_marker:
            pen = QPen(QColor(self.theme["select"]), 0)
            x, y = self.snap_marker[0], self.snap_marker[1]
            self.scene.addEllipse(x - 4, y - 4, 8, 8, pen, QBrush(Qt.NoBrush))
        self.update_stats()

    def update_stats(self):
        if not hasattr(self, "stats_label"):
            return
        visible_count = sum(1 for item in self.items if self.layer_visible(item.get("layer")))
        hidden_count = len(self.items) - visible_count
        layer_count = len(self.layers)
        drawing_bounds = core_bounds(self.items)
        if drawing_bounds:
            min_x, min_y, max_x, max_y = drawing_bounds
            size_text = f"ابعاد محدوده: {self.unit_manager.format_length(max_x - min_x, 1)} × {self.unit_manager.format_length(max_y - min_y, 1)}"
        else:
            size_text = "ابعاد محدوده: -"
        locked_count = sum(1 for data in self.layers.values() if data.get("locked", False))
        self.stats_label.setText(
            f"کل آیتم‌ها: {len(self.items)} | نمایان: {visible_count} | پنهان: {hidden_count} | "
            f"لایه‌ها: {layer_count} | لایه قفل‌شده: {locked_count} | {size_text}"
        )

    def draw_grid(self):
        rect = self.scene.sceneRect()
        step = self.grid_size
        pen = QPen(QColor(self.theme["grid"]), 0)
        start_x = math.floor(rect.left() / step) * step
        x = start_x
        while x <= rect.right():
            self.scene.addLine(x, rect.top(), x, rect.bottom(), pen)
            x += step
        start_y = math.floor(rect.top() / step) * step
        y = start_y
        while y <= rect.bottom():
            self.scene.addLine(rect.left(), y, rect.right(), y, pen)
            y += step
        axis_pen = QPen(QColor(self.theme["axis"]), 0)
        self.scene.addLine(0, rect.top(), 0, rect.bottom(), axis_pen)
        self.scene.addLine(rect.left(), 0, rect.right(), 0, axis_pen)

    def draw_item(self, item, selected=False, preview=False):
        layer = item.get("layer", "راه")
        color = self.theme["select"] if selected else item.get("color") or self.layers.get(layer, {}).get("color", "#ffffff")
        width = float(item.get("width", self.layers.get(layer, {}).get("width", 2)))
        pen = QPen(QColor(color), width)
        pen.setCosmetic(True)
        if preview:
            pen.setStyle(Qt.DashLine)
        kind = item.get("type")
        pts = [QPointF(x, y) for x, y in item.get("points", [])]
        if not pts:
            return
        if kind in ("line", "polyline", "contour", "area"):
            self.draw_poly(pts, pen, closed=kind == "area")
            if kind == "contour":
                self.add_text_at(item.get("points", [])[len(pts) // 2], f"EL {item.get('elevation', 0):.2f}", color, -12)
            if kind == "area" and len(item.get("points", [])) > 2:
                raw = item.get("points", [])
                cx = sum(p[0] for p in raw) / len(raw)
                cy = sum(p[1] for p in raw) / len(raw)
                self.add_text_at((cx, cy), f"A={self.unit_manager.format_area(polygon_area(raw))}", color, 0)
        elif kind == "beam":
            self.draw_offset_pair(item.get("points", [])[:2], color, width, 5)
        elif kind == "wall":
            self.draw_offset_pair(item.get("points", [])[:2], color, width, 8)
            self.scene.addLine(pts[0].x(), pts[0].y(), pts[1].x(), pts[1].y(), QPen(QColor(color), 0, Qt.DotLine))
        elif kind == "drain":
            self.draw_poly(pts, pen)
            raw = item.get("points", [])
            if len(raw) >= 2:
                p1, p2 = raw[:2]
                self.add_text_at(((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2), f"S={item.get('slope', 1.0):.2f}%", color, -14)
        elif kind == "dimension":
            self.draw_dimension(item, color)
        elif kind == "column":
            self.draw_rect_item(pts, pen, cross=True)
        elif kind == "text":
            self.add_text_at(item.get("points", [])[0], item.get("text", "متن"), color, 0, bold=True)
        elif kind == "arc":
            self.draw_arc(item, pen)
        elif kind == "footing":
            self.draw_rect_item(pts, pen, cross=True, grid=True)
            raw = item.get("points", [])
            if len(raw) >= 2:
                self.add_text_at(((raw[0][0] + raw[1][0]) / 2, (raw[0][1] + raw[1][1]) / 2), item.get("text", "F"), color, 0)
        elif kind == "rebar":
            self.draw_poly(pts, QPen(QColor(color), max(width, 3)))
            raw = item.get("points", [])
            if len(raw) >= 2:
                self.add_text_at(((raw[0][0] + raw[1][0]) / 2, (raw[0][1] + raw[1][1]) / 2), item.get("text", "Ø16"), color, -12)
        if selected:
            handle_pen = QPen(QColor(self.theme["select"]), 0)
            for point in pts:
                self.scene.addRect(point.x() - 3, point.y() - 3, 6, 6, handle_pen, QBrush(QColor(self.theme["select"])))

    def draw_poly(self, pts, pen, closed=False):
        if len(pts) == 1:
            self.scene.addEllipse(pts[0].x() - 2, pts[0].y() - 2, 4, 4, pen, QBrush(pen.color()))
            return
        path = QPainterPath(pts[0])
        for point in pts[1:]:
            path.lineTo(point)
        if closed:
            path.closeSubpath()
        self.scene.addPath(path, pen)

    def draw_offset_pair(self, points, color, width, offset):
        if len(points) < 2:
            return
        p1, p2 = points[:2]
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        length = math.hypot(dx, dy) or 1
        ox, oy = -dy / length * offset, dx / length * offset
        pen = QPen(QColor(color), width)
        pen.setCosmetic(True)
        self.scene.addLine(p1[0] + ox, p1[1] + oy, p2[0] + ox, p2[1] + oy, pen)
        self.scene.addLine(p1[0] - ox, p1[1] - oy, p2[0] - ox, p2[1] - oy, pen)

    def draw_rect_item(self, pts, pen, cross=False, grid=False):
        if len(pts) < 2:
            return
        x1, y1, x2, y2 = pts[0].x(), pts[0].y(), pts[1].x(), pts[1].y()
        left, top = min(x1, x2), min(y1, y2)
        width, height = abs(x2 - x1), abs(y2 - y1)
        self.scene.addRect(left, top, width, height, pen)
        if cross:
            self.scene.addLine(x1, y1, x2, y2, pen)
            self.scene.addLine(x1, y2, x2, y1, pen)
        if grid:
            grid_pen = QPen(pen.color(), 0, Qt.DashLine)
            for factor in (0.25, 0.5, 0.75):
                x = x1 + (x2 - x1) * factor
                y = y1 + (y2 - y1) * factor
                self.scene.addLine(x, y1, x, y2, grid_pen)
                self.scene.addLine(x1, y, x2, y, grid_pen)

    def draw_dimension(self, item, color):
        pts = item.get("points", [])
        if len(pts) < 2:
            return
        p1, p2 = pts[:2]
        pen = QPen(QColor(color), 2)
        pen.setCosmetic(True)
        self.scene.addLine(p1[0], p1[1], p2[0], p2[1], pen)
        mid = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
        self.add_text_at(mid, self.unit_manager.format_length(distance(p1, p2)), color, -8)

    def draw_arc(self, item, pen):
        pts = item.get("points", [])
        if len(pts) < 2:
            return
        p1, p2 = pts[:2]
        rect = QRectF(min(p1[0], p2[0]), min(p1[1], p2[1]), abs(p2[0] - p1[0]), abs(p2[1] - p1[1]))
        if rect.width() < 4 or rect.height() < 4:
            return
        path = QPainterPath()
        path.arcMoveTo(rect, 20)
        path.arcTo(rect, 20, 140)
        self.scene.addPath(path, pen)

    def add_text_at(self, point, text, color, dy=0, bold=False):
        item = QGraphicsTextItem(str(text))
        font = QFont("Segoe UI", 11)
        font.setBold(bold)
        item.setFont(font)
        item.setDefaultTextColor(QColor(color))
        item.setPos(point[0], point[1] + dy)
        item.setTransform(QTransform.fromScale(1, -1), True)
        self.scene.addItem(item)

    def visible_items(self):
        return [item for item in self.items if self.layer_visible(item.get("layer"))]

    def layer_visible(self, layer):
        return self.layers.get(layer, {}).get("visible", True)

    def layer_locked(self, layer):
        return self.layers.get(layer, {}).get("locked", False)

    def hit_test(self, point):
        scale = max(self.view.transform().m11(), 0.01)
        best = None
        best_distance = 12 / scale
        for index in range(len(self.items) - 1, -1, -1):
            item = self.items[index]
            if not self.layer_visible(item.get("layer")):
                continue
            dist = item_distance(point, item)
            if dist < best_distance:
                best = index
                best_distance = dist
        return best

    def refresh_layers(self):
        if not hasattr(self, "layer_list"):
            return
        current = self.current_layer
        self.layer_list.blockSignals(True)
        self.layer_list.clear()
        for name, data in self.layers.items():
            flags = []
            if not data.get("visible", True):
                flags.append("پنهان")
            if data.get("locked", False):
                flags.append("قفل")
            item = QListWidgetItem(f"{name} {' / '.join(flags)}".strip())
            item.setData(Qt.UserRole, name)
            item.setForeground(QBrush(QColor(data.get("color", "#ffffff"))))
            self.layer_list.addItem(item)
        if current in self.layers:
            self.layer_list.setCurrentRow(list(self.layers).index(current))
        self.layer_list.blockSignals(False)
        if hasattr(self, "layer_combo"):
            self.layer_combo.blockSignals(True)
            self.layer_combo.clear()
            self.layer_combo.addItems(list(self.layers))
            self.layer_combo.blockSignals(False)

    def on_layer_selected(self, row):
        if row < 0:
            return
        item = self.layer_list.item(row)
        self.current_layer = item.data(Qt.UserRole)
        if hasattr(self, "layer_combo"):
            self.layer_combo.setCurrentText(self.current_layer)

    def add_layer(self):
        name, ok = QInputDialog.getText(self, "لایه جدید", "نام لایه:")
        if not ok or not name:
            return
        if name in self.layers:
            QMessageBox.warning(self, "لایه", "این نام قبلاً وجود دارد.")
            return
        color = QColorDialog.getColor(QColor("#ffffff"), self, "رنگ لایه")
        self.document.push_undo()
        self.document.redo_stack.clear()
        self.layers[name] = {"color": color.name() if color.isValid() else "#ffffff", "visible": True, "locked": False, "width": 2}
        self.current_layer = name
        self.refresh_layers()
        self.redraw()
        self.update_window_title()

    def rename_layer(self):
        old = self.current_layer
        if old not in self.layers:
            return
        new, ok = QInputDialog.getText(self, "تغییر نام لایه", "نام جدید:", text=old)
        if not ok or not new or new == old:
            return
        self.document.push_undo()
        self.document.redo_stack.clear()
        self.layers[new] = self.layers.pop(old)
        for item in self.items:
            if item.get("layer") == old:
                item["layer"] = new
        self.current_layer = new
        self.refresh_layers()
        self.redraw()
        self.update_window_title()

    def change_layer_color(self):
        layer = self.current_layer
        if layer not in self.layers:
            return
        color = QColorDialog.getColor(QColor(self.layers[layer]["color"]), self, "رنگ لایه")
        if color.isValid():
            self.document.push_undo()
            self.document.redo_stack.clear()
            self.layers[layer]["color"] = color.name()
            self.refresh_layers()
            self.redraw()
            self.update_window_title()

    def toggle_layer_visible(self):
        layer = self.current_layer
        if layer in self.layers:
            self.document.push_undo()
            self.document.redo_stack.clear()
            self.layers[layer]["visible"] = not self.layers[layer].get("visible", True)
            self.refresh_layers()
            self.redraw()
            self.update_window_title()

    def toggle_layer_lock(self):
        layer = self.current_layer
        if layer in self.layers:
            self.document.push_undo()
            self.document.redo_stack.clear()
            self.layers[layer]["locked"] = not self.layers[layer].get("locked", False)
            self.refresh_layers()
            self.redraw()
            self.update_window_title()

    def update_properties(self):
        if not hasattr(self, "type_label"):
            return
        if self.selected is None or self.selected >= len(self.items):
            self.type_label.setText("-")
            self.layer_combo.setCurrentIndex(-1)
            self.width_edit.clear()
            self.color_edit.clear()
            self.text_edit.clear()
            self.info_box.setPlainText("آیتمی انتخاب نشده است.")
            return
        item = self.items[self.selected]
        self.type_label.setText(TOOL_LABELS.get(item.get("type"), item.get("type", "-")))
        self.layer_combo.setCurrentText(item.get("layer", ""))
        self.width_edit.setText(str(item.get("width", "")))
        self.color_edit.setText(item.get("color", ""))
        self.text_edit.setText(item.get("text", ""))
        self.info_box.setPlainText(item_info(item, self.unit_manager))

    def apply_properties(self):
        if self.selected is None:
            return
        item = self.items[self.selected]
        self.document.push_undo()
        self.document.redo_stack.clear()
        layer = self.layer_combo.currentText()
        if layer in self.layers:
            item["layer"] = layer
        try:
            item["width"] = max(1, float(self.width_edit.text()))
        except ValueError:
            pass
        if self.color_edit.text().startswith("#"):
            item["color"] = self.color_edit.text()
        if self.text_edit.text():
            item["text"] = self.text_edit.text()
        self.update_properties()
        self.redraw()
        self.update_window_title()

    def choose_item_color(self):
        if self.selected is None:
            return
        color = QColorDialog.getColor(QColor(self.color_edit.text() or "#ffffff"), self, "رنگ آیتم")
        if color.isValid():
            self.color_edit.setText(color.name())
            self.apply_properties()

    def cancel(self):
        self.start = None
        self.preview = None
        self.poly_points = []
        self.area_points = []
        self.measure_points = []
        self.snap_marker = None
        self.redraw()

    def undo(self):
        if self.document.undo():
            self.selected = None
            self.refresh_layers()
            self.update_properties()
            self.redraw()
            self.update_window_title()

    def redo(self):
        if self.document.redo():
            self.selected = None
            self.refresh_layers()
            self.update_properties()
            self.redraw()
            self.update_window_title()

    def copy_selected(self):
        if self.selected is not None:
            self.clipboard = json.dumps(self.items[self.selected], ensure_ascii=False)

    def paste_item(self):
        if not self.clipboard:
            return
        item = normalize_item(json.loads(self.clipboard))
        item.pop("id", None)
        move_item(item, self.grid_size, self.grid_size)
        self.add_item(item)

    def delete_selected(self):
        if self.selected is None:
            return
        if self.layer_locked(self.items[self.selected].get("layer")):
            QMessageBox.warning(self, "لایه قفل است", "این آیتم روی لایه قفل‌شده قرار دارد.")
            return
        self.document.delete_item(self.selected)
        self.selected = None
        self.update_properties()
        self.redraw()
        self.update_window_title()

    def offset_selected(self):
        if self.selected is None:
            QMessageBox.information(self, "Offset", "ابتدا یک خط، دیوار، تیر یا پلی‌لاین را انتخاب کنید.")
            return
        item = self.items[self.selected]
        if len(item.get("points", [])) < 2:
            return
        dist, ok = QInputDialog.getDouble(self, "Offset", "فاصله Offset:", 5.0)
        if not ok:
            return
        side, ok = QInputDialog.getText(self, "Offset", "جهت را وارد کنید: L یا R", text="L")
        if not ok:
            return
        sign = 1 if side.upper().startswith("L") else -1
        new_item = json.loads(json.dumps(item, ensure_ascii=False))
        new_item.pop("id", None)
        new_item["points"] = offset_points([tuple(p) for p in item["points"]], self.unit_manager.to_base_length(dist) * sign)
        self.add_item(normalize_item(new_item))

    def trim_selected(self):
        if self.selected is None:
            return
        item = self.items[self.selected]
        if len(item.get("points", [])) < 2:
            return
        percent, ok = QInputDialog.getDouble(self, "Trim", "چند درصد از انتهای آیتم کم شود؟", 10.0, 1.0, 90.0)
        if ok:
            self.document.push_undo()
            self.document.redo_stack.clear()
            trim_item_end(item, percent)
            self.redraw()
            self.update_window_title()

    def extend_selected(self):
        if self.selected is None:
            return
        item = self.items[self.selected]
        if len(item.get("points", [])) < 2:
            return
        length, ok = QInputDialog.getDouble(self, "Extend", "مقدار افزایش طول:", 5.0)
        if ok:
            self.document.push_undo()
            self.document.redo_stack.clear()
            extend_item_end(item, self.unit_manager.to_base_length(length))
            self.redraw()
            self.update_window_title()

    def show_measure(self, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        angle = math.degrees(math.atan2(dy, dx))
        QMessageBox.information(self, "اندازه‌گیری", f"طول: {self.unit_manager.format_length(length, 3)}\nزاویه: {angle:.2f}°")

    def quantity_report(self):
        self.show_text_window("گزارش متره", quantity_report(self.items, self.unit_manager))

    def show_text_window(self, title, text):
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setText(text)
        dialog.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        dialog.exec()

    def zoom_view(self, factor):
        self.scale_factor *= factor
        self.view.scale(factor, factor)

    def zoom_reset(self):
        self.view.resetTransform()
        self.scale_factor = 1.0

    def zoom_to_fit(self):
        drawing_bounds = core_bounds(self.items)
        if not drawing_bounds:
            return
        min_x, min_y, max_x, max_y = drawing_bounds
        rect = QRectF(min_x - 50, min_y - 50, max_x - min_x + 100, max_y - min_y + 100)
        self.view.fitInView(rect, Qt.KeepAspectRatio)

    def template_road_section(self):
        y = 100 + len(self.items) * 2
        self.document.add_items(template_road_section(self.document.id_counter, y))
        self.redraw()
        self.update_window_title()

    def template_footing(self):
        self.document.add_items(template_footing(self.document.id_counter))
        self.redraw()
        self.update_window_title()

    def template_drainage(self):
        self.document.add_items(template_drainage(self.document.id_counter))
        self.redraw()
        self.update_window_title()

    def new_file(self):
        if not self.maybe_save_changes():
            return
        self.document.reset()
        self.selected = None
        self.file_path = None
        self.last_saved_snapshot = self.save_snapshot()
        self.refresh_layers()
        self.update_properties()
        self.redraw()
        self.update_window_title()

    def save_file(self):
        if not self.file_path:
            return self.save_as()
        return self.write_project(self.file_path)

    def save_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "ذخیره", "", "CivilCAD (*.ccad);;JSON (*.json)")
        if path:
            self.file_path = path
            return self.write_project(path)
        return False

    def write_project(self, path):
        data = self.document.to_data(self.theme_name, self.unit)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        self.last_saved_snapshot = self.save_snapshot()
        self.set_status(f"ذخیره شد: {os.path.basename(path)}")
        self.update_window_title()
        return True

    def open_file(self):
        if not self.maybe_save_changes():
            return
        path, _ = QFileDialog.getOpenFileName(self, "باز کردن", "", "CivilCAD (*.ccad);;JSON (*.json);;All Files (*)")
        if not path:
            return
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        self.document.load_data(data)
        theme_name = data.get("theme", self.theme_name)
        unit = data.get("unit", "m")
        self.file_path = path
        self.selected = None
        self.theme_manager.set_theme(theme_name)
        self.unit_manager.set_unit(unit)
        self.last_saved_snapshot = self.save_snapshot()
        self.refresh_layers()
        self.update_properties()
        self.redraw()
        self.update_window_title()

    def export_svg(self):
        path, _ = QFileDialog.getSaveFileName(self, "خروجی SVG", "", "SVG (*.svg)")
        if not path:
            return
        svg = export_svg_text(self.items, self.layers)
        if svg is None:
            QMessageBox.information(self, "SVG", "چیزی برای خروجی وجود ندارد.")
            return
        with open(path, "w", encoding="utf-8") as file:
            file.write(svg)
        self.set_status(f"SVG ساخته شد: {os.path.basename(path)}")

    def export_dxf(self):
        path, _ = QFileDialog.getSaveFileName(self, "خروجی DXF", "", "DXF (*.dxf)")
        if path:
            with open(path, "w", encoding="utf-8") as file:
                file.write(export_dxf_text(self.items))
            self.set_status(f"DXF ساخته شد: {os.path.basename(path)}")

    def save_snapshot(self):
        return json.dumps({"document": json.loads(self.document.snapshot()), "theme": self.theme_name, "unit": self.unit}, ensure_ascii=False, sort_keys=True)

    def is_dirty(self):
        return self.save_snapshot() != self.last_saved_snapshot

    def update_window_title(self):
        marker = " *" if self.is_dirty() else ""
        name = f" - {os.path.basename(self.file_path)}" if self.file_path else ""
        self.setWindowTitle(f"{APP_TITLE} | Developer: Savan Mohebi{name}{marker}")

    def maybe_save_changes(self):
        if not self.is_dirty():
            return True
        choice = QMessageBox.question(
            self,
            "ذخیره تغییرات",
            "تغییرات ذخیره نشده‌اند. قبل از ادامه ذخیره شوند؟",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if choice == QMessageBox.Cancel:
            return False
        if choice == QMessageBox.Save:
            return bool(self.save_file())
        return True

    def closeEvent(self, event):
        if self.maybe_save_changes():
            event.accept()
        else:
            event.ignore()


def create_splash():
    pixmap = QPixmap(520, 260)
    pixmap.fill(QColor("#0f172a"))
    splash = QSplashScreen(pixmap)
    splash.setLayoutDirection(Qt.LeftToRight)
    splash.showMessage(
        "CivilCAD Pro MVP\nDeveloper: Savan Mohebi",
        Qt.AlignCenter | Qt.AlignVCenter,
        QColor("#f8fafc"),
    )
    return splash


def main():
    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    app.setFont(QFont("Segoe UI", 10))
    splash = create_splash()
    splash.show()
    state = {"window": None, "splash": splash}

    def launch_main_window():
        window = CivilCAD()
        state["window"] = window
        window.show()
        state["splash"].finish(window)

    QTimer.singleShot(2300, launch_main_window)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
