"""g = stress field at the centroid of the pore, unchanged."""

import numpy as np
import pandas as pd

from q_fitter import Sample, StressModel, register


@register("field")
class FieldStress(StressModel):
    """g = g_field: the value of the stress field at (xi, zeta) of the pore, unchanged."""

    params = {}

    def stress(self, pores: pd.DataFrame, sample: Sample) -> np.ndarray:
        return pores["g_field"].to_numpy()
