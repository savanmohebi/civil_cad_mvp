# CivilCAD Pro MVP

CivilCAD Pro MVP is a Python desktop application for lightweight 2D CAD-style drafting focused on civil engineering sketches, conceptual plans, simple quantity takeoff, and education. The active GUI is built with **PySide6**, while the geometry/document logic is kept separate in `cad_core.py` for easier future development.

## Run

Install the GUI dependency first:

```bash
python -m pip install -r requirements.txt
```

Then start the app:

```bash
python civil_cad_mvp.py
```

or:

```bash
python3 civil_cad_mvp.py
```

## 📂 Project Structure (Modular Architecture)

The project has transitioned to a modular structure to ensure scalability, enabling easier integration of AI-driven engineering tools and complex geometric computations.
```text
civil_cad_mvp/
├── civil_cad_mvp.py      # Entry point (Bootstrap script)
├── app_pyside.py         # Main GUI Controller (PySide6 Logic)
├── cad_core.py           # Legacy Core Interface / Bridge
├── canvas_renderer.py    # Rendering engine for drawing operations
├── requirements.txt      # Dependency manifest
├── README.md             # Project documentation
│
├── core/                 # 🧠 Geometric & Engineering Logic
│   ├── geometry.py       # Vector math, intersections, and spatial logic
│   ├── document.py       # CAD state management & Undo/Redo stacks
│   └── quantities.py     # Civil engineering estimation & takeoff engines
│
├── ui/                   # 🎨 User Interface Components
│   ├── main_window.ui    # Qt Designer layouts
│   ├── widgets/          # Custom property editors & layer managers
│   └── dialogs/          # Template pickers & export settings
│
├── theme/                # 🌓 Visual Styles & Branding
│   ├── styles.qss        # Qt Style Sheets (Engineering Night, Blueprint, etc.)
│   └── icons/            # SVG/PNG assets for drafting tools
│
├── units/                # 📏 Coordinate & Unit Systems
│   ├── conversion.py     # Metric/Imperial & Civil scale management
│   └── projections.py    # Local coordinate system mappings
│
├── outputs/              # 📤 Generated Reports & Exports
│   ├── dxf_export/       # DXF schema handlers
│   └── reports/          # PDF/CSV Quantity takeoff templates
│
├── tests/                # 🧪 Quality Assurance & Regression
│   ├── test_core.py      # Unit tests for geometry engines
│   └── test_ui.py        # Integration tests for GUI workflows
│
└── .vscode/              # ⚙️ Development Environment settings

## Main Features

- Persian/right-to-left friendly desktop interface
- Multiple visual themes:
  - Engineering Night
  - Classic Light
  - Blueprint Blue
  - Site Green
  - Soil and Concrete
- Layer management:
  - Create layers
  - Rename layers
  - Change layer colors
  - Hide/show layers
  - Lock/unlock layers
- Item properties panel:
  - Change item layer
  - Change line width
  - Set custom item color
  - Set custom text/label
- Grid, snap, and ortho drafting aids
- Snap modes for grid, endpoints, midpoints, and real segment intersections
- Drawing statistics dock with item counts, visible/hidden counts, layer counts, and drawing extents
- Unsaved-change prompts when creating a new drawing, opening a file, or exiting
- Select, move, delete, copy, and paste
- Undo and redo
- Zoom, pan, zoom to fit, zoom in/out, and reset zoom

## Drawing Tools

- Line / road axis
- Polyline
- Arc / simple curve
- Beam
- Column
- Wall
- Drain pipe with slope label
- Dimension
- Persian text label
- Contour/elevation line
- Footing
- Rebar
- Length and angle measurement
- Polygon area calculation

## Editing Tools

- Offset for lines, walls, beams, and polylines
- Approximate trim from item end
- Approximate extend from item end
- Copy / paste
- Delete

## Civil Templates

The Templates menu can insert ready-made civil examples:

- Road section
- Isolated footing
- Simple drainage plan

## Reports and Export

- Simple quantity report grouped by layer and item type
- Save/open `.ccad` project files
- SVG export with metadata, layer attributes, polygons, and simple arcs
- Simple DXF export with closed areas and rectangle outlines for columns/footings

## Controls

- Left click: start drawing or select an item
- Left drag: preview drawing or move selected item
- Double click: finish polyline or area polygon
- Right/middle drag: pan
- Mouse wheel: zoom
- `Ctrl+S`: save
- `Ctrl+Shift+S`: save as
- `Ctrl+O`: open
- `Ctrl+N`: new drawing
- `Ctrl+Z`: undo
- `Ctrl+Y`: redo
- `Ctrl+C`: copy
- `Ctrl+V`: paste
- `Delete`: delete selected item
- `Esc`: cancel active tool
- `F2`: zoom to fit
- `Ctrl++`: zoom in
- `Ctrl+-`: zoom out
- `Ctrl+0`: reset zoom

## Tests

Run the core CAD test suite with:

```bash
python -m unittest discover -s tests
```

## Important Note

This project is still an MVP. It is not a replacement for AutoCAD, Civil 3D, or other production CAD/BIM tools. It is intended for simple drafting, learning, conceptual civil sketches, quantity experiments, and continued development.

## Future Ideas

- More advanced snapping and object tracking
- Reference-based trim/extend
- Hatch patterns for concrete, soil, and section fills
- Direct PDF printing/export
- Real DXF import
- Professional coordinate system and drawing scale tools
- Road/drainage longitudinal profiles
- Cut/fill volume calculations
