"""Fit of ONE q for all IDs from the stress at the crack origins (maths: Q_FIT.md).

Only the stress at the origin of every crack is used – not its position and not the size of the
pore it started at. For a crack c of an ID, with g_c = stress of the field of the sections at the
crack's xi, zeta:

    u_c(q) = share of Σ w g^q (all parts of all sections of the ID, parts of the pore stress
             method as in the Pareto) that lies at a stress above g_c; parts at exactly g_c count half

If the pore model with this q describes at which stress cracks start, the u_c are draws from the
uniform distribution on 0..1, so their mean ū = 0.5. Every u_c rises with q (more weight on high
stress), so there is one q̂ with ū(q̂) = 0.5.

BOUND (the main result): the smallest q at which the critical pores lie above the crack origins:
at least fit.bound.share of Σ w g^q lies at a stress above the crack origin, i.e. u_c(q) >= share,
for every crack (reference every_crack) or for the least loaded crack of every ID (reference
lowest_crack_per_id), and that for at least fit.bound.cracks of the cracks / IDs. u_c rises with q,
so every crack has one q from which on it is covered; the bound is the corresponding quantile of
these q. Larger q always covers more – the bound is the smallest q that is enough.

TYPICAL q̂: ū(q̂) = 0.5 (above). Interval (95 %): all q at which ū does not differ significantly from 0.5, i.e. |ū(q) - 0.5| <= c with
c = 97.5 % quantile of |mean of the crack weights x uniform numbers - 0.5| (simulated, exact also
for few cracks). Spread over the IDs: bootstrap (IDs drawn with replacement, q̂ fitted again), only
with at least fit.min_ids IDs.
"""

from dataclasses import dataclass, field

import numpy as np

from .data import Sample

SIMULATED = 20000               # draws of uniform numbers for the critical value of the interval
DIGITS = 9                      # g rounded to merge parts of equal stress (speed only, no effect on u)


@dataclass
class _Section:
    g: np.ndarray               # sorted distinct stresses of the parts
    w: np.ndarray               # summed weight w per stress
    lo: np.ndarray              # per crack: first index with g >= g_c
    hi: np.ndarray              # per crack: first index with g > g_c


@dataclass
class _Prepared:
    id: str
    labels: list[str]
    crack_g: np.ndarray         # (cracks,) stress at the origin (field of the first section)
    sections: list[_Section]

    def shares(self, q: float) -> np.ndarray:
        """u of every crack of the ID at this q (nan if no pore contributes)."""
        above, equal, total = np.zeros(len(self.labels)), np.zeros(len(self.labels)), 0.0
        for s in self.sections:
            with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
                v = s.w * s.g ** q
            v = np.where(np.isfinite(v), v, 0.0)
            tail = np.append(np.cumsum(v[::-1])[::-1], 0.0)        # tail[k] = Σ v[k:]
            above += tail[s.hi]
            equal += tail[s.lo] - tail[s.hi]
            total += tail[0]
        if not total > 0:
            return np.full(len(self.labels), np.nan)
        return (above + 0.5 * equal) / total

    def distribution(self, q: float, bins: np.ndarray) -> np.ndarray:
        """Share of Σ w g^q of the ID per stress bin (sums to 1)."""
        histogram = np.zeros(len(bins) - 1)
        for s in self.sections:
            with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
                v = s.w * s.g ** q
            histogram += np.histogram(s.g, bins, weights=np.where(np.isfinite(v), v, 0.0))[0]
        total = histogram.sum()
        return histogram / total if total > 0 else histogram


@dataclass
class Bound:
    """Smallest q at which at least `share` of Σ w g^q lies above the crack origins (see above)."""
    share: float
    reference: str              # every_crack | lowest_crack_per_id
    cracks: float               # share of the cracks / IDs that must be covered
    units: list[str]            # what must be covered: "S001 C1" (every crack) or "S001" (lowest crack per ID)
    value: np.ndarray           # (units, q) share of Σ w g^q above the unit's crack
    unit_q: np.ndarray          # q from which on the unit is covered (inf: not up to q max)
    covered: np.ndarray         # (q,) share of the units covered
    q: float                    # the bound (nan: not reached up to q max)
    side: str                   # "" | "below" (covered already at q min) | "above" (not reached up to q max)
    decisive: str               # the unit that sets the bound

    def describe(self) -> str:
        what = "every crack" if self.reference == "every_crack" else "the least loaded crack of every ID"
        kind = "cracks" if self.reference == "every_crack" else "IDs"
        scope = f"for {self.cracks:.0%} of the {kind}" if self.cracks < 1 else f"for all {len(self.units)} {kind}"
        if self.side == "above":
            head = f"bound q > q max: not reached (decided by {self.decisive})"
        elif self.side == "below":
            head = "bound q ≤ q min (covered everywhere)"
        else:
            head = f"bound q = {self.q:.2f} (set by {self.decisive})"
        return f"{head}  ·  ≥ {self.share:.0%} of Σ A g^q above {what}, {scope}"


@dataclass
class Fit:
    method: str
    q: np.ndarray               # grid (the q of the slider)
    u: np.ndarray               # (cracks, len(q)) u of every crack
    ids: list[str]              # ID of every crack
    labels: list[str]           # C1, C2, … of every crack
    crack_g: np.ndarray         # stress at the origin of every crack
    weights: np.ndarray         # weight of every crack in ū (fit.weight)
    mean: np.ndarray            # ū(q)
    q_hat: float
    side: str                   # "" | "below" (ū >= 0.5 already at q min) | "above" (ū < 0.5 up to q max)
    low: float                  # 95 % interval (model: u uniform at the right q)
    high: float
    low_side: str               # "below": the interval reaches q min (lower end open), else ""
    high_side: str              # "above": the interval reaches q max (upper end open), else ""
    spread: tuple               # (2.5 %, 97.5 %) of q̂ over the IDs (bootstrap), (nan, nan) if too few IDs
    skipped: list[str] = field(default_factory=list)       # cracks / IDs not used, with reason
    prepared: list[_Prepared] = field(default_factory=list, repr=False)
    bound: Bound | None = None

    @property
    def ok(self) -> bool:
        return len(self.labels) > 0

    def describe(self) -> str:
        if not self.ok:
            return "fit of q: no crack with pore results"
        if self.side == "above":
            text = f"typical q̂ > {self.q[-1]:g} (ū < 0.5 up to q max)"
        elif self.side == "below":
            text = f"typical q̂ ≤ {self.q[0]:g} (ū ≥ 0.5 already at q min)"
        else:
            text = f"typical q̂ = {self.q_hat:.2f} (ū = 0.5)"
        low = f"≤ {self.low:g}" if self.low_side else f"{self.low:.2f}"
        high = f"> {self.high:g}" if self.high_side else f"{self.high:.2f}"
        text += f",  95 %: {low} … {high}"
        if np.isfinite(self.spread[0]):
            text += f"  ·  over the IDs: {self.spread[0]:.2f} … {self.spread[1]:.2f}"
        return f"{text}  ·  {len(self.labels)} cracks / {len(set(self.ids))} IDs  ·  {self.method}"

    def distribution(self, q: float, bins: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(pores, cracks): share per stress bin – pores: Σ w g^q of the IDs (each ID with the weight
        of its cracks), cracks: their stresses at the origin (with their weights). Both sum to 1."""
        pores = np.zeros(len(bins) - 1)
        for prepared in self.prepared:
            weight = self.weights[[i for i, crack_id in enumerate(self.ids) if crack_id == prepared.id]].sum()
            pores += weight * prepared.distribution(q, bins)
        cracks = np.histogram(np.clip(self.crack_g, bins[0], bins[-1]), bins, weights=self.weights)[0]
        total = self.weights.sum()
        return pores / total, cracks / total


class Fitter:
    """Fits q for every pore stress method on demand (cached); u of the cracks of one ID at any q."""

    def __init__(self, samples: list[Sample], config: dict):
        self.samples = samples
        q, fit = config["q"], config["fit"]
        steps = round((q["max"] - q["min"]) / q["step"])
        self.q = np.round(q["min"] + np.arange(steps + 1) * q["step"], 10)
        self.weight, self.bootstrap, self.min_ids, self.seed = fit["weight"], fit["bootstrap"], fit["min_ids"], fit["seed"]
        if self.weight not in ("crack", "id"):
            raise ValueError(f"config.yaml fit.weight: '{self.weight}' – allowed: crack, id")
        bound = fit["bound"]
        self.share, self.reference, self.cover = float(bound["share"]), bound["reference"], float(bound["cracks"])
        if self.reference not in ("every_crack", "lowest_crack_per_id"):
            raise ValueError(f"config.yaml fit.bound.reference: '{self.reference}' – allowed: every_crack, lowest_crack_per_id")
        if not (0 < self.share < 1 and 0 < self.cover <= 1):
            raise ValueError("config.yaml fit.bound: share must lie between 0 and 1, cracks between 0 and 1")
        self._prepared: dict[tuple[str, str], _Prepared | None] = {}
        self._fits: dict[str, Fit] = {}

    def prepared(self, sample: Sample, method: str) -> _Prepared | None:
        key = (sample.id, method)
        if key not in self._prepared:
            self._prepared[key] = _prepare(sample, method)
        return self._prepared[key]

    def shares(self, sample: Sample, q: float, method: str) -> np.ndarray | None:
        """u of every crack of the sample at q (None: no crack or no section with stress)."""
        prepared = self.prepared(sample, method)
        return None if prepared is None else prepared.shares(q)

    def cached(self, method: str) -> bool:
        """The fit of this method is already computed."""
        return method in self._fits

    def fit(self, method: str) -> Fit:
        if method not in self._fits:
            self._fits[method] = self._fit(method)
        return self._fits[method]

    def _fit(self, method: str) -> Fit:
        rows, ids, labels, crack_g, used, skipped = [], [], [], [], [], []
        for sample in self.samples:
            if not sample.cracks:
                continue
            prepared = self.prepared(sample, method)
            if prepared is None:
                skipped.append(f"{sample.id}: {len(sample.cracks)} crack(s), but no section with stress")
                continue
            u = np.array([prepared.shares(q) for q in self.q]).T              # (cracks, q)
            for k, label in enumerate(prepared.labels):
                if not np.all(np.isfinite(u[k])):
                    skipped.append(f"{sample.id} {label}: no pore contributes at some q")
                    continue
                rows.append(u[k])
                ids.append(sample.id)
                labels.append(label)
                crack_g.append(prepared.crack_g[k])
            used.append(prepared)
        u = np.array(rows).reshape(len(rows), len(self.q))
        if self.weight == "id":
            weights = np.array([1.0 / ids.count(i) for i in ids])
        else:
            weights = np.ones(len(ids))
        if not ids:
            return Fit(method, self.q, u, ids, labels, np.array(crack_g), weights, np.full(len(self.q), np.nan),
                       np.nan, "", np.nan, np.nan, "", "", (np.nan, np.nan), skipped, used)
        mean = weights @ u / weights.sum()
        q_hat, side = _crossing(self.q, mean[None, :])
        rng = np.random.default_rng(self.seed)
        uniform = rng.random((SIMULATED, len(weights))) @ weights / weights.sum()
        c = np.quantile(np.abs(uniform - 0.5), 0.95)
        (low,), (low_side,) = _crossing(self.q, mean[None, :], 0.5 - c)
        (high,), (high_side,) = _crossing(self.q, mean[None, :], 0.5 + c)
        low_side = "below" if low_side == "below" else ""
        high_side = "above" if high_side == "above" else ""
        spread = (np.nan, np.nan)
        distinct = sorted(set(ids))
        if len(distinct) >= self.min_ids and self.bootstrap > 0:
            counts = rng.multinomial(len(distinct), np.full(len(distinct), 1 / len(distinct)), size=self.bootstrap)
            crack_weights = counts[:, [distinct.index(i) for i in ids]] * weights          # (bootstrap, cracks)
            means = crack_weights @ u / crack_weights.sum(axis=1, keepdims=True)
            draws, _ = _crossing(self.q, means)
            spread = tuple(float(v) for v in np.percentile(draws, [2.5, 97.5]))
        return Fit(method, self.q, u, ids, labels, np.array(crack_g), weights, mean, float(q_hat[0]), side[0],
                   float(low), float(high), low_side, high_side, spread, skipped, used,
                   self._bound(u, ids, labels, weights))

    def _bound(self, u, ids, labels, weights) -> Bound:
        if self.reference == "every_crack":
            units = [f"{i} {label}" for i, label in zip(ids, labels)]
            value, unit_weights = u, weights
        else:                                       # the least loaded crack of an ID has the largest u
            units = sorted(set(ids))
            value = np.array([u[[k for k, i in enumerate(ids) if i == unit]].max(axis=0) for unit in units])
            unit_weights = np.ones(len(units))
        crossing, sides = _crossing(self.q, value, self.share)
        unit_q = np.where([side == "above" for side in sides], np.inf, crossing)
        covered = (value >= self.share).astype(float).T @ unit_weights / unit_weights.sum()
        order = np.argsort(unit_q, kind="stable")
        reached = np.cumsum(unit_weights[order]) / unit_weights.sum() >= self.cover - 1e-9
        k = order[int(np.argmax(reached))]
        q_bound = float(unit_q[k])
        if not np.isfinite(q_bound):
            side = "above"
        elif sides[k] == "below":
            side = "below"
        else:
            side = ""
        return Bound(self.share, self.reference, self.cover, units, value, unit_q, covered,
                     q_bound if np.isfinite(q_bound) else np.nan, side, units[k])


def _prepare(sample: Sample, method: str) -> _Prepared | None:
    images = [image for image in sample.images if image.ok]
    if not images or not sample.cracks:
        return None
    xi = np.array([crack.xi for crack in sample.cracks])
    zeta = np.array([crack.zeta for crack in sample.cracks])
    sections, first = [], None
    for image in images:
        _, w, g = image.parts[image.method(method)]
        g, inverse = np.unique(np.round(np.asarray(g, dtype=np.float64), DIGITS), return_inverse=True)
        w = np.bincount(inverse, weights=w, minlength=len(g))
        crack_g = np.round(np.asarray(image.stress.evaluate(xi, zeta), dtype=np.float64), DIGITS)
        first = crack_g if first is None else first
        sections.append(_Section(g, w, np.searchsorted(g, crack_g, "left"), np.searchsorted(g, crack_g, "right")))
    return _Prepared(sample.id, [crack.label for crack in sample.cracks], first, sections)


def _crossing(q: np.ndarray, means: np.ndarray, level: float = 0.5) -> tuple[np.ndarray, list[str]]:
    """Per row of means (ū over q): the q where ū first reaches level (linear between grid points);
    q min with side "below" if ū >= level already there, q max with side "above" if never."""
    reached = means >= level
    first = reached.argmax(axis=1)
    found = reached.any(axis=1)
    k = np.maximum(first, 1)
    rows = np.arange(len(means))
    m0, m1 = means[rows, k - 1], means[rows, k]
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(m1 > m0, (level - m0) / (m1 - m0), 0.0)
    result = q[k - 1] + np.clip(t, 0, 1) * (q[k] - q[k - 1])
    result = np.where(first == 0, q[0], result)
    result = np.where(found, result, q[-1])
    side = ["" if f and k0 > 0 else ("below" if f else "above") for f, k0 in zip(found, first)]
    return result, side
