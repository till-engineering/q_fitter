"""The fit panel of the window (fit of q over all IDs from the stress at the crack origins, Q_FIT.md):

left   over q: u of every crack (grey) = share of Σ A g^q above the stress at its origin
       BOUND (green, main result): share of the cracks (or IDs) with u >= fit.bound.share (step
       line), the required share (dashed), the bound = smallest q that covers enough of them
       TYPICAL: ū (black), q̂ where ū = 0.5 (red, 95 % range shaded)
       the q of the slider (blue)
right  at the q of the slider: how Σ A g^q is spread over the stress (bars, all IDs with cracks),
       the stresses at the crack origins (red) and the crack that sets the bound (green): the share
       of the bars right of the green line is what the bound asks for
"""

import numpy as np
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from .fit import Fit

PORES, CRACKS, Q_HAT, Q_NOW, BOUND = "#74c0fc", "#e03131", "#e03131", "#1c7ed6", "#2b8a3e"


def decisive_stress(fit: Fit) -> float:
    """Stress at the origin of the crack that sets the bound (lowest crack of the ID if per ID)."""
    bound = fit.bound
    unit = bound.decisive
    if bound.reference == "every_crack":
        k = [f"{i} {label}" for i, label in zip(fit.ids, fit.labels)].index(unit)
        return float(fit.crack_g[k])
    return float(min(g for i, g in zip(fit.ids, fit.crack_g) if i == unit))


class FitPlot:
    def __init__(self, figure: Figure, bins: int):
        self.figure, self.bins = figure, bins
        self.curve, self.histogram = figure.subplots(1, 2, width_ratios=[1.5, 1])

    def show(self, fit: Fit, q: float) -> None:
        curve, histogram = self.curve, self.histogram
        curve.cla()
        histogram.cla()
        if not fit.ok:
            curve.text(0.5, 0.5, fit.describe() + ("\n" + "\n".join(fit.skipped) if fit.skipped else ""),
                       ha="center", va="center", transform=curve.transAxes, color="#868e96")
            histogram.set_axis_off()
            return
        histogram.set_axis_on()
        bound = fit.bound
        curve.plot(fit.q, bound.value.T, color="#ced4da", linewidth=0.8)
        low = fit.q[0] if fit.low_side else fit.low
        high = fit.q[-1] if fit.high_side else fit.high
        curve.axvspan(low, high, color=Q_HAT, alpha=0.07, linewidth=0)
        curve.plot(fit.q, fit.mean, color="black", linewidth=1.2)
        if not fit.side:
            curve.axvline(fit.q_hat, color=Q_HAT, linewidth=1.2, linestyle="--")
        curve.axhline(bound.share, color=BOUND, linestyle="--", linewidth=1.0)
        curve.step(fit.q, bound.covered, where="post", color=BOUND, linewidth=2.2)
        if not bound.side:
            curve.axvline(bound.q, color=BOUND, linewidth=2.0)
        curve.axvline(q, color=Q_NOW, linewidth=1.2)
        curve.set_xlim(fit.q[0], fit.q[-1])
        curve.set_ylim(0, 1.02)
        curve.set_xlabel("q")
        curve.set_ylabel("share")
        curve.set_title(bound.describe() + "\n" + fit.describe(), loc="left", fontsize="medium", linespacing=1.4)
        kind = "cracks" if bound.reference == "every_crack" else "IDs"
        curve.legend(handles=[
            Line2D([], [], color=BOUND, linewidth=2.2, label=f"{kind} covered (u ≥ {bound.share:.0%}) → bound"),
            Line2D([], [], color="#ced4da", linewidth=0.8, label="u: share of Σ A g^q above the crack"),
            Line2D([], [], color="black", linewidth=1.2, label="ū (mean) → typical q̂ (red)"),
            Line2D([], [], color=Q_NOW, linewidth=1.2, label="q of the slider")],
            loc="lower right", fontsize="small")

        top = max(max(float(s.g.max()) for s in p.sections) for p in fit.prepared)
        top = max(top, float(np.max(fit.crack_g)))
        bins = np.linspace(min(0.0, float(np.min(fit.crack_g))), top * (1 + 1e-9), self.bins + 1)
        pores, cracks = fit.distribution(q, bins)
        width = bins[1] - bins[0]
        histogram.bar(bins[:-1], 100 * pores, width=width, align="edge", color=PORES, edgecolor="white",
                      linewidth=0.5)
        histogram.stairs(100 * cracks, bins, color=CRACKS, linewidth=1.6)
        histogram.plot(fit.crack_g, np.zeros(len(fit.crack_g)), "|", color=CRACKS, markersize=14,
                       markeredgewidth=2, clip_on=False)
        g_bound = decisive_stress(fit)
        histogram.axvline(g_bound, color=BOUND, linewidth=2.0)
        i = int(np.argmin(np.abs(fit.q - q)))
        k = bound.units.index(bound.decisive)
        reached = "bound reached" if bound.covered[i] >= bound.cracks - 1e-9 else "below the bound → larger q"
        histogram.set_title(f"q = {q:g}:  {bound.covered[i]:.0%} of the {kind} covered ({reached})\n"
                            f"{bound.value[k, i]:.0%} of Σ A g^q right of the green line ({bound.decisive})",
                            loc="left", fontsize="medium", linespacing=1.4)
        histogram.set_xlim(bins[0], bins[-1])
        histogram.set_xlabel("stress g")
        histogram.set_ylabel("share (%)")
        histogram.legend(handles=[Patch(color=PORES, label="pores: share of Σ A g^q"),
                                  Line2D([], [], color=CRACKS, linewidth=1.6, label="crack origins"),
                                  Line2D([], [], color=BOUND, linewidth=2.0, label="crack that sets the bound")],
                         loc="upper left", fontsize="small")
