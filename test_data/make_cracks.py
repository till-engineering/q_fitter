"""Test only: writes crack reports in the format of the Fatigue_crack_labeler
(input/cracks/<ID>_results/<ID>_cracks.xlsx, sheets Cracks + Images) for the test IDs.
The cracks are placed at chosen pores of the sections (pores.json: xi, zeta), as if the crack
had started there; S004 gets no crack file. Real files come from the labeler."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PORES, CRACKS = ROOT / "input" / "pores", ROOT / "input" / "cracks"
CRACK_COLUMNS = ["image", "crack_no", "x_img_px", "y_img_px", "x_px", "z_px", "xi", "zeta", "x_um", "z_um",
                 "stress", "stress_unit", "stress_field"]
IMAGE_COLUMNS = ["image", "cracks", "frame", "frame_note", "pixel_size_um", "frame_thickness_px", "frame_length_px"]
# ID -> which pore (rank by contribution at this q) of its first section with frame is the crack origin
PLAN = {"S001": [(10, 0)], "S002": [(3, 0), (3, 4)], "S003": [(1, 0)], "S005": [(10, 2)]}

for folder in sorted(PORES.glob("*_results")):
    image_id = folder.name[:-len("_results")]
    if image_id not in PLAN:
        continue
    images = json.loads((folder / "images.json").read_text(encoding="utf-8"))
    with_frame = [name for name, length in zip(images["image"], images["frame_length_px"]) if length]
    if not with_frame:
        print(f"{image_id}: no section with frame, skipped")
        continue
    pores = json.loads((folder / with_frame[0] / "pores.json").read_text(encoding="utf-8"))
    rows = []
    for no, (q, rank) in enumerate(PLAN[image_id], start=1):
        column = "weighted_area_q" + f"{q:g}".replace(".", "_") + "_px2"
        i = int(np.argsort(pores[column])[::-1][rank])
        xi, zeta = pores["xi"][i], pores["zeta"][i]
        rows.append({"image": f"{image_id}_fracture", "crack_no": no, "xi": xi, "zeta": zeta,
                     "stress": abs(2 * zeta - 1), "stress_unit": "-", "stress_field": "bending"})
        print(f"{image_id}: crack {no} at pore {pores['pore_id'][i]} of {with_frame[0]} (xi {xi:.3f}, zeta {zeta:.3f})")
    out = CRACKS / folder.name
    out.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out / f"{image_id}_cracks.xlsx", engine="openpyxl") as writer:
        pd.DataFrame(rows, columns=CRACK_COLUMNS).to_excel(writer, sheet_name="Cracks", index=False)
        pd.DataFrame([{"image": f"{image_id}_fracture", "cracks": len(rows), "frame": "yes"}],
                     columns=IMAGE_COLUMNS).to_excel(writer, sheet_name="Images", index=False)
