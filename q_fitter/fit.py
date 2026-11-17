"""Fit of q to measured crack curves (FIT.md).

The curves (config.yaml fit.curves) are the cumulated frequency of the crack origins over the
relative stress g, from 0 % at fit.g_min (mean stress, 0.5) to 100 % at fit.g_max (full stress, 1),
entered as formulas in g (e.g. the cubic trend line from Excel).

Compared is only the range in which the stress field exists: up to g_top = min(g_max, highest
stress of the fields of the sections). Both curves are taken conditional on [g_min, g_top]: the
measured curve is scaled to 0 at g_min and 1 at g_top (a field that reaches only 0.98 at the edge
compares the distribution of the cracks between 0.5 and 0.98, nothing is assumed above).

The model for a q: the crack origins are spread over the stress like Σ A g^q of the pores, so the
model curve is the share of Σ A g^q that lies at a stress <= g, counting only pores in
[g_min, g_top]:

    F_q(g) = Σ_{g_k <= g} w_k g_k^q / Σ_{g_min <= g_k <= g_top} w_k g_k^q

(w_k, g_k = the parts of the pores with the pore stress method, data.py). fit.weight = id: F_q is
the mean of F_q of every ID (every ID counts the same, the sections of an ID are summed);
pore: Σ A g^q of all IDs together.

The fitted q of a curve minimises the RMS distance between F_q and the curve on fit.points
evenly spaced stresses: scan over the q range of the slider, then refined (golden section).
"""

import math
import re
from dataclasses import dataclass, field

import numpy as np

from .data import Sample
from .stress import FORMULA_NAMES

WEIGHTS = ("id", "pore")
GOLDEN = (math.sqrt(5) - 1) / 2
TOLERANCE_Q = 1e-4
FIELD_SAMPLES = 401             # per axis: highest stress of a field (formula) on this mesh over the frame


# ------------------------------------------------------------------------------------ curves

def parse_formula(text: str) -> str:
    """Formula as written by hand or copied from an Excel trend line -> NumPy expression in g.
    Allowed besides NumPy: 'x' for g, '^' / '²' / '³' for powers, 'x3' for x^3 (Excel loses the
    superscript when copied), '3x' for 3*x, a decimal comma between digits ('1,5' = 1.5; separate
    function arguments with ', ') and a leading 'y ='."""
    s = str(text).strip()
    s = re.sub(r"^\s*[yY]\s*=", "", s)
    s = s.replace("−", "-").replace("²", "^2").replace("³", "^3").replace("^", "**")
    s = re.sub(r"(?<=\d),(?=\d)", ".", s)
    s = re.sub(r"(?<![A-Za-z_])([xg])(\d)", r"\1**\2", s)          # x3 -> x**3
    s = re.sub(r"(\d)\s*(?=[xg](?![A-Za-z_]))", r"\1*", s)          # 3x -> 3*x
    return re.sub(r"\bx\b", "g", s)


@dataclass
class Curve:
    name: str
    formula: str                # as in config.yaml
    expression: str             # NumPy expression in g
    values: np.ndarray          # target share 0..1 on the grid
    warning: str = ""           # e.g. not rising everywhere


def load_curves(fit: dict, grid: np.ndarray) -> list[Curve]:
    """The curves of config.yaml on the grid [g_min, g_top], scaled to 0 at g_min and 1 at g_top."""
    curves = []
    for k, entry in enumerate(fit.get("curves") or []):
        name = str(entry.get("name", f"curve {k + 1}"))
        formula = str(entry["formula"])
        expression = parse_formula(formula)
        try:
            raw = eval(expression, {"__builtins__": {}}, {**FORMULA_NAMES, "g": grid})
        except Exception as error:
            raise ValueError(f"config.yaml fit.curves '{name}': formula '{formula}' cannot be evaluated "
                             f"(read as '{expression}'): {type(error).__name__}: {error}") from error
        raw = np.broadcast_to(np.asarray(raw, dtype=np.float64), grid.shape).copy()
        if not np.all(np.isfinite(raw)):
            raise ValueError(f"config.yaml fit.curves '{name}': formula is not finite on [{grid[0]}, {grid[-1]}]")
        warning = ""
        span = raw[-1] - raw[0]         # percent or share; small offsets of the trend line do not matter
        if span <= 0:
            raise ValueError(f"config.yaml fit.curves '{name}': value at g = {grid[-1]:.3g} not above "
                             f"the value at g_min")
        values = (raw - raw[0]) / span
        if np.any(np.diff(values) < -1e-6):
            warning = "curve falls in places (cumulated frequency must rise)"
        curves.append(Curve(name, formula, expression, values, warning))
    return curves


# ------------------------------------------------------------------------------------ model

@dataclass
class _Id:
    """The pore parts of one ID with g in [g_min, g_top], sorted by g."""
    weight: np.ndarray
    g: np.ndarray
    log_g: np.ndarray
    index: np.ndarray           # per grid point: number of parts with g <= grid point


@dataclass
class Result:
    curve: Curve
    q: float                    # fitted q (nan: no model)
    rms: float                  # RMS distance at q (share 0..1)
    at_limit: bool = False      # minimum at the edge of the q range


@dataclass
class Fit:
    method: str
    q_scan: np.ndarray
    rms_scan: np.ndarray        # (curves, q)
    results: list[Result] = field(default_factory=list)
    note: str = ""              # why there is no model

    @property
    def ok(self) -> bool:
        return not self.note


class Fitter:
    def __init__(self, samples: list[Sample], config: dict):
        fit, q = config["fit"], config["q"]
        if fit["weight"] not in WEIGHTS:
            raise ValueError(f"config.yaml fit.weight: '{fit['weight']}' – allowed: {', '.join(WEIGHTS)}")
        self.samples, self.weight = samples, fit["weight"]
        self.g_min, self.g_max = float(fit["g_min"]), float(fit["g_max"])
        if not 0 < self.g_min < self.g_max:
            raise ValueError("config.yaml fit: 0 < g_min < g_max needed")
        self.field_max = _field_max(samples)
        self.g_top = min(self.g_max, self.field_max) if np.isfinite(self.field_max) else self.g_max
        if self.g_top <= self.g_min:
            raise ValueError(f"the stress fields reach only g = {self.field_max:.3g}, not above "
                             f"config.yaml fit.g_min = {self.g_min:g}")
        self.grid = np.linspace(self.g_min, self.g_top, int(fit["points"]))
        self.curves = load_curves(fit, self.grid)
        self.q_scan = np.arange(q["min"], q["max"] + q["step"] / 2, q["step"])
        self._prepared, self._fits = {}, {}

    # ---------------------------------------------------------------- model curve

    def _ids(self, method: str) -> list[_Id]:
        if method not in self._prepared:
            ids = []
            for sample in self.samples:
                weights, gs = [], []
                for image in sample.images:
                    if image.ok:
                        _, w, g = image.parts[image.method(method)]
                        keep = (g >= self.g_min) & (g <= self.g_top) & (w > 0)
                        weights.append(w[keep])
                        gs.append(g[keep])
                if weights and sum(len(w) for w in weights):
                    w, g = np.concatenate(weights), np.concatenate(gs)
                    order = np.argsort(g, kind="stable")
                    w, g = w[order].astype(np.float64), g[order].astype(np.float64)
                    ids.append(_Id(w, g, np.log(g), np.searchsorted(g, self.grid, side="right")))
            self._prepared[method] = ids
        return self._prepared[method]

    def model(self, q: float, method: str) -> np.ndarray | None:
        """F_q on the grid (share 0..1), None without pores in the range."""
        ids = self._ids(method)
        if not ids:
            return None
        parts = []
        for one in ids:
            values = one.weight * np.exp(q * (one.log_g - one.log_g[-1]))   # scaled: no underflow
            cumulative = np.concatenate([[0.0], np.cumsum(values)])
            parts.append((cumulative[one.index], cumulative[-1], one.log_g[-1]))
        if self.weight == "id":
            return np.mean([c / total for c, total, _ in parts], axis=0)
        top = max(scale for _, _, scale in parts)                   # common scale of all IDs
        factor = [math.exp(q * (scale - top)) for _, _, scale in parts]
        return sum(c * f for (c, _, _), f in zip(parts, factor)) / sum(t * f for (_, t, _), f in zip(parts, factor))

    def _rms(self, q: float, curve: Curve, method: str) -> float:
        return float(np.sqrt(np.mean((self.model(q, method) - curve.values) ** 2)))

    # ---------------------------------------------------------------- fit

    def cached(self, method: str) -> bool:
        return method in self._fits

    def fit(self, method: str) -> Fit:
        if method not in self._fits:
            self._fits[method] = self._fit(method)
        return self._fits[method]

    def _fit(self, method: str) -> Fit:
        if not self.curves:
            return Fit(method, self.q_scan, np.empty((0, len(self.q_scan))), note="no curves in config.yaml fit.curves")
        if not self._ids(method):
            return Fit(method, self.q_scan, np.empty((0, len(self.q_scan))),
                       note=f"no pores with g in [{self.g_min:g}, {self.g_top:.3g}]")
        models = np.array([self.model(q, method) for q in self.q_scan])         # (q, grid)
        targets = np.array([c.values for c in self.curves])                     # (curves, grid)
        rms = np.sqrt(np.mean((models[None, :, :] - targets[:, None, :]) ** 2, axis=2))
        fit = Fit(method, self.q_scan, rms)
        for k, curve in enumerate(self.curves):
            best = int(np.argmin(rms[k]))
            lo = self.q_scan[max(best - 1, 0)]
            hi = self.q_scan[min(best + 1, len(self.q_scan) - 1)]
            q = _golden(lambda value: self._rms(value, curve, method), lo, hi)
            at_limit = best in (0, len(self.q_scan) - 1)
            fit.results.append(Result(curve, q, self._rms(q, curve, method), at_limit))
        return fit


def _field_max(samples: list[Sample]) -> float:
    """The lowest of the highest stresses of the fields of all sections (each over its sample frame,
    xi and zeta 0..1): up to there every section has stresses; nan without sections."""
    tops, done = [], {}
    axis = np.linspace(0.0, 1.0, FIELD_SAMPLES)
    for sample in samples:
        for image in sample.images:
            if not image.ok:
                continue
            field = image.stress
            if field.key not in done:
                xs, zs = axis, axis
                if field.grid_xi is not None:           # the maximum of a bilinear grid lies on a node
                    xs = np.union1d(axis, np.clip(field.grid_xi, 0, 1))
                    zs = np.union1d(axis, np.clip(field.grid_zeta, 0, 1))
                xi, zeta = np.meshgrid(xs, zs)
                done[field.key] = float(np.nanmax(field.evaluate(xi, zeta)))
            tops.append(done[field.key])
    return min(tops) if tops else math.nan


def _golden(function, lo: float, hi: float) -> float:
    """Minimum of a function on [lo, hi] (golden section search)."""
    a, b = lo, hi
    c, d = b - GOLDEN * (b - a), a + GOLDEN * (b - a)
    fc, fd = function(c), function(d)
    while b - a > TOLERANCE_Q:
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - GOLDEN * (b - a)
            fc = function(c)
        else:
            a, c, fc = c, d, fd
            d = a + GOLDEN * (b - a)
            fd = function(d)
    q = (a + b) / 2
    ends = [(function(lo), lo), (function(q), q), (function(hi), hi)]
    return min(ends)[1]
