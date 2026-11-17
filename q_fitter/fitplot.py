"""The fit panel (FIT.md).

left   cumulated share over the stress g in [g_min, g_top] (g_top: as far as the stress field reaches): every measured curve (dashed, thick),
       the model at its fitted q (same colour, thin), the model at the q of the slider (black) and,
       for comparison, the crack origins of the input (grey steps; not used by the fit)
right  RMS distance between model and every curve over q, fitted q marked, slider q as a line
"""

import numpy as np
from matplotlib.figure import Figure

from .fit import Fit, Fitter

CURVE_COLORS = ("#d9480f", "#0f6d8c", "#2b8a3e", "#7048e8", "#c2255c", "#e67700")
SLIDER = "#212529"
CRACKS = "#868e96"


def curve_color(k: int) -> str:
    return CURVE_COLORS[k % len(CURVE_COLORS)]


class FitPlot:
    def __init__(self, figure: Figure, fitter: Fitter):
        self.figure, self.fitter = figure, fitter
        self.curves_ax, self.rms_ax = figure.subplots(1, 2, width_ratios=(1.3, 1))
        self.crack_g = _crack_stresses(fitter)

    def show(self, fit: Fit, q: float) -> None:
        ax, rms = self.curves_ax, self.rms_ax
        ax.clear()
        rms.clear()
        fitter, grid = self.fitter, self.fitter.grid
        if not fit.ok:
            ax.text(0.5, 0.5, fit.note, ha="center", va="center", transform=ax.transAxes, color=CRACKS)
            rms.set_axis_off()
            return
        rms.set_axis_on()
        method = fit.method
        if len(self.crack_g):
            g = np.sort(self.crack_g)
            ax.step(np.concatenate([[fitter.g_min], g, [fitter.g_top]]),
                    np.concatenate([[0], np.arange(1, len(g) + 1) / len(g), [1]]) * 100, where="post",
                    color=CRACKS, linewidth=1.0, label=f"cracks in input (n = {len(g)})")
        for k, result in enumerate(fit.results):
            color = curve_color(k)
            ax.plot(grid, result.curve.values * 100, "--", color=color, linewidth=2.2, label=result.curve.name)
            if np.isfinite(result.q):
                ax.plot(grid, fitter.model(result.q, method) * 100, color=color, linewidth=1.2,
                        label=f"model q = {result.q:.2f}")
        ax.plot(grid, fitter.model(q, method) * 100, color=SLIDER, linewidth=1.4, label=f"model q = {q:g} (slider)")
        ax.set_xlim(fitter.g_min, fitter.g_top)
        ax.set_ylim(0, 102)
        ax.set_xlabel("relative stress g")
        ax.set_ylabel("cumulated share (%)")
        title = "measured curves and model F_q(g)"
        if fitter.g_top < fitter.g_max:
            title += f"  ·  compared up to g = {fitter.g_top:.3f} (highest stress of the fields), curves scaled to 100 % there"
        ax.set_title(title, loc="left", fontsize="medium")
        ax.legend(loc="upper left", fontsize="small")

        for k, result in enumerate(fit.results):
            color = curve_color(k)
            rms.plot(fit.q_scan, fit.rms_scan[k] * 100, color=color, linewidth=1.4)
            if np.isfinite(result.q):
                rms.plot(result.q, result.rms * 100, "o", color=color, markersize=6)
        rms.axvline(q, color=SLIDER, linewidth=1.0)
        rms.set_xlim(fit.q_scan[0], fit.q_scan[-1])
        rms.set_ylim(bottom=0)
        rms.set_xlabel("q")
        rms.set_ylabel("RMS distance (%)")
        lines = []
        for k, result in enumerate(fit.results):
            text = f"{result.curve.name}: q = {result.q:.2f}, RMS {result.rms * 100:.1f} %"
            if result.at_limit:
                text += "  (at the edge of the q range!)"
            if result.curve.warning:
                text += f"  – {result.curve.warning}"
            lines.append(text)
        rms.set_title("\n".join(lines), loc="left", fontsize="small")


def _crack_stresses(fitter: Fitter) -> np.ndarray:
    """g at every crack origin of the input (stress field of the first section of its ID), only
    the cracks in [g_min, g_top]."""
    values = []
    for sample in fitter.samples:
        image = next((image for image in sample.images if image.ok), None)
        if image is None or not sample.cracks:
            continue
        g = image.stress.evaluate([c.xi for c in sample.cracks], [c.zeta for c in sample.cracks])
        values.extend(float(v) for v in np.atleast_1d(g))
    values = np.array(values)
    return values[(values >= fitter.g_min) & (values <= fitter.g_top)]
