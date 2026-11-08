"""Base classes of the three kinds of methods. A new method derives from one of them, gets
@register("name") and lives in its own file in the matching folder - see METHODEN.md."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .data import Sample
from .registry import Method


class PoreModel(Method):
    """Changes the pores BEFORE the stress is computed: area, position, merging, ...
    Runs as a chain (config: pore_models, in that order). Gets the pore table of one sample and
    returns the changed table. Columns: see q_fitter/core/data.py (A_um2, xi, zeta, labels, kind, ...)."""

    kind = "pore_model"

    def apply(self, pores: pd.DataFrame, sample: Sample) -> pd.DataFrame:
        raise NotImplementedError


class StressModel(Method):
    """Computes the stress g that is used, one value per row of the pore table (crack origin included).
    The table already has g_field = stress field at (xi, zeta). Exactly one per run (config: stress.model)."""

    kind = "stress_model"

    def stress(self, pores: pd.DataFrame, sample: Sample) -> np.ndarray:
        raise NotImplementedError


@dataclass
class FitResult:
    per_sample: pd.DataFrame | None = None          # one row per sample, column "ID" (joined into the sheet Proben)
    per_pore: dict[str, pd.DataFrame] = field(default_factory=dict)   # ID -> columns added to the pore table
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)     # own sheets / JSON files
    figures: dict = field(default_factory=dict)                       # file name (without .png) -> matplotlib figure


@dataclass
class Prediction:
    """What a fit predicts with its q - used by the quality control (config: validation)."""
    q: float                         # one q: the crack origin must be the most severe pore at it (hit, rank)
    q_values: np.ndarray             # grid points of the fitted q range: share of the range in which it wins
    k: float | None = None           # sharpness of failure (M2) -> P(crack origin); None = no probability
    info: dict = field(default_factory=dict)   # extra columns of the split table (e.g. M1: V min)


class Fit(Method):
    """Determines q from all samples (M1, later M2, M3 ...). Config: fits (any number)."""

    kind = "fit"

    def fit(self, samples: list[Sample]) -> FitResult:
        raise NotImplementedError

    def prediction(self, result: FitResult) -> Prediction | None:
        """q (and k) of a result for predicting new samples. None = this fit cannot predict
        (then it is left out of the quality control) or the result has no q."""
        return None
