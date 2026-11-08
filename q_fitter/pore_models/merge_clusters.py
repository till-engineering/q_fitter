"""Merge Schliff pores that lie close together (pore clusters) into one pore."""

import math

import cv2
import numpy as np
import pandas as pd

from q_fitter import PoreModel, Sample, register


@register("merge_clusters")
class MergeClusters(PoreModel):
    """Schliff pores whose edges are closer than gap_um become one pore (only within one image).

    How: every pore is grown by gap_um / 2 (rounded up to whole pixels); pores whose grown areas touch
    belong to one cluster - so the gap is met to about one pixel. The merged pore:
        A_um2      sum of the A_um2 of its parts (changes of earlier pore models are kept)
        A_raw_um2  sum of the raw areas
        xi, zeta   centroid of all its pixels (raw areas as weights)
        labels     all labels of its parts
    The crack origin is not touched."""

    params = {"gap_um": "largest gap between two pore edges in µm that still merges them"}

    def apply(self, pores: pd.DataFrame, sample: Sample) -> pd.DataFrame:
        keep = [pores[pores["kind"] == "crack"]]
        for name, image in sample.images.items():
            in_image = pores[(pores["kind"] == "pore") & (pores["image"] == name)]
            if in_image.empty:
                continue
            radius_px = max(0, math.ceil(self.gap_um / 2 / image.pixel_size_um))
            used = np.zeros(int(image.labels.max()) + 1, bool)
            for labels in in_image["labels"]:
                used[list(labels)] = True
            mask = used[image.labels].astype(np.uint8)
            if radius_px > 0:   # grow by radius_px: distance to the nearest pore pixel (fast for any radius)
                distance = cv2.distanceTransform(1 - mask, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
                mask = (distance <= radius_px).astype(np.uint8)
            _, clusters = cv2.connectedComponents(mask, connectivity=8)
            cluster_of_label = np.zeros(len(used), np.int64)
            cluster_of_label[image.labels[image.labels > 0]] = clusters[image.labels > 0]
            group = in_image["labels"].map(lambda labels: cluster_of_label[labels[0]])
            for _, part in in_image.groupby(group.to_numpy(), sort=False):
                keep.append(part if len(part) == 1 else _merge(part))
        return pd.concat(keep, ignore_index=True).infer_objects()


def _merge(part: pd.DataFrame) -> pd.DataFrame:
    weights = part["A_raw_um2"].to_numpy()
    first = part.iloc[0]
    merged = first.copy()
    merged["pore_id"] = f"{first['pore_id']}+{len(part) - 1}"
    merged["labels"] = tuple(label for labels in part["labels"] for label in labels)
    merged["A_raw_um2"] = weights.sum()
    merged["A_um2"] = part["A_um2"].sum()
    merged["xi"] = np.average(part["xi"], weights=weights)
    merged["zeta"] = np.average(part["zeta"], weights=weights)
    merged["excluded"] = bool(part["excluded"].any())
    merged["note"] = _join([f"merged from {len(part)} pores"] + [n for n in part["note"] if n])
    return merged.to_frame().T


def _join(notes) -> str:
    return "; ".join(dict.fromkeys(notes))
