"""Reads the input: the results of Pore_Detection (<ID>_results folders) and the crack reports of the
Fatigue_crack_labeler (<ID>_cracks.xlsx), matched by the ID.

Per image everything needed to draw the Pareto of the pore contributions A g^q for ANY q is
prepared once: pores.json only holds them for the q_values of the run, so they are computed again
from labels.tif, the sample frame (images.json) and the stress field – exactly as pore_index of
Pore_Detection does it (same pore_stress, pores split pixel by pixel at the zone boundary):

    contribution of pore i = sum over its parts k of  w_k * g_k^q
        area      every pixel is a part:  w = 1,          g = stress at the pixel
        centroid  pore part per zone:     w = part area,  g = stress at the centroid of the part
        max       pore part per zone:     w = part area,  g = highest stress in the part

Positions: xi = x / length, zeta = z / thickness in the sample frame (zeta = 0 inner, 1 outer).
The cracks of the labeler (xi, zeta on the fracture surface) are drawn at the same xi, zeta on
every section of the ID.
"""

import json
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import yaml

from .stress import load_field

PROJECT_DIR = Path(__file__).resolve().parent.parent
CONFIG = PROJECT_DIR / "config.yaml"
RESULTS_SUFFIX = "_results"
CRACKS_SUFFIX = "_cracks.xlsx"
CRACKS_SHEET = "Cracks"
ZONE_BOUNDARY = 0.5         # zeta of the boundary between inner and outer zone (as pore_index)
PORE_STRESS = ("centroid", "area", "max")


def load_config() -> dict:
    with open(CONFIG, encoding="utf-8") as file:
        return yaml.safe_load(file)


def resolve(path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else PROJECT_DIR / path


@dataclass
class Crack:
    label: str              # C1, C2, … numbered over the ID
    image: str              # image of the labeler (fracture surface)
    xi: float
    zeta: float


@dataclass
class Image:
    """One section of an ID. note != "": no Pareto possible (reason shown instead)."""

    name: str
    note: str = ""
    info: str = ""                          # stress field, pore_stress, picture source
    pore_ids: np.ndarray = None             # (n,) pore numbers as in Pore_Detection
    pore_zeta: np.ndarray = None            # (n,) zeta of the pore centroid (zone colour)
    pore_xy: np.ndarray = None              # (n, 2) centroid in picture px
    part_pore: np.ndarray = None            # (m,) index of the pore of every part
    part_weight: np.ndarray = None          # (m,)
    part_g: np.ndarray = None               # (m,)
    sample_area_px2: float = math.nan
    picture: np.ndarray = None              # straightened sample, RGB uint8, outer surface on top
    # picture px = scale * (frame px + margin): x to the right, z upwards
    scale: float = 1.0
    margin_px: float = 0.0
    length_px: float = 0.0
    thickness_px: float = 0.0

    @property
    def ok(self) -> bool:
        return not self.note

    def contributions(self, q: float) -> np.ndarray:
        """A g^q of every pore (px²)."""
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            values = self.part_weight * self.part_g ** q
        return np.bincount(self.part_pore, weights=values, minlength=len(self.pore_ids))

    def to_picture(self, xi, zeta) -> tuple[np.ndarray, np.ndarray]:
        """(xi, zeta) -> picture px (x, y)."""
        x = self.scale * (np.asarray(xi) * self.length_px + self.margin_px)
        y = self.scale * (self.thickness_px + self.margin_px - np.asarray(zeta) * self.thickness_px)
        return x, y


@dataclass
class Sample:
    """One ID: its sections and the cracks of the labeler."""

    id: str
    images: list[Image] = field(default_factory=list)
    cracks: list[Crack] = field(default_factory=list)
    crack_file: Path | None = None
    crack_note: str = ""                    # e.g. cracks without sample frame in the labeler


def load_all(config: dict, report=print) -> list[Sample]:
    """All IDs of input.pores_dir, sorted by ID, with their cracks."""
    pores_dir = resolve(config["input"]["pores_dir"])
    cracks = find_cracks(resolve(config["input"]["cracks_dir"]))
    folders = sorted(p for p in pores_dir.iterdir() if p.is_dir() and p.name.endswith(RESULTS_SUFFIX))
    report(f"{len(folders)} IDs in {pores_dir}, crack files for {len(cracks)} IDs")
    fields_dir = resolve(config["input"]["stress_fields_dir"])

    def one(folder: Path) -> Sample:
        sample = load_sample(folder, fields_dir, config["plot"])
        if sample.id in cracks:
            sample.crack_file, sample.cracks, sample.crack_note = cracks[sample.id]
        report(f"  {sample.id}: {len(sample.images)} images, {len(sample.cracks)} cracks")
        return sample

    with ThreadPoolExecutor() as pool:
        samples = list(pool.map(one, folders))
    for orphan in sorted(set(cracks) - {s.id for s in samples}):
        report(f"  crack file without pore results: {cracks[orphan][0]}")
    return samples


def find_cracks(folder: Path) -> dict[str, tuple[Path, list[Crack], str]]:
    """ID -> (file, cracks, note) of every <ID>_cracks.xlsx below the folder (sheet Cracks)."""
    result = {}
    if not folder.is_dir():
        return result
    for path in sorted(folder.rglob("*" + CRACKS_SUFFIX)):
        if path.name.startswith("~$"):                  # lock file of an open Excel
            continue
        image_id = path.name[:-len(CRACKS_SUFFIX)]
        table = pd.read_excel(path, sheet_name=CRACKS_SHEET)
        placed = table.dropna(subset=["xi", "zeta"])
        cracks = [Crack(f"C{i + 1}", str(row.image), float(row.xi), float(row.zeta))
                  for i, row in enumerate(placed.itertuples())]
        missing = len(table) - len(placed)
        note = f"{missing} crack(s) without sample frame in the labeler (not shown)" if missing else ""
        result[image_id] = (path, cracks, note)
    return result


def load_sample(folder: Path, fields_dir: Path, plot: dict) -> Sample:
    sample = Sample(folder.name[:-len(RESULTS_SUFFIX)])
    for row in _rows(folder / "images.json"):
        try:
            sample.images.append(load_image(folder / row["image"], row, fields_dir, plot))
        except Exception as error:                     # one bad image must not stop the program
            sample.images.append(Image(row["image"], note=f"cannot be read – {type(error).__name__}: {error}"))
    return sample


def load_image(folder: Path, row: dict, fields_dir: Path, plot: dict) -> Image:
    name = row["image"]
    if _empty(row.get("frame_length_px")):
        return Image(name, note="no sample frame found by Pore_Detection – no stress, no A g^q")
    if _empty(row.get("pore_stress")) or _empty(row.get("stress_field")):
        return Image(name, note="pore_index was not run for this image (no stress field)")
    mode = row["pore_stress"]
    if mode not in PORE_STRESS:
        return Image(name, note=f"unknown pore_stress '{mode}'")
    stress = load_field(fields_dir, row["stress_field"])

    labels = _read(folder / "labels.tif", cv2.IMREAD_UNCHANGED)
    flat = np.flatnonzero(labels)
    ids = labels.ravel()[flat]
    rows, cols = np.divmod(flat, labels.shape[1])
    length, thickness = float(row["frame_length_px"]), float(row["frame_thickness_px"])
    angle = math.radians(float(row["frame_angle_deg"]))
    (xy, xx), (zy, zx) = (-math.sin(angle), math.cos(angle)), (-math.cos(angle), -math.sin(angle))
    oy, ox = row["frame_origin_px"]
    dy, dx = rows - oy, cols - ox
    x, z = dx * xx + dy * xy, dx * zx + dy * zy
    xi, zeta = np.clip(x / length, 0, 1), np.clip(z / thickness, 0, 1)
    g = stress.evaluate(xi, zeta)

    pore_ids, index, count = np.unique(ids, return_inverse=True, return_counts=True)
    n = len(pore_ids)
    part = 2 * index + (zeta >= ZONE_BOUNDARY)
    part_area = np.bincount(part, minlength=2 * n).astype(np.float64)
    if mode == "area":
        part_pore, weight, part_g = index, np.ones(len(g)), g
    else:
        used = part_area > 0
        if mode == "centroid":
            area = np.maximum(part_area, 1)
            part_g = stress.evaluate(np.bincount(part, weights=xi, minlength=2 * n) / area,
                                     np.bincount(part, weights=zeta, minlength=2 * n) / area)
        else:
            part_g = np.zeros(2 * n)
            np.maximum.at(part_g, part, g)
        part_pore, weight, part_g = (np.arange(2 * n) // 2)[used], part_area[used], part_g[used]

    margin = plot["picture_margin"] * max(length, thickness)
    scale = min(1.0, plot["picture_max_px"] / (max(length, thickness) + 2 * margin))
    image = Image(name, pore_ids=pore_ids,
                  pore_zeta=np.bincount(index, weights=zeta, minlength=n) / count,
                  part_pore=part_pore, part_weight=weight, part_g=part_g,
                  sample_area_px2=float(row["sample_area_outer_px2"]) + float(row["sample_area_inner_px2"]),
                  scale=scale, margin_px=margin, length_px=length, thickness_px=thickness)
    sx, sz = np.bincount(index, weights=x, minlength=n) / count, np.bincount(index, weights=z, minlength=n) / count
    image.pore_xy = np.column_stack([scale * (sx + margin), scale * (thickness + margin - sz)])

    original, source = _picture_source(folder, row, labels)
    image.picture = _straighten(original, scale, margin, length, thickness, (oy, ox), (xy, xx), (zy, zx))
    image.info = f"field {stress.key} [{stress.unit}], pore_stress {mode}, picture: {source}"
    return image


def _picture_source(folder: Path, row: dict, labels: np.ndarray) -> tuple[np.ndarray, str]:
    """The original image (path in images.json), else a picture made from the masks of the results."""
    for key in ("draw_path", "path"):
        path = row.get(key)
        if not _empty(path) and Path(path).is_file():
            return cv2.cvtColor(_read(Path(path), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB), "original"
    roi = folder / "roi_mask.tif"
    sample = _read(roi, cv2.IMREAD_GRAYSCALE) > 0 if roi.is_file() else np.ones(labels.shape, bool)
    gray = np.where(sample, 205, 250).astype(np.uint8)
    gray[labels > 0] = 30
    return np.dstack([gray] * 3), "masks (original image not found)"


def _straighten(original, scale, margin, length, thickness, origin, x_axis, z_axis) -> np.ndarray:
    """The sample straightened along its frame (as Pore_Detection's plots): outer surface on top."""
    width, height = round(scale * (length + 2 * margin)), round(scale * (thickness + 2 * margin))
    small = cv2.resize(original, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else original
    (xy, xx), (zy, zx) = x_axis, z_axis
    oy, ox = origin
    shift_x = scale * (ox - margin * xx + (thickness + margin) * zx)
    shift_y = scale * (oy - margin * xy + (thickness + margin) * zy)
    matrix = np.array([[xx, -zx, shift_x], [xy, -zy, shift_y]], dtype=np.float64)
    return cv2.warpAffine(small, matrix, (width, height), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))


def _rows(path: Path) -> list[dict]:
    """Column-wise JSON table ({"column": [values]}) -> list of rows."""
    with open(path, encoding="utf-8") as file:
        table = json.load(file)
    return [dict(zip(table, values)) for values in zip(*table.values())]


def _read(path: Path, flags: int) -> np.ndarray:
    """cv2.imread that also works with non-ASCII paths."""
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), flags)
    if image is None:
        raise OSError(f"cannot read {path}")
    return image


def _empty(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))
