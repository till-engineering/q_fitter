"""Geometry check (standalone tool: geometry_main.py, explanation: GEOMETRIE.md).

The q fitter works in relative coordinates (xi = x / length, zeta = z / thickness of the sample
frame): a crack of the fracture surface at (xi, zeta) is drawn at the same (xi, zeta) on every
section. That is only right if the frames of the fracture surface (Fatigue_crack_labeler) and of
the sections (Pore_Detection) of an ID describe the same geometry. Here all frames of an ID are
put side by side in absolute units (µm, from the pixel size of the scale bar):

    frames        length, thickness, length / thickness of every frame, deviation from the median
                  of the ID; outline of the sample (roi_mask.tif) in the frame
    cracks        depth of every crack below the outer and above the inner surface on the
                  fracture surface and where the same zeta lands in every section (difference in µm)

Sources (as written by the programs, nothing is computed again):
    sections      <pores_dir>/<ID>_results/images.json (+ <image>/roi_mask.tif); frames set by hand
                  in Pore_Detection are already in images.json
    fractures     <cracks_dir>/**/<ID>_cracks.xlsx; next to it (labeler results folder) images.json,
                  frames.json (frames set by hand, replace the automatic ones) and <image>/roi_mask.tif.
                  Only the Excel: sheet Images (length, thickness, pixel size), no outline
"""

import math
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from .data import CRACKS_SHEET, CRACKS_SUFFIX, RESULTS_SUFFIX, _empty, _read, _rows, resolve

IMAGES_JSON = "images.json"
FRAMES_JSON = "frames.json"
IMAGES_SHEET = "Images"
ROI_MASK = "roi_mask.tif"
OUTLINE_PX = 1.0                # outline simplified to this many px (only drawing)
SECTION, FRACTURE = "section", "fracture"
OFF_SCALE = 3.0                 # a frame this many times larger / smaller than the median: shown as factor,
                                # left out of the absolute plot (wrong scale)


@dataclass
class Frame:
    source: str                 # SECTION (Pore_Detection) | FRACTURE (labeler)
    image: str
    length_px: float
    thickness_px: float
    pixel_size_um: float = math.nan     # nan: no scale
    scale_label: str = ""
    manual: bool = False        # frame set by hand (labeler: frames.json)
    wedge_deg: float = math.nan
    outline: np.ndarray | None = None   # (n, 2) outline of the sample in the frame: x, z in px
    note: str = ""

    @property
    def length_um(self) -> float:
        return self.length_px * self.pixel_size_um

    @property
    def thickness_um(self) -> float:
        return self.thickness_px * self.pixel_size_um

    @property
    def aspect(self) -> float:
        return self.length_px / self.thickness_px


@dataclass
class CrackPoint:
    label: str                  # C1, C2, … numbered over the ID (as in the q fitter)
    image: str                  # fracture image of the labeler
    xi: float
    zeta: float


@dataclass
class IdGeometry:
    id: str
    sections: list[Frame] = field(default_factory=list)
    fractures: list[Frame] = field(default_factory=list)
    cracks: list[CrackPoint] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)       # images without frame, with reason
    crack_file: Path | None = None

    @property
    def frames(self) -> list[Frame]:
        return self.sections + self.fractures

    def median(self) -> tuple[float, float, float]:
        """Median length (µm), thickness (µm) and length / thickness over all frames of the ID."""
        def med(values):
            values = [v for v in values if np.isfinite(v)]
            return float(np.median(values)) if values else math.nan
        return (med(f.length_um for f in self.frames), med(f.thickness_um for f in self.frames),
                med(f.aspect for f in self.frames))


def load_geometry(config: dict) -> list[IdGeometry]:
    """All IDs of the pore and crack folders, sorted by ID."""
    ids: dict[str, IdGeometry] = {}
    pores_dir = resolve(config["input"]["pores_dir"])
    for folder in sorted(p for p in pores_dir.iterdir() if p.is_dir() and p.name.endswith(RESULTS_SUFFIX)):
        geometry = ids.setdefault(folder.name[:-len(RESULTS_SUFFIX)], IdGeometry(folder.name[:-len(RESULTS_SUFFIX)]))
        for row in _rows(folder / IMAGES_JSON):
            frame = _frame(SECTION, row, folder / row["image"] / ROI_MASK)
            if isinstance(frame, str):
                geometry.missing.append(f"section {row['image']}: {frame}")
            else:
                geometry.sections.append(frame)
    cracks_dir = resolve(config["input"]["cracks_dir"])
    for path in sorted(cracks_dir.rglob("*" + CRACKS_SUFFIX)) if cracks_dir.is_dir() else []:
        if path.name.startswith("~$"):
            continue
        image_id = path.name[:-len(CRACKS_SUFFIX)]
        geometry = ids.setdefault(image_id, IdGeometry(image_id))
        geometry.crack_file = path
        _load_fractures(geometry, path)
    return [ids[key] for key in sorted(ids)]


def _load_fractures(geometry: IdGeometry, path: Path) -> None:
    folder = path.parent
    table = pd.read_excel(path, sheet_name=CRACKS_SHEET)
    placed = table.dropna(subset=["xi", "zeta"])
    geometry.cracks = [CrackPoint(f"C{i + 1}", str(row.image), float(row.xi), float(row.zeta))
                       for i, row in enumerate(placed.itertuples())]
    if (folder / IMAGES_JSON).is_file():            # the results folder of the labeler
        manual = {row["image"]: row for row in _rows(folder / FRAMES_JSON)} if (folder / FRAMES_JSON).is_file() else {}
        for row in _rows(folder / IMAGES_JSON):
            hand = manual.get(row["image"])
            if hand is not None:                    # as apply_frames of the labeler
                row = {**row, "frame_origin_px": hand["origin_px"], "frame_angle_deg": hand["angle_deg"],
                       "frame_thickness_px": hand["thickness_px"], "frame_length_px": hand["length_px"],
                       "frame_wedge_deg": None}
            frame = _frame(FRACTURE, row, folder / row["image"] / ROI_MASK)
            if isinstance(frame, str):
                geometry.missing.append(f"fracture {row['image']}: {frame}")
            else:
                frame.manual = hand is not None
                geometry.fractures.append(frame)
        return
    images = pd.read_excel(path, sheet_name=IMAGES_SHEET)    # only the Excel: sizes, no outline
    for row in images.to_dict("records"):
        if _empty(row.get("frame_length_px")) or _empty(row.get("frame_thickness_px")):
            geometry.missing.append(f"fracture {row['image']}: no frame in the labeler")
            continue
        size = row.get("pixel_size_um")
        geometry.fractures.append(Frame(FRACTURE, str(row["image"]), float(row["frame_length_px"]),
                                        float(row["frame_thickness_px"]),
                                        math.nan if _empty(size) else float(size),
                                        note="only the Excel (no images.json): no outline"))


def _frame(source: str, row: dict, mask: Path) -> "Frame | str":
    """Frame of a row of images.json (both programs write the same frame_* columns); else the reason."""
    if _empty(row.get("frame_length_px")) or _empty(row.get("frame_thickness_px")):
        note = row.get("frame_note")
        return f"no sample frame{f' ({note})' if note else ''}"
    size = row.get("pixel_size_um")
    wedge = row.get("frame_wedge_deg")
    frame = Frame(source, row["image"], float(row["frame_length_px"]), float(row["frame_thickness_px"]),
                  math.nan if _empty(size) else float(size), str(row.get("scale_label") or ""),
                  wedge_deg=math.nan if _empty(wedge) else float(wedge))
    origin = row.get("frame_origin_px")
    if isinstance(origin, (list, tuple)) and mask.is_file():
        frame.outline = _outline(mask, origin, float(row["frame_angle_deg"]))
    elif not mask.is_file():
        frame.note = f"no {ROI_MASK}: no outline"
    return frame


def _outline(path: Path, origin, angle_deg: float) -> np.ndarray | None:
    """Outline of the largest object of the mask in the sample frame (x, z in px) – same frame maths
    as the q fitter (data.load_image) and both programs."""
    mask = (_read(path, cv2.IMREAD_GRAYSCALE) > 0).astype(np.uint8)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    points = cv2.approxPolyDP(max(contours, key=cv2.contourArea), OUTLINE_PX, True)[:, 0, :].astype(np.float64)
    angle = math.radians(angle_deg)
    (xy, xx), (zy, zx) = (-math.sin(angle), math.cos(angle)), (-math.cos(angle), -math.sin(angle))
    oy, ox = float(origin[0]), float(origin[1])
    dx, dy = points[:, 0] - ox, points[:, 1] - oy
    return np.column_stack([dx * xx + dy * xy, dx * zx + dy * zy])


# ---------------------------------------------------------------- checks


def frame_table(geometries: list[IdGeometry], tolerance: float, wedge_max: float) -> pd.DataFrame:
    """One row per frame: sizes, deviation from the median of the ID (%), what is conspicuous."""
    rows = []
    for geometry in geometries:
        length, thickness, aspect = geometry.median()
        for frame in geometry.frames:
            d_length = 100 * (frame.length_um / length - 1)
            d_thickness = 100 * (frame.thickness_um / thickness - 1)
            d_aspect = 100 * (frame.aspect / aspect - 1)
            flags = []
            if not np.isfinite(frame.pixel_size_um):
                flags.append("no scale")
            for name, value in (("length", d_length), ("thickness", d_thickness), ("length/thickness", d_aspect)):
                if np.isfinite(value) and abs(value) > tolerance:
                    ratio = 1 + value / 100
                    far = ratio > OFF_SCALE or ratio < 1 / OFF_SCALE
                    flags.append(f"{name} ×{ratio:.3g}" if far else f"{name} {value:+.0f} %")
            if np.isfinite(frame.wedge_deg) and frame.wedge_deg > wedge_max:
                flags.append(f"wedge {frame.wedge_deg:.1f}°")
            rows.append({"ID": geometry.id, "source": frame.source, "image": frame.image,
                         "frame": "by hand" if frame.manual else "automatic",
                         "length_um": frame.length_um, "thickness_um": frame.thickness_um, "length/thickness": frame.aspect,
                         "d_length_%": d_length, "d_thickness_%": d_thickness, "d_aspect_%": d_aspect,
                         "pixel_size_um": frame.pixel_size_um, "scale_label": frame.scale_label,
                         "wedge_deg": frame.wedge_deg, "check": ", ".join(flags) or "ok", "note": frame.note})
    return pd.DataFrame(rows)


def crack_table(geometries: list[IdGeometry]) -> pd.DataFrame:
    """One row per crack and section: where the crack's zeta lands in the section (µm) compared with
    the fracture surface – the error made by working in relative coordinates."""
    rows = []
    for geometry in geometries:
        fractures = {f.image: f for f in geometry.fractures}
        for crack in geometry.cracks:
            fracture = fractures.get(crack.image) or (geometry.fractures[0] if geometry.fractures else None)
            if fracture is None:
                continue
            outer = (1 - crack.zeta) * fracture.thickness_um        # depth below the outer surface
            inner = crack.zeta * fracture.thickness_um              # height above the inner surface
            along = crack.xi * fracture.length_um
            for section in geometry.sections:
                rows.append({"ID": geometry.id, "crack": crack.label, "xi": crack.xi, "zeta": crack.zeta,
                             "section": section.image,
                             "below_outer_fracture_um": outer, "below_outer_section_um": (1 - crack.zeta) * section.thickness_um,
                             "d_below_outer_um": (1 - crack.zeta) * section.thickness_um - outer,
                             "d_above_inner_um": crack.zeta * section.thickness_um - inner,
                             "d_along_um": crack.xi * section.length_um - along})
    return pd.DataFrame(rows)
