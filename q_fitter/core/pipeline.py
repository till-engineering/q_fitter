"""The run: read -> pore models -> exclusion -> g_field -> stress model -> fits -> output.

    1. read every ID (labels.tif + images.json, cracks.json, rissausgaenge.xlsx)
    2. pore model chain              (config: pore_models)      changes A_um2, xi, zeta, merges pores
    3. exclusion near crack origin   (config: exclusion)        Schliff pores closer than radius_um
    4. g_field = stress field(xi, zeta)  (config: stress.field)
    5. stress model -> g             (config: stress.model)
    6. fits (M1, ...)                (config: fits)
    6b. quality control              (config: validation)       random train/test splits, optional
    7. output                        (config: output.dir)
"""

import logging
import time

import yaml

import numpy as np
import pandas as pd

from . import output
from .config import load_config, project_path
from .data import PORE_COLUMNS, Sample, load_samples
from .registry import create
from .stress_field import StressField, load_field
from .validation import validate

log = logging.getLogger("q_fitter")


def build(config: dict):
    """The methods and the stress field selected in the config."""
    pore_models = [create("pore_model", entry) for entry in config["pore_models"] or []]
    stress_model = create("stress_model", config["stress"]["model"])
    field = load_field(project_path(config["input"]["dir"]) / "spannungsfelder", config["stress"]["field"])
    fits = [create("fit", entry) for entry in config["fits"] or []]
    return pore_models, stress_model, field, fits


def apply_pore_models(sample: Sample, pore_models) -> None:
    for model in pore_models:
        pores = model.apply(sample.pores.copy(), sample)
        missing = [c for c in PORE_COLUMNS if c not in pores.columns]
        if missing:
            raise ValueError(f"pore model {model.name} removed the columns {missing}")
        if (pores["kind"] == "crack").sum() != 1:
            raise ValueError(f"pore model {model.name}: the table must keep exactly one crack origin")
        sample.pores = pores.reset_index(drop=True)


def apply_exclusion(sample: Sample, radius_um: float) -> None:
    """dist_um = distance of the nearest pixel of a Schliff pore to the crack origin (mapped into the
    Schliff image by xi, zeta); pores closer than radius_um are excluded."""
    pores = sample.pores
    crack = sample.crack
    distances = {name: image.min_distance_um(crack["xi"], crack["zeta"]) for name, image in sample.images.items()}
    dist = np.full(len(pores), np.nan)
    for i, pore in enumerate(pores.itertuples()):
        if pore.kind == "pore" and pore.labels:
            dist[i] = min(distances[pore.image].get(label, np.inf) for label in pore.labels)
    pores["dist_um"] = dist
    near = (pores["kind"] == "pore") & (pores["dist_um"] < radius_um) & ~pores["excluded"]
    pores.loc[near, "excluded"] = True
    pores.loc[near, "note"] = _append(pores.loc[near, "note"], f"closer than {radius_um} um to the crack origin")


FRAME_TOLERANCE = 0.01      # xi, zeta this far outside 0..1 count as outside the sample frame


def apply_stress(sample: Sample, field: StressField, stress_model) -> None:
    """g_field = stress field at (xi, zeta), then the stress model -> g. A pore (or crack origin)
    outside the sample frame keeps its row but gets the stress of the nearest edge - it is marked
    (column outside_frame, note) and counted per sample, so a badly placed frame is seen at once."""
    pores = sample.pores
    xi, zeta = pores["xi"].to_numpy(float), pores["zeta"].to_numpy(float)
    outside = ((xi < -FRAME_TOLERANCE) | (xi > 1 + FRAME_TOLERANCE) |
               (zeta < -FRAME_TOLERANCE) | (zeta > 1 + FRAME_TOLERANCE))
    pores["outside_frame"] = outside
    if outside.any():
        notes = [f"outside the sample frame (xi = {x:.3g}, zeta = {z:.3g}) - stress of the nearest edge"
                 for x, z in zip(xi[outside], zeta[outside])]
        pores.loc[outside, "note"] = [n + "; " + t if n else t for n, t in zip(pores.loc[outside, "note"], notes)]
        n_pores = int((outside & (pores["kind"] == "pore").to_numpy()).sum())
        what = [f"{n_pores} Schliff pore{'s' if n_pores > 1 else ''}"] if n_pores else []
        if outside[(pores["kind"] == "crack").to_numpy()].any():
            what.insert(0, "the crack origin")
        log.warning("%s: %s outside the sample frame - check the frame (images.json / labeler)",
                    sample.id, " and ".join(what))
    pores["g_field"] = field.evaluate(xi, zeta)
    g = np.asarray(stress_model.stress(pores, sample), dtype=np.float64)
    if g.shape != (len(pores),):
        raise ValueError(f"stress model {stress_model.name} returned {g.shape}, expected ({len(pores)},)")
    pores["g"] = g


def run(config: dict | None = None):
    config = config or load_config()
    logging.basicConfig(level=config["logging"]["level"], format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")
    start = time.perf_counter()
    pore_models, stress_model, field, fits = build(config)
    log.info("stress field %s, stress model %s, pore models: %s", field.describe(), stress_model.describe(),
             " -> ".join(m.describe() for m in pore_models) or "none")

    input_dir = project_path(config["input"]["dir"])
    samples, skipped = load_samples(input_dir, config["input"]["crack_area_column"])
    log.info("%d samples read, %d skipped", len(samples), len(skipped))
    for sample in samples:
        apply_pore_models(sample, pore_models)
        apply_exclusion(sample, float(config["exclusion"]["radius_um"]))
        apply_stress(sample, field, stress_model)

    results = [fit.fit(samples) for fit in fits]
    validation = validate(config["validation"], samples, fits, results)
    if validation is not None:
        results.append(validation)

    out_dir = project_path(config["output"]["dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    output.clean(out_dir)                         # files of the previous run
    (out_dir / "config_used.yaml").write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
                                             encoding="utf-8")   # the settings really used
    output.write(out_dir, samples, skipped, results, field)
    log.info("done in %.1f s -> %s", time.perf_counter() - start, out_dir)
    return out_dir


def _append(notes: pd.Series, text: str) -> pd.Series:
    return notes.where(notes == "", notes + "; ") + text
