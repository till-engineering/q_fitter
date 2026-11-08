"""Area of the convex hull (smooth envelope, as with Murakami's sqrt(area))."""

import cv2
import numpy as np
import pandas as pd

from q_fitter import PoreModel, Sample, register

CORNERS = np.array([[-0.5, -0.5], [-0.5, 0.5], [0.5, -0.5], [0.5, 0.5]])


@register("convex_hull")
class ConvexHull(PoreModel):
    """A_um2 = area of the convex hull around all pixels of each Schliff pore (pixels as squares).
    After merge_clusters: the hull around the whole cluster. Position stays. Crack origin untouched."""

    params = {}

    def apply(self, pores: pd.DataFrame, sample: Sample) -> pd.DataFrame:
        for i, pore in pores[pores["kind"] == "pore"].iterrows():
            y, x = sample.pixels(pore)
            centres = np.column_stack([x, y]).astype(np.float32)
            hull = cv2.convexHull(centres).reshape(-1, 2)
            corners = (hull[:, None, :] + CORNERS[None, :, :]).reshape(-1, 2).astype(np.float32)
            area_px = cv2.contourArea(cv2.convexHull(corners))
            pores.at[i, "A_um2"] = float(area_px) * sample.images[pore["image"]].pixel_area_um2
        return pores
