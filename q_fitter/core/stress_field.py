"""Stress fields: one YAML file per field, same format as Fatigue_crack_labeler / Pore_Detection.

Variables: xi = x / length, zeta = z / thickness, both 0..1 in the sample frame (zeta = 0 inner /
bottom edge, 1 outer / top edge). A file has either `formula` (NumPy expression in xi and zeta) or
`grid` (support points, interpolated bilinearly):

    name: Bending (relative)    # optional
    unit: "-"
    formula: "abs(2*zeta - 1)"

    grid:
      xi:   [0.0, 0.5, 1.0]
      zeta: [0.0, 1.0]
      sigma: [[0, 10, 0], [300, 320, 300]]   # rows = zeta, columns = xi

For the evaluation xi and zeta are limited to 0..1.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

FORMULA_NAMES = {name: getattr(np, name) for name in (
    "abs", "sqrt", "exp", "log", "log10", "sin", "cos", "tan", "arcsin", "arccos", "arctan", "sinh", "cosh",
    "tanh", "minimum", "maximum", "clip", "where", "sign", "floor", "ceil", "pi", "e")}
FORMULA_NAMES["min"], FORMULA_NAMES["max"] = np.minimum, np.maximum


@dataclass(frozen=True)
class StressField:
    key: str                    # file name without .yaml
    name: str
    unit: str
    formula: str | None = None
    grid_xi: np.ndarray | None = None
    grid_zeta: np.ndarray | None = None
    grid_sigma: np.ndarray | None = None    # (len(zeta), len(xi))

    def evaluate(self, xi, zeta) -> np.ndarray:
        """Stress at (xi, zeta) (numbers or arrays), limited to the sample."""
        xi = np.clip(np.asarray(xi, dtype=np.float64), 0.0, 1.0)
        zeta = np.clip(np.asarray(zeta, dtype=np.float64), 0.0, 1.0)
        if self.formula is not None:
            value = eval(self.formula, {"__builtins__": {}}, {**FORMULA_NAMES, "xi": xi, "zeta": zeta})
            return np.array(np.broadcast_to(np.asarray(value, dtype=np.float64), np.broadcast(xi, zeta).shape))
        return _bilinear(self.grid_xi, self.grid_zeta, self.grid_sigma, xi, zeta)

    def describe(self) -> str:
        if self.formula is not None:
            return f"{self.key}: sigma = {self.formula} [{self.unit}]"
        return f"{self.key}: grid {len(self.grid_zeta)} x {len(self.grid_xi)} (zeta x xi) [{self.unit}]"


def load_field(folder: Path, key: str) -> StressField:
    path = Path(folder) / f"{key}.yaml"
    if not path.is_file():
        found = ", ".join(p.stem for p in Path(folder).glob("*.yaml")) or "none"
        raise FileNotFoundError(f"stress field '{key}' not found in {folder} (available: {found})")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    name, unit = str(data.get("name", key)), str(data.get("unit", ""))
    if ("formula" in data) == ("grid" in data):
        raise ValueError(f"{path.name}: exactly one of 'formula' and 'grid' is needed")
    if "formula" in data:
        field = StressField(key, name, unit, formula=str(data["formula"]))
    else:
        grid = data["grid"]
        xi, zeta = np.asarray(grid["xi"], dtype=np.float64), np.asarray(grid["zeta"], dtype=np.float64)
        sigma = np.asarray(grid["sigma"], dtype=np.float64)
        if sigma.shape != (len(zeta), len(xi)):
            raise ValueError(f"{path.name}: sigma has shape {sigma.shape}, expected ({len(zeta)}, {len(xi)})")
        if np.any(np.diff(xi) <= 0) or np.any(np.diff(zeta) <= 0):
            raise ValueError(f"{path.name}: xi and zeta must be strictly ascending")
        field = StressField(key, name, unit, grid_xi=xi, grid_zeta=zeta, grid_sigma=sigma)
    field.evaluate(np.array([0.0, 0.5, 1.0]), np.array([0.0, 0.5, 1.0]))   # fails here, not during a run
    return field


def _bilinear(xs, zs, values, x, z) -> np.ndarray:
    x, z = np.broadcast_arrays(x, z)
    if len(xs) == 1 and len(zs) == 1:
        return np.full(x.shape, values[0, 0])
    if len(xs) == 1:
        return np.interp(z, zs, values[:, 0])
    if len(zs) == 1:
        return np.interp(x, xs, values[0])
    i = np.clip(np.searchsorted(xs, x) - 1, 0, len(xs) - 2)
    j = np.clip(np.searchsorted(zs, z) - 1, 0, len(zs) - 2)
    tx = np.clip((x - xs[i]) / (xs[i + 1] - xs[i]), 0.0, 1.0)
    tz = np.clip((z - zs[j]) / (zs[j + 1] - zs[j]), 0.0, 1.0)
    bottom = values[j, i] * (1 - tx) + values[j, i + 1] * tx
    top = values[j + 1, i] * (1 - tx) + values[j + 1, i + 1] * tx
    return bottom * (1 - tz) + top * tz
