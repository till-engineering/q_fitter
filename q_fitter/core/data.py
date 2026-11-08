"""The data of one sample (ID) and how it is read from the input folder.

What a method can use (see METHODEN.md):

    sample.id          ID of the sample
    sample.pores       table, one row per pore; the crack origin is a row too (kind == "crack")
    sample.images      Schliff images by name -> SchliffImage (labels.tif, scale, sample frame)
    sample.excel       the row of rissausgaenge.xlsx (all columns, also your own ones)
    sample.crack       the row of the crack origin (shortcut)
    sample.pixels(p)   (y, x) image pixels of a pore row p (all its labels)

Columns of sample.pores (one row per pore):

    pore_id     "crack" or "<image>:<label>" (merged pores: "<image>:<label>+<n>")
    kind        "crack" | "pore"
    image       Schliff image of the pore ("" for the crack origin)
    labels      tuple of the pore numbers in labels.tif (empty for the crack origin)
    A_raw_um2   area as read (pixel count x pixel size^2; crack origin: A0 from the Excel)
    A_um2       area that is used          <- pore models change it
    xi, zeta    position in the sample frame, 0..1   <- pore models may change it
    excluded    True = not used as competitor (e.g. near the crack origin)
    note        text, also in the result
  added by the pipeline after the pore models:
    dist_um     distance of the nearest pore pixel to the crack origin (Schliff pores)
    g_field     stress field at (xi, zeta)
    g           stress that is used        <- stress model
"""

from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
import json
import logging

import cv2
import numpy as np
import pandas as pd

log = logging.getLogger("q_fitter")

PORE_COLUMNS = ["pore_id", "kind", "image", "labels", "A_raw_um2", "A_um2", "xi", "zeta", "excluded", "note"]


@dataclass
class SchliffImage:
    """One Schliff image of Pore_Detection: labels.tif + scale + sample frame (from images.json).

    Sample frame as in Pore_Detection: origin = inner (bottom) edge meets the left edge, x along the
    outer edge to the right, z perpendicular upwards (towards the outer side); xi = x / length,
    zeta = z / thickness. Image pixels: (y, x), pixel index = pixel centre."""

    name: str
    labels: np.ndarray          # (H, W) int32, 0 = no pore, n = pore n
    pixel_size_um: float
    origin_px: tuple[float, float]   # (y, x)
    angle_deg: float
    length_px: float
    thickness_px: float

    @property
    def length_um(self) -> float:
        return self.length_px * self.pixel_size_um

    @property
    def thickness_um(self) -> float:
        return self.thickness_px * self.pixel_size_um

    @property
    def pixel_area_um2(self) -> float:
        return self.pixel_size_um ** 2

    def _axes(self):
        a = np.radians(self.angle_deg)
        return (-np.sin(a), np.cos(a)), (-np.cos(a), -np.sin(a))    # x axis, z axis as (dy, dx)

    def to_xi_zeta(self, y, x) -> tuple[np.ndarray, np.ndarray]:
        """Image pixels -> (xi, zeta), not limited to 0..1."""
        (xy, xx), (zy, zx) = self._axes()
        dy = np.asarray(y, dtype=np.float64) - self.origin_px[0]
        dx = np.asarray(x, dtype=np.float64) - self.origin_px[1]
        return (dx * xx + dy * xy) / self.length_px, (dx * zx + dy * zy) / self.thickness_px

    def to_image_px(self, xi, zeta) -> tuple[np.ndarray, np.ndarray]:
        """(xi, zeta) -> image pixels (y, x)."""
        (xy, xx), (zy, zx) = self._axes()
        x, z = np.asarray(xi) * self.length_px, np.asarray(zeta) * self.thickness_px
        return self.origin_px[0] + x * xy + z * zy, self.origin_px[1] + x * xx + z * zx

    @cached_property
    def _index(self):
        """Pixels sorted by label: flat positions + start of every label (fast lookup per pore)."""
        flat = self.labels.ravel()
        positions = np.flatnonzero(flat)
        positions = positions[np.argsort(flat[positions], kind="stable")]
        sorted_labels = flat[positions]
        return positions, sorted_labels

    def pixels(self, label: int) -> tuple[np.ndarray, np.ndarray]:
        """(y, x) of all pixels of one label."""
        positions, sorted_labels = self._index
        start, end = np.searchsorted(sorted_labels, [label, label + 1])
        return np.divmod(positions[start:end], self.labels.shape[1])

    def label_table(self) -> pd.DataFrame:
        """label, pixel count, centroid (y, x) of every label."""
        flat = self.labels.ravel()
        positions = np.flatnonzero(flat)
        ids = flat[positions]
        y, x = np.divmod(positions, self.labels.shape[1])
        count = np.bincount(ids)
        present = np.flatnonzero(count)
        return pd.DataFrame({"label": present, "count": count[present],
                             "y": np.bincount(ids, weights=y)[present] / count[present],
                             "x": np.bincount(ids, weights=x)[present] / count[present]})

    def min_distance_um(self, xi: float, zeta: float) -> dict[int, float]:
        """Per label: distance of its nearest pixel to the point (xi, zeta), in µm."""
        py, px = self.to_image_px(xi, zeta)
        flat = self.labels.ravel()
        positions = np.flatnonzero(flat)
        ids = flat[positions]
        y, x = np.divmod(positions, self.labels.shape[1])
        d = np.hypot(y - py, x - px) * self.pixel_size_um
        nearest = np.full(int(ids.max()) + 1 if len(ids) else 1, np.inf)
        np.minimum.at(nearest, ids, d)
        return {int(label): float(nearest[label]) for label in np.unique(ids)}


@dataclass
class Sample:
    id: str
    pores: pd.DataFrame
    images: dict[str, SchliffImage]
    excel: dict
    notes: list[str] = field(default_factory=list)

    @property
    def crack(self) -> pd.Series:
        return self.pores.loc[self.pores["kind"] == "crack"].iloc[0]

    def pixels(self, pore: pd.Series) -> tuple[np.ndarray, np.ndarray]:
        """(y, x) image pixels of a pore row (all its labels); empty for the crack origin."""
        if not pore["labels"]:
            return np.empty(0, int), np.empty(0, int)
        image = self.images[pore["image"]]
        parts = [image.pixels(label) for label in pore["labels"]]
        return np.concatenate([p[0] for p in parts]), np.concatenate([p[1] for p in parts])


# ----------------------------------------------------------------------------------------------
# reading the input folder

@dataclass
class Skipped:
    id: str
    reason: str


def load_samples(input_dir: Path, crack_area_column: str) -> tuple[list[Sample], list[Skipped]]:
    """All IDs of the input folder: daten/poren/<ID>_results, daten/risse/<ID>_results,
    daten/rissausgaenge.xlsx. An ID is used only if it is complete; otherwise it is skipped with a reason."""
    pores_dir, cracks_dir = input_dir / "poren", input_dir / "risse"
    excel = read_crack_excel(input_dir / "rissausgaenge.xlsx")
    ids = sorted(set(_ids(pores_dir)) | set(_ids(cracks_dir)) | set(excel))
    samples, skipped = [], []
    for sample_id in ids:
        try:
            samples.append(_load_sample(sample_id, pores_dir, cracks_dir, excel, crack_area_column))
        except SkipSample as reason:
            skipped.append(Skipped(sample_id, str(reason)))
            log.warning("%s skipped: %s", sample_id, reason)
    return samples, skipped


class SkipSample(Exception):
    pass


def read_crack_excel(path: Path) -> dict[str, dict]:
    if not path.is_file():
        raise FileNotFoundError(f"crack origin table not found: {path}")
    table = pd.read_excel(path, sheet_name=0, dtype={"ID": str})
    rows = {}
    for row in table.to_dict("records"):
        sample_id = _clean_id(row.get("ID"))
        if not sample_id:
            continue
        if sample_id in rows:
            raise ValueError(f"{path.name}: ID {sample_id} appears twice")
        rows[sample_id] = {key: (None if _is_missing(value) else value) for key, value in row.items()}
    return rows


def read_json_table(path: Path) -> pd.DataFrame:
    """Column-wise JSON table ({"column": [values]}) as written by Pore_Detection and the labeler."""
    with open(path, encoding="utf-8") as file:
        return pd.DataFrame(json.load(file))


def _ids(folder: Path) -> list[str]:
    if not folder.is_dir():
        return []
    return [p.name[: -len("_results")] for p in folder.iterdir() if p.is_dir() and p.name.endswith("_results")]


def _load_sample(sample_id, pores_dir, cracks_dir, excel, crack_area_column) -> Sample:
    if sample_id not in excel:
        raise SkipSample("not in rissausgaenge.xlsx")
    row = excel[sample_id]
    area = row.get(crack_area_column)
    if area is None or not float(area) > 0:
        raise SkipSample(f"no area in column {crack_area_column} of rissausgaenge.xlsx")

    crack_file = cracks_dir / f"{sample_id}_results" / "cracks.json"
    if not crack_file.is_file():
        raise SkipSample(f"{crack_file.relative_to(cracks_dir.parent)} missing")
    cracks = read_json_table(crack_file)
    if len(cracks) != 1:
        raise SkipSample(f"cracks.json has {len(cracks)} crack origins, exactly 1 is needed")
    xi, zeta = cracks["xi"].iloc[0], cracks["zeta"].iloc[0]
    if _is_missing(xi) or _is_missing(zeta):
        raise SkipSample("crack origin without xi / zeta (no sample frame in the labeler)")

    images, notes = _load_images(pores_dir / f"{sample_id}_results")
    if not images:
        raise SkipSample("no usable Schliff image (" + "; ".join(notes or ["poren folder missing"]) + ")")

    rows = [dict(pore_id="crack", kind="crack", image="", labels=(), A_raw_um2=float(area), A_um2=float(area),
                 xi=float(xi), zeta=float(zeta), excluded=False, note="")]
    for image in images.values():
        table = image.label_table()
        xis, zetas = image.to_xi_zeta(table["y"].to_numpy(), table["x"].to_numpy())
        areas = table["count"].to_numpy() * image.pixel_area_um2
        for label, a, pxi, pzeta in zip(table["label"], areas, xis, zetas):
            rows.append(dict(pore_id=f"{image.name}:{label}", kind="pore", image=image.name, labels=(int(label),),
                             A_raw_um2=float(a), A_um2=float(a), xi=float(pxi), zeta=float(pzeta),
                             excluded=False, note=""))
    pores = pd.DataFrame(rows, columns=PORE_COLUMNS)
    return Sample(sample_id, pores, images, row, notes)


def _load_images(folder: Path) -> tuple[dict[str, SchliffImage], list[str]]:
    images, notes = {}, []
    table_file = folder / "images.json"
    if not table_file.is_file():
        return images, [f"{folder.name}/images.json missing"]
    for row in read_json_table(table_file).to_dict("records"):
        name = row["image"]
        missing = [key for key in ("pixel_size_um", "frame_origin_px", "frame_angle_deg", "frame_length_px",
                                   "frame_thickness_px") if _is_missing(row.get(key))]
        if missing:
            notes.append(f"{name}: no {', '.join(missing)} (no scale / sample frame) - image not used")
            continue
        labels_file = folder / name / "labels.tif"
        labels = cv2.imread(str(labels_file), cv2.IMREAD_UNCHANGED)
        if labels is None:
            notes.append(f"{name}: labels.tif missing or unreadable - image not used")
            continue
        origin = row["frame_origin_px"]
        images[name] = SchliffImage(name, labels.astype(np.int32, copy=False), float(row["pixel_size_um"]),
                                    (float(origin[0]), float(origin[1])), float(row["frame_angle_deg"]),
                                    float(row["frame_length_px"]), float(row["frame_thickness_px"]))
    for note in notes:
        log.warning("%s", note)
    return images, notes


def _clean_id(value) -> str:
    if _is_missing(value):
        return ""
    text = str(value).strip()
    return text[:-2] if text.endswith(".0") and text[:-2].isdigit() else text


def _is_missing(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and np.isnan(value):
        return True
    return isinstance(value, str) and not value.strip()
