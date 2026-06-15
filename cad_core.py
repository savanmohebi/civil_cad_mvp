import copy
import html
import json
import math


APP_TITLE = "سیویل‌کد پیشرفته | CivilCAD Pro MVP"
DEFAULT_FONT = ("Segoe UI", 10)
TITLE_FONT = ("Segoe UI", 13, "bold")
SMALL_FONT = ("Segoe UI", 9)

THEMES = {
    "شب مهندسی": {
        "bg": "#0f172a", "panel": "#1e293b", "panel2": "#263449", "text": "#f8fafc",
        "muted": "#cbd5e1", "grid": "#2f3b4a", "axis": "#64748b", "select": "#ffd166",
        "button": "#334155", "button_text": "#f8fafc", "entry": "#111827",
        "accent": "#38bdf8",
    },
    "روشن کلاسیک": {
        "bg": "#f8fafc", "panel": "#e2e8f0", "panel2": "#cbd5e1", "text": "#0f172a",
        "muted": "#334155", "grid": "#cbd5e1", "axis": "#64748b", "select": "#f59e0b",
        "button": "#ffffff", "button_text": "#0f172a", "entry": "#ffffff",
        "accent": "#2563eb",
    },
    "آبی نقشه": {
        "bg": "#061826", "panel": "#0b2a42", "panel2": "#123a58", "text": "#e0f2fe",
        "muted": "#bae6fd", "grid": "#164e63", "axis": "#38bdf8", "select": "#facc15",
        "button": "#075985", "button_text": "#e0f2fe", "entry": "#082f49",
        "accent": "#7dd3fc",
    },
    "سبز سایت": {
        "bg": "#102018", "panel": "#183528", "panel2": "#214936", "text": "#ecfdf5",
        "muted": "#bbf7d0", "grid": "#28513e", "axis": "#22c55e", "select": "#fde047",
        "button": "#166534", "button_text": "#ecfdf5", "entry": "#052e16",
        "accent": "#86efac",
    },
    "خاک و بتن": {
        "bg": "#211a16", "panel": "#37251d", "panel2": "#493126", "text": "#fff7ed",
        "muted": "#fed7aa", "grid": "#5a3d30", "axis": "#fb923c", "select": "#fde68a",
        "button": "#7c2d12", "button_text": "#fff7ed", "entry": "#1c1917",
        "accent": "#fdba74",
    },
}

DEFAULT_LAYERS = {
    "راه": {"color": "#f7c948", "visible": True, "locked": False, "width": 2},
    "تیر": {"color": "#5dade2", "visible": True, "locked": False, "width": 2},
    "ستون": {"color": "#f76f72", "visible": True, "locked": False, "width": 2},
    "دیوار": {"color": "#b8e986", "visible": True, "locked": False, "width": 2},
    "زهکش": {"color": "#73d2de", "visible": True, "locked": False, "width": 2},
    "اندازه‌گذاری": {"color": "#ffffff", "visible": True, "locked": False, "width": 1},
    "متن": {"color": "#f4a261", "visible": True, "locked": False, "width": 1},
    "آرماتور": {"color": "#ff6b6b", "visible": True, "locked": False, "width": 2},
    "فونداسیون": {"color": "#c084fc", "visible": True, "locked": False, "width": 2},
    "مرزبندی": {"color": "#fb7185", "visible": True, "locked": False, "width": 2},
    "توپوگرافی": {"color": "#86efac", "visible": True, "locked": False, "width": 1},
    "خاکبرداری": {"color": "#d97706", "visible": True, "locked": False, "width": 2},
    "آب": {"color": "#38bdf8", "visible": True, "locked": False, "width": 2},
    "برق": {"color": "#facc15", "visible": True, "locked": False, "width": 2},
}

TOOL_LABELS = {
    "select": "انتخاب / جابه‌جایی",
    "line": "خط / محور راه",
    "polyline": "پلی‌لاین",
    "arc": "قوس / منحنی",
    "beam": "تیر",
    "column": "ستون",
    "wall": "دیوار",
    "drain": "لوله زهکش",
    "dimension": "اندازه‌گذاری",
    "text": "متن",
    "contour": "خط تراز",
    "footing": "فونداسیون",
    "rebar": "آرماتور",
    "measure": "اندازه‌گیری",
    "area": "مساحت",
}

LAYER_BY_TOOL = {
    "line": "راه", "polyline": "راه", "arc": "راه", "beam": "تیر", "column": "ستون",
    "wall": "دیوار", "drain": "زهکش", "dimension": "اندازه‌گذاری", "text": "متن",
    "contour": "توپوگرافی", "footing": "فونداسیون", "rebar": "آرماتور",
    "measure": "اندازه‌گذاری", "area": "اندازه‌گذاری",
}

LINE_TYPES = {"solid": None, "dash": (8, 5), "dot": (2, 5), "center": (12, 4, 2, 4)}


def clone_layers():
    return copy.deepcopy(DEFAULT_LAYERS)


def normalize_item(item, next_id=None):
    normalized = dict(item)
    normalized["points"] = [tuple(point) for point in normalized.get("points", [])]
    if "id" not in normalized and next_id is not None:
        normalized["id"] = next_id
    return normalized


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def polygon_area(points):
    area = 0
    normalized = [tuple(point) for point in points]
    for a, b in zip(normalized, normalized[1:] + normalized[:1]):
        area += a[0] * b[1] - b[0] * a[1]
    return abs(area) / 2


def point_in_polygon(point, polygon):
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i, pi in enumerate(polygon):
        xi, yi = pi
        xj, yj = polygon[j]
        crosses = (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
        if crosses:
            inside = not inside
        j = i
    return inside


def line_distance(point, a, b):
    px, py = point
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return distance(point, a)
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return distance(point, (ax + t * dx, ay + t * dy))


def segment_intersection(a, b, c, d, tolerance=1e-9):
    ax, ay = a
    bx, by = b
    cx, cy = c
    dx, dy = d
    denominator = (ax - bx) * (cy - dy) - (ay - by) * (cx - dx)
    if abs(denominator) <= tolerance:
        return None
    det_ab = ax * by - ay * bx
    det_cd = cx * dy - cy * dx
    x = (det_ab * (cx - dx) - (ax - bx) * det_cd) / denominator
    y = (det_ab * (cy - dy) - (ay - by) * det_cd) / denominator
    if (min(ax, bx) - tolerance <= x <= max(ax, bx) + tolerance and
            min(ay, by) - tolerance <= y <= max(ay, by) + tolerance and
            min(cx, dx) - tolerance <= x <= max(cx, dx) + tolerance and
            min(cy, dy) - tolerance <= y <= max(cy, dy) + tolerance):
        return (x, y)
    return None


def item_segments(item):
    pts = item.get("points", [])
    if item.get("type") in ("column", "footing") and len(pts) >= 2:
        a, b = pts[:2]
        left, right = sorted((a[0], b[0]))
        top, bottom = sorted((a[1], b[1]))
        corners = [(left, top), (right, top), (right, bottom), (left, bottom), (left, top)]
        return list(zip(corners, corners[1:]))
    if item.get("type") == "area" and len(pts) > 2:
        closed = list(pts) + [pts[0]]
        return list(zip(closed, closed[1:]))
    return list(zip(pts, pts[1:]))


def rect_distance(point, a, b):
    px, py = point
    min_x, max_x = sorted((a[0], b[0]))
    min_y, max_y = sorted((a[1], b[1]))
    if min_x <= px <= max_x and min_y <= py <= max_y:
        return 0
    cx = min(max(px, min_x), max_x)
    cy = min(max(py, min_y), max_y)
    return distance(point, (cx, cy))


def item_distance(point, item):
    kind = item.get("type")
    pts = item.get("points", [])
    if not pts:
        return 1e9
    if kind == "text":
        return distance(point, pts[0])
    if kind in ("column", "footing") and len(pts) >= 2:
        return rect_distance(point, pts[0], pts[1])
    if kind == "area" and len(pts) > 2 and point_in_polygon(point, pts):
        return 0
    if len(pts) == 1:
        return distance(point, pts[0])
    return min(line_distance(point, a, b) for a, b in zip(pts, pts[1:]))


def move_item(item, dx, dy):
    item["points"] = [(point[0] + dx, point[1] + dy) for point in item.get("points", [])]
    return item


def offset_points(points, offset):
    points = [tuple(point) for point in points]
    if len(points) < 2:
        return points
    result = []
    for index, point in enumerate(points):
        if index == 0:
            a, b = points[0], points[1]
        elif index == len(points) - 1:
            a, b = points[-2], points[-1]
        else:
            a, b = points[index - 1], points[index + 1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy) or 1
        result.append((point[0] - dy / length * offset, point[1] + dx / length * offset))
    return result


def trim_item_end(item, percent):
    pts = item.get("points", [])
    if len(pts) < 2:
        return item
    a, b = pts[-2], pts[-1]
    factor = 1 - percent / 100
    pts[-1] = (a[0] + (b[0] - a[0]) * factor, a[1] + (b[1] - a[1]) * factor)
    return item


def extend_item_end(item, length):
    pts = item.get("points", [])
    if len(pts) < 2:
        return item
    a, b = pts[-2], pts[-1]
    dx, dy = b[0] - a[0], b[1] - a[1]
    base = math.hypot(dx, dy) or 1
    pts[-1] = (b[0] + dx / base * length, b[1] + dy / base * length)
    return item


def bounds(items):
    pts = [point for item in items for point in item.get("points", [])]
    if not pts:
        return None
    xs = [point[0] for point in pts]
    ys = [point[1] for point in pts]
    return min(xs), min(ys), max(xs), max(ys)


def find_next_id(items):
    return max([item.get("id", 0) for item in items] + [0]) + 1


def _format_length(value_m, unit_formatter, precision=2):
    if hasattr(unit_formatter, "format_length"):
        return unit_formatter.format_length(value_m, precision)
    return f"{value_m:.{precision}f} {unit_formatter}"


def _format_area(value_m2, unit_formatter, precision=2):
    if hasattr(unit_formatter, "format_area"):
        return unit_formatter.format_area(value_m2, precision)
    return f"{value_m2:.{precision}f} {unit_formatter}²"


def quantity_report(items, unit):
    lengths = {}
    areas = {}
    counts = {}
    type_counts = {}
    for item in items:
        layer = item.get("layer", "بدون لایه")
        counts[layer] = counts.get(layer, 0) + 1
        item_type = item.get("type", "unknown")
        type_counts[item_type] = type_counts.get(item_type, 0) + 1
        pts = item.get("points", [])
        if item.get("type") == "area" and len(pts) > 2:
            areas[layer] = areas.get(layer, 0) + polygon_area(pts)
        elif len(pts) > 1:
            lengths[layer] = lengths.get(layer, 0) + sum(distance(a, b) for a, b in zip(pts, pts[1:]))
    total_length = sum(lengths.values())
    total_area = sum(areas.values())
    lines = ["گزارش متره ساده", "-" * 28, f"تعداد کل آیتم‌ها: {sum(counts.values())}"]
    if total_length:
        lines.append(f"طول کل نقشه: {_format_length(total_length, unit)}")
    if total_area:
        lines.append(f"مساحت کل: {_format_area(total_area, unit)}")
    if type_counts:
        lines.append("-" * 28)
        lines.append("تفکیک نوع آیتم:")
        for item_type in sorted(type_counts):
            lines.append(f"  {TOOL_LABELS.get(item_type, item_type)}: {type_counts[item_type]}")
    lines.append("-" * 28)
    lines.append("تفکیک لایه‌ها:")
    for layer in sorted(counts):
        lines.append(f"{layer}: تعداد {counts[layer]}")
        if layer in lengths:
            lines.append(f"  طول کل: {_format_length(lengths[layer], unit)}")
        if layer in areas:
            lines.append(f"  مساحت کل: {_format_area(areas[layer], unit)}")
    return "\n".join(lines)


def item_info(item, unit):
    pts = item.get("points", [])
    lines = [f"ID: {item.get('id', '-')}", f"لایه: {item.get('layer', '-')}", f"تعداد نقاط: {len(pts)}"]
    if len(pts) > 1:
        length = sum(distance(a, b) for a, b in zip(pts, pts[1:]))
        lines.append(f"طول: {_format_length(length, unit, 3)}")
    if item.get("type") == "area" and len(pts) > 2:
        lines.append(f"مساحت: {_format_area(polygon_area(pts), unit, 3)}")
    if item.get("type") in ("column", "footing") and len(pts) >= 2:
        width = abs(pts[1][0] - pts[0][0])
        height = abs(pts[1][1] - pts[0][1])
        if hasattr(unit, "format_length"):
            lines.append(f"ابعاد: {unit.format_length(width)} × {unit.format_length(height)}")
        else:
            lines.append(f"ابعاد: {width:.2f} × {height:.2f} {unit}")
    return "\n".join(lines)


def make_item(points, kind, current_layer, layers, metadata=None):
    layer = LAYER_BY_TOOL.get(kind, current_layer)
    item = {
        "type": kind,
        "layer": layer,
        "points": [tuple(point) for point in points],
        "width": layers.get(layer, {}).get("width", 2),
    }
    if kind == "drain":
        item["slope"] = 1.0
    if kind == "footing":
        item["text"] = "F1"
    if kind == "rebar":
        item["text"] = "Ø16 @ 20cm"
    if metadata:
        item.update(metadata)
    return item


def template_road_section(start_id, y):
    items = [
        {"type": "line", "layer": "راه", "points": [(-120, y), (120, y)], "width": 3, "text": "محور"},
        {"type": "line", "layer": "مرزبندی", "points": [(-120, y - 35), (120, y - 35)], "width": 2},
        {"type": "line", "layer": "مرزبندی", "points": [(-120, y + 35), (120, y + 35)], "width": 2},
        {"type": "dimension", "layer": "اندازه‌گذاری", "points": [(-120, y + 55), (120, y + 55)], "width": 1},
        {"type": "text", "layer": "متن", "points": [(-40, y - 65)], "text": "مقطع راه نمونه", "width": 1},
    ]
    return _with_ids(items, start_id)


def template_footing(start_id):
    items = [
        {"type": "footing", "layer": "فونداسیون", "points": [(-60, -40), (60, 40)], "text": "F1", "width": 2},
        {"type": "column", "layer": "ستون", "points": [(-15, -15), (15, 15)], "width": 2},
        {"type": "rebar", "layer": "آرماتور", "points": [(-50, -25), (50, -25)], "text": "Ø16 @ 20", "width": 2},
        {"type": "rebar", "layer": "آرماتور", "points": [(-50, 25), (50, 25)], "text": "Ø16 @ 20", "width": 2},
    ]
    return _with_ids(items, start_id)


def template_drainage(start_id):
    pts = [(-120, -80), (-40, -40), (40, -10), (130, 50)]
    items = [{"type": "polyline", "layer": "زهکش", "points": pts, "width": 3, "slope": 1.5}]
    for index, point in enumerate(pts):
        items.append({
            "type": "text",
            "layer": "متن",
            "points": [(point[0] + 5, point[1] - 20)],
            "text": f"MH-{index + 1}",
            "width": 1,
        })
    return _with_ids(items, start_id)


def _with_ids(items, start_id):
    for offset, item in enumerate(items):
        item["id"] = start_id + offset
    return [normalize_item(item) for item in items]


class CadDocument:
    def __init__(self):
        self.items = []
        self.layers = clone_layers()
        self.id_counter = 1
        self.undo_stack = []
        self.redo_stack = []

    def snapshot(self):
        return json.dumps({"items": self.items, "layers": self.layers, "id_counter": self.id_counter}, ensure_ascii=False)

    def restore_snapshot(self, data):
        state = json.loads(data)
        self.items = [normalize_item(item) for item in state.get("items", [])]
        self.layers = state.get("layers", clone_layers())
        self.id_counter = state.get("id_counter", find_next_id(self.items))

    def push_undo(self):
        self.undo_stack.append(self.snapshot())
        if len(self.undo_stack) > 80:
            self.undo_stack.pop(0)

    def undo(self):
        if not self.undo_stack:
            return False
        self.redo_stack.append(self.snapshot())
        self.restore_snapshot(self.undo_stack.pop())
        return True

    def redo(self):
        if not self.redo_stack:
            return False
        self.undo_stack.append(self.snapshot())
        self.restore_snapshot(self.redo_stack.pop())
        return True

    def next_id(self):
        value = self.id_counter
        self.id_counter += 1
        return value

    def add_item(self, item, record_undo=True):
        if record_undo:
            self.push_undo()
        normalized = normalize_item(item, self.next_id())
        self.items.append(normalized)
        self.redo_stack.clear()
        return len(self.items) - 1

    def add_items(self, items):
        self.push_undo()
        self.items.extend(normalize_item(item) for item in items)
        self.id_counter = find_next_id(self.items)
        self.redo_stack.clear()

    def delete_item(self, index):
        if index is None or index >= len(self.items):
            return False
        self.push_undo()
        del self.items[index]
        self.redo_stack.clear()
        return True

    def reset(self):
        self.items = []
        self.layers = clone_layers()
        self.id_counter = 1
        self.undo_stack = []
        self.redo_stack = []

    def load_data(self, data):
        self.items = [normalize_item(item) for item in data.get("items", [])]
        self.layers = data.get("layers", clone_layers())
        self.id_counter = data.get("id_counter", find_next_id(self.items))
        self.undo_stack = []
        self.redo_stack = []

    def to_data(self, theme, unit):
        return {
            "version": 3,
            "items": self.items,
            "layers": self.layers,
            "theme": theme,
            "unit": unit,
            "id_counter": self.id_counter,
        }


def export_svg_text(items, layers):
    drawing_bounds = bounds(items)
    if not drawing_bounds:
        return None
    min_x, min_y, max_x, max_y = drawing_bounds
    width = max(max_x - min_x + 100, 1)
    height = max(max_y - min_y + 100, 1)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{min_x-50} {min_y-50} {width} {height}">',
        '<metadata>Generated by CivilCAD Pro MVP</metadata>',
        '<g fill="none" stroke-linecap="round" stroke-linejoin="round">',
    ]
    for item in items:
        layer = item.get("layer")
        if not layers.get(layer, {}).get("visible", True):
            continue
        color = item.get("color") or layers.get(layer, {}).get("color", "#ffffff")
        width_value = item.get("width", 2)
        pts = item.get("points", [])
        kind = item.get("type")
        layer_attr = html.escape(str(layer or "0"))
        if kind == "text" and pts:
            text = html.escape(str(item.get("text", "متن")))
            parts.append(f'</g><text data-layer="{layer_attr}" x="{pts[0][0]}" y="{pts[0][1]}" fill="{color}" font-size="14" font-family="Segoe UI, Tahoma, sans-serif">{text}</text><g fill="none" stroke-linecap="round" stroke-linejoin="round">')
        elif kind in ("column", "footing") and len(pts) >= 2:
            a, b = pts[:2]
            parts.append(f'<rect data-layer="{layer_attr}" x="{min(a[0], b[0])}" y="{min(a[1], b[1])}" width="{abs(a[0]-b[0])}" height="{abs(a[1]-b[1])}" stroke="{color}" stroke-width="{width_value}" />')
        elif kind == "area" and len(pts) > 2:
            pairs = " ".join(f"{x},{y}" for x, y in pts)
            parts.append(f'<polygon data-layer="{layer_attr}" points="{pairs}" fill="{color}" fill-opacity="0.08" stroke="{color}" stroke-width="{width_value}" />')
        elif kind == "arc" and len(pts) >= 2:
            a, b = pts[:2]
            rx = abs(a[0] - b[0]) / 2
            ry = abs(a[1] - b[1]) / 2
            parts.append(f'<path data-layer="{layer_attr}" d="M {a[0]} {a[1]} A {rx} {ry} 0 0 1 {b[0]} {b[1]}" stroke="{color}" stroke-width="{width_value}" />')
        elif len(pts) > 1:
            pairs = " ".join(f"{x},{y}" for x, y in pts)
            parts.append(f'<polyline data-layer="{layer_attr}" points="{pairs}" stroke="{color}" stroke-width="{width_value}" />')
    parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)


def export_dxf_text(items):
    lines = ["0", "SECTION", "2", "ENTITIES"]
    for item in items:
        pts = item.get("points", [])
        layer = item.get("layer", "0")
        kind = item.get("type")
        if kind == "text" and pts:
            lines += ["0", "TEXT", "8", layer, "10", str(pts[0][0]), "20", str(pts[0][1]), "40", "2.5", "1", str(item.get("text", "TEXT"))]
        elif kind == "area" and len(pts) > 2:
            closed = list(pts) + [pts[0]]
            for a, b in zip(closed, closed[1:]):
                lines += ["0", "LINE", "8", layer, "10", str(a[0]), "20", str(a[1]), "11", str(b[0]), "21", str(b[1])]
        elif kind in ("column", "footing") and len(pts) >= 2:
            for a, b in item_segments(item):
                lines += ["0", "LINE", "8", layer, "10", str(a[0]), "20", str(a[1]), "11", str(b[0]), "21", str(b[1])]
        elif len(pts) > 1:
            for a, b in zip(pts, pts[1:]):
                lines += ["0", "LINE", "8", layer, "10", str(a[0]), "20", str(a[1]), "11", str(b[0]), "21", str(b[1])]
    lines += ["0", "ENDSEC", "0", "EOF"]
    return "\n".join(lines)
