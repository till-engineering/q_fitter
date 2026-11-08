"""Area of a fitted ellipse instead of the pixel area."""

import cv2
import numpy as np
import pandas as pd

from q_fitter import PoreModel, Sample, register


@register("ellipse")
class Ellipse(PoreModel):
    """A_um2 = area of an ellipse fitted to each Schliff pore (computed from its pixels again).

    fit: moments  ellipse with the same centroid and second moments as the pixels (robust, every size)
         contour  least-squares ellipse through the outline (cv2.fitEllipse; needs >= 5 outline
                  points, smaller pores fall back to moments)
    Position stays (centroid of the pixels). The crack origin is not touched (it has no shape)."""

    params = {"fit": "moments | contour"}

    def apply(self, pores: pd.DataFrame, sample: Sample) -> pd.DataFrame:
        if self.fit not in ("moments", "contour"):
            raise ValueError(f"ellipse: fit must be moments or contour, not {self.fit!r}")
        for i, pore in pores[pores["kind"] == "pore"].iterrows():
            y, x = sample.pixels(pore)
            pixel_area = sample.images[pore["image"]].pixel_area_um2
            area_px = _contour_area(y, x) if self.fit == "contour" else None
            if area_px is None:
                area_px = _moment_area(y, x)
            pores.at[i, "A_um2"] = area_px * pixel_area
        return pores


def _moment_area(y: np.ndarray, x: np.ndarray) -> float:
    """Ellipse of equal second moments: semi-axes 2 sqrt(lambda) -> area 4 pi sqrt(det C).
    + 1/12 per axis: every pixel is a unit square, not a point."""
    if len(y) == 1:
        return 1.0
    cov = np.cov(np.vstack([y, x]), bias=True) + np.eye(2) / 12.0
    return float(4.0 * np.pi * np.sqrt(max(np.linalg.det(cov), 0.0)))


def _contour_area(y: np.ndarray, x: np.ndarray) -> float | None:
    top, left = y.min(), x.min()
    crop = np.zeros((y.max() - top + 3, x.max() - left + 3), np.uint8)
    crop[y - top + 1, x - left + 1] = 1
    contours, _ = cv2.findContours(crop, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    points = np.vstack(contours).astype(np.float32)
    if len(points) < 5:
        return None
    (_, _), (width, height), _ = cv2.fitEllipse(points)
    return float(np.pi * width * height / 4.0) if width > 0 and height > 0 else None
