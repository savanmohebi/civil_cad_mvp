from cad_core import LINE_TYPES, SMALL_FONT


class CanvasRendererMixin:
    def redraw(self):
        if not hasattr(self, "canvas"):
            return
        self.canvas.delete("all")
        if self.grid_visible.get():
            self.draw_grid()
        for index, item in enumerate(self.items):
            if self.layer_visible(item.get("layer")):
                self.draw_item(item, selected=index == self.selected)
        if self.preview:
            self.draw_item(self.preview, selected=True, preview=True)
        if self.snap_marker:
            x, y = self.screen(self.snap_marker[0], self.snap_marker[1])
            self.canvas.create_oval(x - 5, y - 5, x + 5, y + 5, outline=self.theme["select"], width=2)

    def draw_grid(self):
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        step = self.grid_size.get() * self.scale
        if step >= 6:
            x = self.pan_x % step
            while x < width:
                self.canvas.create_line(x, 0, x, height, fill=self.theme["grid"])
                x += step
            y = self.pan_y % step
            while y < height:
                self.canvas.create_line(0, y, width, y, fill=self.theme["grid"])
                y += step
        ox, oy = self.screen(0, 0)
        self.canvas.create_line(ox, 0, ox, height, fill=self.theme["axis"], width=2)
        self.canvas.create_line(0, oy, width, oy, fill=self.theme["axis"], width=2)

    def draw_item(self, item, selected=False, preview=False):
        layer = item.get("layer", "راه")
        color = item.get("color") or self.layers.get(layer, {}).get("color", "#ffffff")
        if selected:
            color = self.theme["select"]
        width = int(float(item.get("width", self.layers.get(layer, {}).get("width", 2))))
        dash = (5, 4) if preview else LINE_TYPES.get(item.get("line_type", "solid"))
        kind = item.get("type")
        points = [self.screen(*p) for p in item.get("points", [])]
        if not points:
            return
        if kind in ("line", "polyline", "contour", "area"):
            self.draw_poly(points, color, width, dash, closed=kind == "area")
            if kind == "contour":
                self.draw_contour_label(item, color)
            if kind == "area" and len(item["points"]) > 2:
                self.draw_area_label(item, color)
        elif kind == "beam":
            self.draw_offset_pair(points[0], points[1], color, width, 5, dash)
        elif kind == "wall":
            self.draw_offset_pair(points[0], points[1], color, width, 8, dash)
            self.canvas.create_line(*points[0], *points[1], fill=color, dash=(2, 4))
        elif kind == "drain":
            self.canvas.create_line(*points[0], *points[1], fill=color, width=width, dash=(8, 5), arrow="last")
            self.draw_drain_label(item, color)
        elif kind == "dimension":
            self.draw_dimension(item, color)
        elif kind == "column":
            self.draw_column(points, color, width, dash)
        elif kind == "text":
            self.canvas.create_text(*points[0], text=item.get("text", "متن"), fill=color, anchor="nw", font=("Segoe UI", 12, "bold"))
        elif kind == "arc":
            self.draw_arc(item, color, width, dash)
        elif kind == "footing":
            self.draw_footing(item, color, width, dash)
        elif kind == "rebar":
            self.draw_rebar(item, color, width, dash)
        if selected:
            for p in points:
                self.canvas.create_rectangle(p[0] - 4, p[1] - 4, p[0] + 4, p[1] + 4, fill=color, outline="")

    def draw_poly(self, points, color, width, dash, closed=False):
        if len(points) == 1:
            x, y = points[0]
            self.canvas.create_oval(x - 2, y - 2, x + 2, y + 2, fill=color, outline=color)
            return
        flat = [coord for p in points for coord in p]
        if closed:
            self.canvas.create_polygon(*flat, outline=color, fill="", width=width, dash=dash)
        else:
            self.canvas.create_line(*flat, fill=color, width=width, dash=dash)

    def draw_offset_pair(self, p1, p2, color, width, offset, dash):
        x1, y1 = p1
        x2, y2 = p2
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy) or 1
        ox, oy = -dy / length * offset, dx / length * offset
        self.canvas.create_line(x1 + ox, y1 + oy, x2 + ox, y2 + oy, fill=color, width=width, dash=dash)
        self.canvas.create_line(x1 - ox, y1 - oy, x2 - ox, y2 - oy, fill=color, width=width, dash=dash)

    def draw_column(self, points, color, width, dash):
        (x1, y1), (x2, y2) = points[:2]
        self.canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=width, dash=dash)
        self.canvas.create_line(x1, y1, x2, y2, fill=color)
        self.canvas.create_line(x1, y2, x2, y1, fill=color)

    def draw_dimension(self, item, color):
        p1, p2 = item["points"][:2]
        x1, y1 = self.screen(*p1)
        x2, y2 = self.screen(*p2)
        self.canvas.create_line(x1, y1, x2, y2, fill=color, width=2, arrow="both")
        mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
        length = self.distance(p1, p2)
        text = f"{length:.2f} {self.unit.get()}"
        self.canvas.create_rectangle(mid_x - 42, mid_y - 12, mid_x + 42, mid_y + 12, fill=self.theme["bg"], outline="")
        self.canvas.create_text(mid_x, mid_y, text=text, fill=color, font=SMALL_FONT)

    def draw_arc(self, item, color, width, dash):
        p1, p2 = item["points"][:2]
        x1, y1 = self.screen(*p1)
        x2, y2 = self.screen(*p2)
        left, top, right, bottom = min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
        if abs(right - left) < 4 or abs(bottom - top) < 4:
            return
        self.canvas.create_arc(left, top, right, bottom, start=20, extent=140, style="arc", outline=color, width=width, dash=dash)

    def draw_footing(self, item, color, width, dash):
        points = [self.screen(*p) for p in item["points"][:2]]
        self.draw_column(points, color, width, dash)
        (x1, y1), (x2, y2) = points
        for t in [0.25, 0.5, 0.75]:
            x = x1 + (x2 - x1) * t
            y = y1 + (y2 - y1) * t
            self.canvas.create_line(x, y1, x, y2, fill=color, dash=(3, 5))
            self.canvas.create_line(x1, y, x2, y, fill=color, dash=(3, 5))
        self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=item.get("text", "F"), fill=color, font=SMALL_FONT)

    def draw_rebar(self, item, color, width, dash):
        points = [self.screen(*p) for p in item["points"][:2]]
        self.canvas.create_line(*points[0], *points[1], fill=color, width=max(width, 3), dash=dash)
        self.canvas.create_oval(points[0][0] - 4, points[0][1] - 4, points[0][0] + 4, points[0][1] + 4, outline=color, width=2)
        self.canvas.create_oval(points[1][0] - 4, points[1][1] - 4, points[1][0] + 4, points[1][1] + 4, outline=color, width=2)
        mid = ((points[0][0] + points[1][0]) / 2, (points[0][1] + points[1][1]) / 2)
        self.canvas.create_text(mid[0], mid[1] - 12, text=item.get("text", "Ø16"), fill=color, font=SMALL_FONT)

    def draw_contour_label(self, item, color):
        pts = item.get("points", [])
        if pts:
            x, y = self.screen(*pts[len(pts) // 2])
            self.canvas.create_text(x, y - 10, text=f"EL {item.get('elevation', 0):.2f}", fill=color, font=SMALL_FONT)

    def draw_area_label(self, item, color):
        pts = item.get("points", [])
        if len(pts) > 2:
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            x, y = self.screen(cx, cy)
            self.canvas.create_text(x, y, text=f"A={self.polygon_area(pts):.2f} {self.unit.get()}²", fill=color, font=SMALL_FONT)

    def draw_drain_label(self, item, color):
        p1, p2 = item["points"][:2]
        x, y = self.screen((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
        self.canvas.create_text(x, y - 12, text=f"S={item.get('slope', 1.0):.2f}%", fill=color, font=SMALL_FONT)

