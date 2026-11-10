"""Main window: one q slider and one pore stress switch for all IDs on top, below all IDs with their sections, each section
one plot over the full width. Only the plots in view are redrawn when q changes (the others when
they are scrolled into view)."""

import matplotlib
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QMainWindow, QScrollArea,
                               QSizePolicy, QSlider, QVBoxLayout, QWidget)

from .data import METHODS, RUN
from .plot import STYLE, ImagePlot

NOTE_HEIGHT_PX = 46         # height of a section without plot (only its note)
REDRAW_DELAY_MS = 60        # slider: redraw after this pause (smooth dragging)


class Canvas(FigureCanvasQTAgg):
    def __init__(self, sample, image, config):
        with matplotlib.rc_context({**STYLE, "font.size": config["plot"]["font_size"]}):
            super().__init__(Figure())
            self.plot = ImagePlot(self.figure, sample, image, config["plot"])
        self.setMinimumSize(1, 1)                   # width follows the window (no horizontal scrolling)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.font_size = config["plot"]["font_size"]
        self.ratio = config["plot"]["height_ratio"] if image.ok else None
        self.drawn = None                           # (q, method) of the last drawing

    def show_q(self, q: float, method: str) -> None:
        if self.drawn == (q, method):
            return
        with matplotlib.rc_context({**STYLE, "font.size": self.font_size}):
            self.plot.set_q(q, method)
            self.draw()
        self.drawn = (q, method)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.drawn = None                         # number placement depends on the size


class Window(QMainWindow):
    def __init__(self, samples, config):
        super().__init__()
        self.setWindowTitle("q fitter")
        q = config["q"]
        self.q_min, self.step = q["min"], q["step"]
        steps = round((q["max"] - q["min"]) / q["step"])

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, steps)
        self.slider.setPageStep(max(1, round(1.0 / q["step"])))     # page step = 1.0 in q
        self.spin = QDoubleSpinBox()
        self.spin.setRange(q["min"], q["max"])
        self.spin.setSingleStep(q["step"])
        self.spin.setDecimals(max(0, len(f"{q['step']:g}".partition(".")[2])))
        self.spin.setMinimumWidth(90)
        self.method = QComboBox()
        for method, text in METHOD_TEXT.items():
            self.method.addItem(text, method)
        self.method.setCurrentIndex(self.method.findData(config["stress"]["pore_stress"]))
        self.method.setToolTip("How the stress of a pore is taken (for all IDs)")
        self.jump = QComboBox()
        self.jump.addItems([s.id for s in samples])
        self.jump.setMinimumWidth(120)

        bar = QHBoxLayout()
        title = QLabel("q")
        title.setStyleSheet("font-size: 16pt; font-weight: bold;")
        bar.addWidget(title)
        bar.addWidget(self.slider, 1)
        bar.addWidget(self.spin)
        bar.addSpacing(24)
        bar.addWidget(QLabel("Pore stress"))
        bar.addWidget(self.method)
        bar.addSpacing(24)
        bar.addWidget(QLabel("Go to ID"))
        bar.addWidget(self.jump)
        top = QWidget()
        top.setLayout(bar)

        self.canvases, self.headers = [], {}
        content = QWidget()
        column = QVBoxLayout(content)
        column.setSpacing(6)
        for sample in samples:
            header = QLabel(_header(sample))
            header.setTextFormat(Qt.RichText)
            header.setStyleSheet("font-size: 13pt; padding: 8px 4px 2px 4px; border-top: 2px solid #495057;")
            column.addWidget(header)
            self.headers[sample.id] = header
            for image in sample.images:
                canvas = Canvas(sample, image, config)
                column.addWidget(canvas)
                self.canvases.append(canvas)
        if not samples:
            column.addWidget(QLabel("No <ID>_results folders found in input.pores_dir (config.yaml)."))
        column.addStretch(1)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setWidget(content)
        self.content = content

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(top)
        layout.addWidget(self.scroll, 1)
        self.setCentralWidget(central)

        self.timer = QTimer(self, singleShot=True, interval=REDRAW_DELAY_MS)
        self.timer.timeout.connect(self.redraw_visible)
        self.slider.valueChanged.connect(self._slider_moved)
        self.spin.valueChanged.connect(self._spin_changed)
        self.method.currentIndexChanged.connect(lambda _: self.redraw_visible())
        self.scroll.verticalScrollBar().valueChanged.connect(lambda _: self.timer.start())
        self.jump.activated.connect(lambda i: self.scroll.verticalScrollBar().setValue(
            self.headers[self.jump.itemText(i)].y()))
        self.spin.setValue(q["start"])
        self._spin_changed(q["start"])
        self.resize(1600, 1000)

    @property
    def q(self) -> float:
        return round(self.q_min + self.slider.value() * self.step, 10)

    def _slider_moved(self, _):
        self.spin.blockSignals(True)
        self.spin.setValue(self.q)
        self.spin.blockSignals(False)
        self.timer.start()

    def _spin_changed(self, value):
        self.slider.blockSignals(True)
        self.slider.setValue(round((value - self.q_min) / self.step))
        self.slider.blockSignals(False)
        self.timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.timer.start()

    def _fit_heights(self) -> None:
        """Plot height = width of the scroll area x height_ratio (checked before every redraw: the
        width is only final once the window is laid out)."""
        width = self.scroll.viewport().width() - 20
        if width == getattr(self, "_fitted_width", None):
            return
        self._fitted_width = width
        for canvas in self.canvases:
            canvas.setFixedHeight(round(width * canvas.ratio) if canvas.ratio else NOTE_HEIGHT_PX)
        self.content.layout().activate()                # positions are needed right away

    def redraw_visible(self):
        """Redraw the plots in view for the current q and pore stress method."""
        self._fit_heights()
        top = self.scroll.verticalScrollBar().value()
        bottom = top + self.scroll.viewport().height()
        q, method = self.q, self.method.currentData()
        for canvas in self.canvases:
            y = canvas.mapTo(self.content, QPoint(0, 0)).y()
            if y < bottom and y + canvas.height() > top:
                canvas.show_q(q, method)


METHOD_TEXT = {
    RUN: "as in the run",
    "area": "area – every pixel",
    "centroid": "centroid",
    "max": "max",
    "mean": "mean over the pore",
}
assert set(METHOD_TEXT) == {RUN, *METHODS}


def _header(sample) -> str:
    ok = sum(image.ok for image in sample.images)
    text = f"<b>{sample.id}</b> &nbsp; {len(sample.images)} sections ({ok} with stress)"
    if sample.crack_file is None:
        text += " &nbsp; · &nbsp; <span style='color:#868e96'>no crack file</span>"
    else:
        cracks = ", ".join(f"{c.label} (ξ {c.xi:.2f}, ζ {c.zeta:.2f})" for c in sample.cracks) or "none"
        text += f" &nbsp; · &nbsp; cracks: {cracks} &nbsp; <span style='color:#868e96'>{sample.crack_file.name}</span>"
    if sample.crack_note:
        text += f" &nbsp; <span style='color:#d9480f'>{sample.crack_note}</span>"
    return text
