"""TEMPLATE for a stress model - copy this file (name without "_"), rename, write your formula.

Files starting with "_" are not loaded, so this one is never active.
Selected in config.yaml:

    stress:
      field: bending
      model:
        name: surface_notch
        k_surface: 1.5
        decay_um: 200

What you get (one row per pore, crack origin included - same formula for both!):
    pores["g_field"]   stress field at the centroid (already computed)
    pores["A_um2"]     area after the pore models
    pores["xi"], pores["zeta"]   position 0..1
    pores["kind"]      "crack" | "pore"
    sample.images[name].thickness_um / .length_um   sample size of the Schliff image in µm
    sample.excel       the Excel row of the sample (own columns allowed)
What you return: one g per row (numpy array, same order).
"""

import numpy as np
import pandas as pd

from q_fitter import Sample, StressModel, register


@register("surface_notch")
class SurfaceNotch(StressModel):
    """Example: g = g_field * K, K falls from k_surface at the outer surface to 1 inside."""

    params = {"k_surface": "notch factor directly at the outer surface (zeta = 1)",
              "decay_um": "distance from the surface in µm over which K falls to 1/e of its excess"}

    def stress(self, pores: pd.DataFrame, sample: Sample) -> np.ndarray:
        thickness_um = next(iter(sample.images.values())).thickness_um     # sample thickness in µm
        depth_um = (1.0 - pores["zeta"].to_numpy()) * thickness_um          # distance to the outer surface
        k = 1.0 + (self.k_surface - 1.0) * np.exp(-depth_um / self.decay_um)
        return pores["g_field"].to_numpy() * k
