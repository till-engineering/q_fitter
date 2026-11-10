"""Check: A g^q of q_fitter == weighted_area_q…_px2 of Pore_Detection (pores.json), for every q of the run."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from q_fitter.data import load_all, load_config, resolve  # noqa: E402

config = load_config()
worst = 0.0
for sample in load_all(config, report=lambda text: None):
    for image in sample.images:
        if not image.ok:
            print(f"{image.name}: skipped – {image.note}")
            continue
        folder = resolve(config["input"]["pores_dir"]) / f"{sample.id}_results" / image.name
        pores = json.loads((folder / "pores.json").read_text(encoding="utf-8"))
        assert list(pores["pore_id"]) == list(image.pore_ids), "pore ids differ"
        for column in [c for c in pores if c.startswith("weighted_area_q")]:
            q = float(column[len("weighted_area_q"):-len("_px2")].replace("_", "."))
            expected = np.array(pores[column], dtype=float)
            error = np.max(np.abs(image.contributions(q) - expected) / np.maximum(np.abs(expected), 1e-12))
            worst = max(worst, error)
        print(f"{image.name}: {len(image.pore_ids)} pores ok")
print(f"largest relative difference: {worst:.2e}")
