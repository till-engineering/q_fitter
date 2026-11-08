"""TEMPLATE for a pore model - copy this file (name without "_"), rename, write your change.

Files starting with "_" are not loaded, so this one is never active.
Selected in config.yaml (a chain, executed in this order):

    pore_models:
      - name: merge_clusters
        gap_um: 5
      - name: area_factor
        factor: 1.5
        apply_to: pore

What you get: `pores`, one row per pore (a copy - change it freely and return it):
    pores["kind"]        "crack" | "pore"      -> treat crack origin and Schliff pores differently
    pores["A_um2"]       area that is used     -> change it
    pores["A_raw_um2"]   area as read (do not change)
    pores["xi"], pores["zeta"]   position 0..1 -> change it (the stress is computed afterwards)
    pores["image"], pores["labels"]   where the pore is in labels.tif
    pores["excluded"], pores["note"]  exclude a pore with a reason
Raw data of a pore row p:
    y, x = sample.pixels(p)                    all its pixels in the image
    image = sample.images[p["image"]]          image.labels, image.pixel_size_um, image.pixel_area_um2,
                                               image.to_xi_zeta(y, x), image.to_image_px(xi, zeta)
    sample.excel                               the Excel row of the sample (own columns allowed)
To merge or split pores: return a table with other rows (exactly one crack row must stay).
"""

import pandas as pd

from q_fitter import PoreModel, Sample, register


@register("area_factor")
class AreaFactor(PoreModel):
    """Example: multiply the area by a fixed factor."""

    params = {"factor": "area factor", "apply_to": "pore | crack | both"}

    def apply(self, pores: pd.DataFrame, sample: Sample) -> pd.DataFrame:
        rows = pores["kind"] == self.apply_to if self.apply_to != "both" else slice(None)
        pores.loc[rows, "A_um2"] *= self.factor
        return pores
