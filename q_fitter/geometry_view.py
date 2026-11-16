"""Window of the geometry check (geometry_main.py): tables of the frames and cracks, one plot per ID,
"Save report" writes <output_dir>/<ID>.png and geometry_check.xlsx.

Plot of an ID:
left    absolute (µm): every frame as a rectangle centred on (0, 0), the outline of the sample
        (roi_mask.tif) in it, the crack origins on their fracture surface
middle  relative (xi, zeta): the same, every frame stretched to the unit square – what the q fitter
        uses; outlines that do not fill the square the same way show different shapes
right   deviation of length, thickness and length / thickness of every frame from the median of
        the ID (%), the tolerance shaded
"""

import math

import matplotlib
import numpy as np
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QScrollArea,
                               QSizePolicy, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from .data import resolve
from .geometry import FRACTURE, OFF_SCALE, IdGeometry, crack_table, frame_table
from .plot import STYLE, section_color, section_letter

FRACTURE_COLORS = ("#e03131", "#f08c00", "#c2255c", "#862e9c")
CRACK = "#00b8d4"
BAD = QColor("#ffe3e3")


def frame_labels(geometry: IdGeometry) -> list[tuple[str, str]]:
    """(short label, colour) of every frame: sections A, B, … as in the q fitter, fractures F1, F2, …"""
    labels = [(section_letter(k), section_color(k)) for k in range(len(geometry.sections))]
    labels += [(f"F{k + 1}", FRACTURE_COLORS[k % len(FRACTURE_COLORS)]) for k in range(len(geometry.fractures))]
    return labels


def draw_id(figure: Figure, geometry: IdGeometry, tolerance: float) -> None:
    absolute, relative, deviation = figure.subplots(1, 3, width_ratios=[1.2, 1.0, 1.1])
    frames, labels = geometry.frames, frame_labels(geometry)
    fractures = {f.image: f for f in geometry.fractures}
    length, thickness, aspect = geometry.median()

    def in_scale(frame) -> bool:
        """Frame with scale and not wildly off the median (wrong scale): drawn in µm."""
        if not np.isfinite(frame.pixel_size_um):
            return False
        ratios = (frame.length_um / length, frame.thickness_um / thickness)
        return all(1 / OFF_SCALE <= r <= OFF_SCALE for r in ratios)
    scaled = [f for f in frames if in_scale(f)]

    for frame, (label, color) in zip(frames, labels):
        style = dict(color=color, linewidth=1.6, linestyle="--" if frame.source == FRACTURE else "-")
        if in_scale(frame):
            L, T, s = frame.length_um, frame.thickness_um, frame.pixel_size_um
            absolute.add_patch(Rectangle((-L / 2, -T / 2), L, T, fill=False, **style))
            if frame.outline is not None:
                absolute.fill(frame.outline[:, 0] * s - L / 2, frame.outline[:, 1] * s - T / 2, color=color,
                              alpha=0.10, linewidth=0.8)
        relative.add_patch(Rectangle((0, 0), 1, 1, fill=False, **{**style, "linewidth": 1.0}))
        if frame.outline is not None:
            relative.plot(np.append(frame.outline[:, 0], frame.outline[0, 0]) / frame.length_px,
                          np.append(frame.outline[:, 1], frame.outline[0, 1]) / frame.thickness_px,
                          color=color, linewidth=1.0, linestyle=style["linestyle"])
    for crack in geometry.cracks:
        fracture = fractures.get(crack.image) or (geometry.fractures[0] if geometry.fractures else None)
        relative.plot(crack.xi, crack.zeta, "X", color=CRACK, markersize=9, markeredgecolor="black")
        relative.annotate(crack.label, (crack.xi, crack.zeta), xytext=(6, 4), textcoords="offset points",
                          color="black", fontweight="bold")
        if fracture is not None and in_scale(fracture):
            x = (crack.xi - 0.5) * fracture.length_um
            z = (crack.zeta - 0.5) * fracture.thickness_um
            absolute.plot(x, z, "X", color=CRACK, markersize=9, markeredgecolor="black")
            absolute.annotate(crack.label, (x, z), xytext=(6, 4), textcoords="offset points", fontweight="bold")

    if scaled:
        extent = max(max(f.length_um, f.thickness_um) for f in scaled) * 0.6
        absolute.set_xlim(-extent, extent)
        absolute.set_ylim(-extent, extent)
    else:
        absolute.text(0.5, 0.5, "no frame with scale", ha="center", va="center", transform=absolute.transAxes)
    absolute.set_aspect("equal")
    absolute.set_xlabel("x (µm), centred")
    absolute.set_ylabel("z (µm), outer surface on top")
    absolute.set_title("absolute (µm)", loc="left")
    relative.set_xlim(-0.08, 1.08)
    relative.set_ylim(-0.08, 1.08)
    relative.set_aspect("equal")
    relative.set_xlabel("ξ")
    relative.set_ylabel("ζ")
    relative.set_title("relative (as used in the q fitter)", loc="left")
    handles = [Line2D([], [], color=c, linestyle="--" if f.source == FRACTURE else "-", label=f"{l}  {f.image}"
                      + ("  (by hand)" if f.manual else "") + ("" if in_scale(f) else "  (no / wrong scale: not in µm)"))
               for f, (l, c) in zip(frames, labels)]
    handles.append(Line2D([], [], marker="X", color=CRACK, markeredgecolor="black", linestyle="", label="crack origin"))
    figure.legend(handles=handles, fontsize="small", loc="outside lower left", ncols=min(4, len(handles)),
                  frameon=False)

    x = np.arange(len(frames))
    width = 0.27
    for k, (name, values, color) in enumerate((
            ("length", [100 * (f.length_um / length - 1) for f in frames], "#495057"),
            ("thickness", [100 * (f.thickness_um / thickness - 1) for f in frames], "#adb5bd"),
            ("length/thickness", [100 * (f.aspect / aspect - 1) for f in frames], "#1c7ed6"))):
        values = np.array(values, dtype=float)
        shown = np.where(np.isfinite(values), values, 0.0)
        deviation.bar(x + (k - 1) * width, np.clip(shown, -100, 100), width=width, color=color, label=name)
        for xi, value in zip(x + (k - 1) * width, values):
            if np.isfinite(value) and abs(value) > 100:          # off the axis: write the factor
                deviation.text(xi, math.copysign(98, value), f"×{1 + value / 100:.2g}", rotation=90,
                               fontsize="x-small", ha="center", va="top" if value > 0 else "bottom")
    deviation.axhspan(-tolerance, tolerance, color="#d3f9d8", zorder=0)
    deviation.axhline(0, color="black", linewidth=0.8)
    deviation.set_xticks(x, [l for l, _ in labels])
    for tick, (_, color) in zip(deviation.get_xticklabels(), labels):
        tick.set_color(color)
    deviation.set_ylim(-100, 100)
    deviation.set_ylabel("deviation from the median of the ID (%)")
    deviation.set_title(f"sizes (tolerance ±{tolerance:g} % shaded)", loc="left")
    deviation.legend(fontsize="x-small", loc="lower right")
    figure.suptitle(f"{geometry.id}:  median length {length:.4g} µm, thickness {thickness:.4g} µm, "
                    f"length/thickness {aspect:.3f}", x=0.01, ha="left", fontsize="large")


class IdCanvas(FigureCanvasQTAgg):
    def __init__(self, geometry: IdGeometry, config: dict):
        g = config["geometry"]
        with matplotlib.rc_context({**STYLE, "font.size": config["plot"]["font_size"]}):
            super().__init__(Figure(figsize=(15, g["plot_height_px"] / 100), layout="constrained"))
            draw_id(self.figure, geometry, g["tolerance_percent"])
        self.setMinimumSize(1, 1)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(g["plot_height_px"])


class GeometryWindow(QMainWindow):
    def __init__(self, geometries: list[IdGeometry], config: dict):
        super().__init__()
        self.setWindowTitle("q fitter – geometry check")
        self.geometries, self.config = geometries, config
        g = config["geometry"]
        self.frames = frame_table(geometries, g["tolerance_percent"], g["wedge_max_deg"])
        self.cracks = crack_table(geometries)

        bad = int((self.frames["check"] != "ok").sum()) if len(self.frames) else 0
        summary = QLabel(f"{len(geometries)} IDs, {len(self.frames)} frames, {bad} conspicuous "
                         f"(tolerance ±{g['tolerance_percent']:g} %, wedge > {g['wedge_max_deg']:g}°)")
        summary.setStyleSheet("font-size: 12pt;")
        save = QPushButton("Save report")
        save.clicked.connect(self.save)
        bar = QHBoxLayout()
        bar.addWidget(summary, 1)
        bar.addWidget(save)

        tabs = QTabWidget()
        tabs.addTab(self._table(self.frames, bad_column="check"), "Frames")
        tabs.addTab(self._table(self.cracks), "Cracks (error of the relative position)")
        plots = QWidget()
        column = QVBoxLayout(plots)
        self.canvases = []
        for geometry in geometries:
            canvas = IdCanvas(geometry, config)
            self.canvases.append((geometry.id, canvas))
            if geometry.missing:
                note = QLabel("<br>".join(f"{geometry.id} – {m}" for m in geometry.missing))
                note.setStyleSheet("color: #868e96;")
                note.setWordWrap(True)
                column.addWidget(note)
            column.addWidget(canvas)
        column.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(plots)
        tabs.addTab(scroll, "Plots per ID")

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(bar)
        layout.addWidget(tabs, 1)
        self.setCentralWidget(central)
        self.resize(1500, 950)

    def _table(self, table, bad_column=None) -> QTableWidget:
        widget = QTableWidget(len(table), len(table.columns))
        widget.setHorizontalHeaderLabels([str(c) for c in table.columns])
        for r, row in enumerate(table.itertuples(index=False)):
            bad = bad_column is not None and getattr(row, bad_column) != "ok"
            for c, value in enumerate(row):
                text = f"{value:.4g}" if isinstance(value, float) else str(value)
                item = QTableWidgetItem("" if text == "nan" else text)
                if bad:
                    item.setBackground(BAD)
                widget.setItem(r, c, item)
        widget.resizeColumnsToContents()
        return widget

    def save(self) -> None:
        folder = resolve(self.config["geometry"]["output_dir"])
        folder.mkdir(parents=True, exist_ok=True)
        try:
            with pd.ExcelWriter(folder / "geometry_check.xlsx", engine="openpyxl") as writer:
                self.frames.to_excel(writer, sheet_name="Frames", index=False)
                self.cracks.to_excel(writer, sheet_name="Cracks", index=False)
        except PermissionError:
            QMessageBox.warning(self, "Save report", f"{folder / 'geometry_check.xlsx'} is open in another program.")
            return
        for image_id, canvas in self.canvases:
            canvas.figure.savefig(folder / f"{image_id}.png", dpi=130)
        QMessageBox.information(self, "Save report", f"written to {folder}")

