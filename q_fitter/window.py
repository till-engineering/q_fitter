"""Main window: one q slider and one pore stress switch for all IDs on top, below all IDs, each ID
one plot over the full width (Pareto of all its sections + the pictures of all its sections). The
plot height follows from the width (pictures as large as possible, at most max_height_ratio of the
visible height). Only the plots in view are redrawn when q changes (the others when they are
scrolled into view). On top (button "Fit q"): the fit of q to the measured crack curves of
config.yaml fit.curves (FIT.md); "q → fit" puts the slider on the fitted q of the chosen curve."""

import matplotlib
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtWidgets import (QApplication, QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QMainWindow, QPushButton,
                               QScrollArea, QSizePolicy, QSlider, QVBoxLayout, QWidget)

from .data import METHODS, RUN
from .fit import Fitter
from .fitplot import FitPlot
from .plot import STYLE, SamplePlot, section_color, section_letter

REDRAW_DELAY_MS = 60        # slider: redraw after this pause (smooth dragging)


class Canvas(FigureCanvasQTAgg):
    def __init__(self, sample, config):
        with matplotlib.rc_context({**STYLE, "font.size": config["plot"]["font_size"]}):
            super().__init__(Figure())
            self.plot = SamplePlot(self.figure, sample, config["plot"])
        self.setMinimumSize(1, 1)                   # width follows the window (no horizontal scrolling)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.font_size = config["plot"]["font_size"]
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


class FitCanvas(FigureCanvasQTAgg):
    """The fit panel (fitplot.FitPlot)."""

    def __init__(self, config, fitter):
        self.font_size = config["plot"]["font_size"]
        with matplotlib.rc_context({**STYLE, "font.size": self.font_size}):
            super().__init__(Figure(layout="constrained"))
            self.plot = FitPlot(self.figure, fitter)
        self.setMinimumSize(1, 1)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(config["fit"]["panel_height_px"])
        self.drawn = None

    def show_fit(self, fit, q: float) -> None:
        if self.drawn == (id(fit), q):
            return
        with matplotlib.rc_context({**STYLE, "font.size": self.font_size}):
            self.plot.show(fit, q)
            self.draw()
        self.drawn = (id(fit), q)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.drawn = None


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
        self.fitter = Fitter(samples, config)
        self.show_fit = QPushButton("Fit q")
        self.show_fit.setCheckable(True)
        self.show_fit.setChecked(True)
        self.show_fit.setToolTip("Fit of q to the measured crack curves (fit.curves in config.yaml, FIT.md)")
        self.curve = QComboBox()
        for curve in self.fitter.curves:
            self.curve.addItem(curve.name)
        self.curve.setToolTip("Curve whose fitted q the button sets")
        self.curve.setVisible(len(self.fitter.curves) > 1)
        self.to_fit = QPushButton("q → fit")
        self.to_fit.setToolTip("Slider to the fitted q of the curve")
        self.to_fit.setEnabled(bool(self.fitter.curves))

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
        bar.addSpacing(24)
        bar.addWidget(self.show_fit)
        bar.addWidget(self.curve)
        bar.addWidget(self.to_fit)
        top = QWidget()
        top.setLayout(bar)

        self.canvases, self.headers = [], {}
        content = QWidget()
        column = QVBoxLayout(content)
        column.setSpacing(6)
        for sample in samples:
            header = QLabel(_header(sample))
            header.setTextFormat(Qt.RichText)
            header.setWordWrap(True)                # a long header must not widen the plots (cut off right)
            header.setMinimumWidth(1)
            header.setStyleSheet("font-size: 13pt; padding: 8px 4px 2px 4px; border-top: 2px solid #495057;")
            column.addWidget(header)
            self.headers[sample.id] = header
            canvas = Canvas(sample, config)
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
        self.fit_canvas = FitCanvas(config, self.fitter)
        layout.addWidget(top)
        layout.addWidget(self.fit_canvas)
        layout.addWidget(self.scroll, 1)
        self.setCentralWidget(central)

        self.timer = QTimer(self, singleShot=True, interval=REDRAW_DELAY_MS)
        self.timer.timeout.connect(self.redraw_visible)
        self.slider.valueChanged.connect(self._slider_moved)
        self.spin.valueChanged.connect(self._spin_changed)
        self.method.currentIndexChanged.connect(lambda _: self.redraw_visible())
        self.show_fit.toggled.connect(self._toggle_fit)
        self.to_fit.clicked.connect(self._to_fit)
        self.scroll.verticalScrollBar().valueChanged.connect(lambda _: self.timer.start())
        self.jump.activated.connect(lambda i: self.scroll.verticalScrollBar().setValue(
            self.headers[self.jump.itemText(i)].y()))
        self.spin.setValue(q["start"])
        self._spin_changed(q["start"])
        self.plot_config = config["plot"]
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

    def _fit(self):
        """The fit for the selected pore stress method (computed once per method, wait cursor)."""
        method = self.method.currentData()
        if not self.fitter.cached(method):
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                self.fitter.fit(method)
            finally:
                QApplication.restoreOverrideCursor()
        return self.fitter.fit(method)

    def _toggle_fit(self, shown: bool) -> None:
        self.fit_canvas.setVisible(shown)
        self.timer.start()

    def _to_fit(self) -> None:
        fit = self._fit()
        k = self.curve.currentIndex()
        if fit.ok and 0 <= k < len(fit.results):
            self.spin.setValue(round(fit.results[k].q / self.step) * self.step)

    def _fit_heights(self) -> None:
        """Plot heights from the width of the plots and the visible height (checked before every
        redraw: the size is only final once the window is laid out)."""
        margins = self.content.layout().contentsMargins()
        width = self.scroll.viewport().width() - margins.left() - margins.right()
        size = (width, self.scroll.viewport().height())
        if size == getattr(self, "_fitted_size", None):
            return
        self._fitted_size = size
        plot = self.plot_config
        max_height = max(plot["min_height_px"], plot["max_height_ratio"] * size[1])
        for canvas in self.canvases:
            canvas.setFixedHeight(canvas.plot.height_for(width, max_height, plot["min_height_px"]))
        self.content.layout().activate()                # positions are needed right away

    def redraw_visible(self):
        """Redraw the plots in view for the current q and pore stress method."""
        self._fit_heights()
        top = self.scroll.verticalScrollBar().value()
        bottom = top + self.scroll.viewport().height()
        q, method = self.q, self.method.currentData()
        if self.fit_canvas.isVisible():
            self.fit_canvas.show_fit(self._fit(), q)
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
    ok = [image for image in sample.images if image.ok]
    text = f"<b>{sample.id}</b> &nbsp; {len(sample.images)} sections ({len(ok)} with stress"
    text += ": " + ", ".join(f"<b style='color:{section_color(k)}'>{section_letter(k)}</b> {image.name}"
                             for k, image in enumerate(ok)) + ")" if ok else ")"
    if sample.crack_file is None:
        text += " &nbsp; · &nbsp; <span style='color:#868e96'>no crack file</span>"
    else:
        cracks = ", ".join(f"{c.label} (ξ {c.xi:.2f}, ζ {c.zeta:.2f})" for c in sample.cracks) or "none"
        text += f" &nbsp; · &nbsp; cracks: {cracks} &nbsp; <span style='color:#868e96'>{sample.crack_file.name}</span>"
    if sample.crack_note:
        text += f" &nbsp; <span style='color:#d9480f'>{sample.crack_note}</span>"
    for image in sample.images:
        if not image.ok:
            text += f"<br><span style='color:#868e96; font-size:10pt'>{image.name}: {image.note}</span>"
    return text
