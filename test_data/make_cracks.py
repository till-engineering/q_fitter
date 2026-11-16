"""Test only: writes crack results in the format of the Fatigue_crack_labeler for the test IDs:
input/cracks/<ID>_results/ with
    <ID>_cracks.xlsx            sheets Cracks + Images (frame of the fracture surface, pixel size)
    images.json                 automatic frame of the pre-run (column-wise, as the labeler)
    frames.json                 frame set by hand (only S005: replaces the automatic one)
    <ID>_fracture/roi_mask.tif  outline of the fracture surface (rounded rectangle)
The cracks are placed at chosen pores of the sections (pores.json: xi, zeta), as if the crack had
started there. The fracture surface is the first section with frame, scaled by FRACTURE_SCALE
(length, thickness), so the geometry check (geometry_main.py) has something to find; its pixel size
is that of the section. S004 gets no crack file. Real files come from the labeler.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PORES, CRACKS = ROOT / "input" / "pores", ROOT / "input" / "cracks"
CRACK_COLUMNS = ["image", "crack_no", "x_img_px", "y_img_px", "x_px", "z_px", "xi", "zeta", "x_um", "z_um",
                 "stress", "stress_unit", "stress_field"]
IMAGE_COLUMNS = ["image", "cracks", "frame", "frame_note", "pixel_size_um", "frame_thickness_px", "frame_length_px"]
# ID -> which pore (rank by contribution at this q) of its first section with frame is the crack origin
PLAN = {"S001": [(10, 0)], "S002": [(3, 0), (3, 4)], "S003": [(1, 0)], "S005": [(10, 2)]}
# ID -> fracture surface = first section x (length, thickness) factor
FRACTURE_SCALE = {"S001": (1.0, 1.0), "S002": (1.03, 1.05), "S003": (1.0, 1.25), "S005": (0.96, 0.9)}
# ID -> frame set by hand in the labeler: automatic frame x (length, thickness) factor -> the frame used
MANUAL = {"S005": (1.04, 1.06)}
BORDER_PX = 100                     # embedding around the fracture surface in its picture
CORNER = 0.08                       # corner radius of the outline, share of the thickness


def column_table(rows: list[dict]) -> dict:
    return {key: [row[key] for row in rows] for key in rows[0]}


def write_json(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(column_table(rows), ensure_ascii=False, indent=1), encoding="utf-8")


def rounded_mask(height, width, left, top, length, thickness) -> np.ndarray:
    mask = np.zeros((height, width), np.uint8)
    r = int(CORNER * thickness)
    x0, y0, x1, y1 = int(left), int(top), int(left + length), int(top + thickness)
    cv2.rectangle(mask, (x0 + r, y0), (x1 - r, y1), 255, -1)
    cv2.rectangle(mask, (x0, y0 + r), (x1, y1 - r), 255, -1)
    for cx, cy in ((x0 + r, y0 + r), (x1 - r, y0 + r), (x0 + r, y1 - r), (x1 - r, y1 - r)):
        cv2.circle(mask, (cx, cy), r, 255, -1)
    return mask


for folder in sorted(PORES.glob("*_results")):
    image_id = folder.name[:-len("_results")]
    if image_id not in PLAN:
        continue
    images = json.loads((folder / "images.json").read_text(encoding="utf-8"))
    with_frame = [i for i, length in enumerate(images["frame_length_px"]) if length]
    if not with_frame:
        print(f"{image_id}: no section with frame, skipped")
        continue
    s = with_frame[0]
    section = images["image"][s]
    pixel_size = images["pixel_size_um"][s]
    scale_l, scale_t = FRACTURE_SCALE[image_id]
    auto_l, auto_t = images["frame_length_px"][s] * scale_l, images["frame_thickness_px"][s] * scale_t
    fracture = f"{image_id}_fracture"
    width, height = int(auto_l * 1.1 + 2 * BORDER_PX), int(auto_t * 1.1 + 2 * BORDER_PX)
    origin = [float(BORDER_PX + auto_t), float(BORDER_PX)]          # (y, x): inner (bottom) edge, left edge
    auto = {"image": fracture, "path": None, "height_px": height, "width_px": width, "pixel_size_um": pixel_size,
            "scale_label": images["scale_label"][s], "scale_bar_px": None, "scale_box_px": None, "scale_note": "",
            "frame_origin_px": origin, "frame_angle_deg": 0.0, "frame_thickness_px": auto_t,
            "frame_thickness_um": auto_t * pixel_size, "frame_length_px": auto_l,
            "frame_length_um": auto_l * pixel_size, "frame_wedge_deg": 0.1, "frame_note": ""}
    used_l, used_t, used_origin = auto_l, auto_t, origin
    out = CRACKS / folder.name
    (out / fracture).mkdir(parents=True, exist_ok=True)
    write_json(out / "images.json", [auto])
    (out / "frames.json").unlink(missing_ok=True)
    if image_id in MANUAL:
        used_l, used_t = auto_l * MANUAL[image_id][0], auto_t * MANUAL[image_id][1]
        used_origin = [float(BORDER_PX + used_t), float(BORDER_PX)]
        write_json(out / "frames.json", [{"image": fracture, "origin_px": used_origin, "angle_deg": 0.0,
                                          "thickness_px": used_t, "length_px": used_l,
                                          "clicks": [[0, 0], [1, 0], [0, 1], [0, 0], [1, 0]]}])
    # the real outline of the fracture surface: the frame used (a frame set by hand fits it better)
    mask = rounded_mask(height, width, BORDER_PX, BORDER_PX, used_l, used_t)
    ok, data = cv2.imencode(".tif", mask)
    data.tofile(str(out / fracture / "roi_mask.tif"))

    pores = json.loads((folder / section / "pores.json").read_text(encoding="utf-8"))
    rows = []
    for no, (q, rank) in enumerate(PLAN[image_id], start=1):
        column = "weighted_area_q" + f"{q:g}".replace(".", "_") + "_px2"
        i = int(np.argsort(pores[column])[::-1][rank])
        xi, zeta = pores["xi"][i], pores["zeta"][i]
        x_px, z_px = xi * used_l, zeta * used_t
        rows.append({"image": fracture, "crack_no": no, "x_img_px": round(used_origin[1] + x_px, 2),
                     "y_img_px": round(used_origin[0] - z_px, 2), "x_px": x_px, "z_px": z_px, "xi": xi,
                     "zeta": zeta, "x_um": x_px * pixel_size, "z_um": z_px * pixel_size,
                     "stress": abs(2 * zeta - 1), "stress_unit": "-", "stress_field": "bending"})
        print(f"{image_id}: crack {no} at pore {pores['pore_id'][i]} of {section} (xi {xi:.3f}, zeta {zeta:.3f})")
    summary = [{"image": fracture, "cracks": len(rows), "frame": "yes", "frame_note": "", "pixel_size_um": pixel_size,
                "frame_thickness_px": used_t, "frame_length_px": used_l}]
    with pd.ExcelWriter(out / f"{image_id}_cracks.xlsx", engine="openpyxl") as writer:
        pd.DataFrame(rows, columns=CRACK_COLUMNS).to_excel(writer, sheet_name="Cracks", index=False)
        pd.DataFrame(summary, columns=IMAGE_COLUMNS).to_excel(writer, sheet_name="Images", index=False)
    note = f", frame set by hand x{MANUAL[image_id]}" if image_id in MANUAL else ""
    print(f"{image_id}: fracture surface = {section} x {FRACTURE_SCALE[image_id]}{note}")
