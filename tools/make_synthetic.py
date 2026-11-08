"""Synthetic test data with a known q (config.yaml, section synthetic).

Takes a Pore_Detection result folder with several Schliff images (e.g. from its
syntetic_test/generate.py) and makes one sample per image. For every sample a virtual crack origin
(NOT in the Schliff - like the real fracture plane) is drawn: xi, zeta uniform, A0 = factor x largest
Schliff pore (factor log-uniform). It is kept only if it wins at q_true:
    A0 g0^q_true > A_i g_i^q_true   for every Schliff pore      (k_true: null - M1 must find q_true)
or, with k_true = k (M2 model, noisy data): the candidate and all Schliff pores compete, the failing
pore is drawn with probability S^k / sum S^k; a failing Schliff pore becomes the crack origin and is
removed from the Schliff. (Never keep/discard by outcome - that biases every likelihood.)
- with the pore models, stress field and stress model of config.yaml. (Assumption: the pore models do not change the crack origin - true for the
shipped ones.)

    python tools/make_synthetic.py
writes <synthetic.target_dir>/ in the layout of the input folder; then set input.dir to it.
"""

import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from q_fitter.core.config import load_config, project_path                       # noqa: E402
from q_fitter.core.data import PORE_COLUMNS, Sample, _load_images, read_json_table  # noqa: E402
from q_fitter.core.pipeline import apply_pore_models, apply_stress, build        # noqa: E402

BATCH = 2000


def main(config: dict | None = None) -> int:
    config = config or load_config()
    syn = config["synthetic"]
    if not syn["source"]:
        print("synthetic.source is not set in config.yaml", file=sys.stderr)
        return 2
    source = project_path(syn["source"])
    target = project_path(syn["target_dir"])
    input_dir = project_path(config["input"]["dir"])
    if target.resolve() == input_dir.resolve() or input_dir.resolve().is_relative_to(target.resolve()):
        print(f"synthetic.target_dir ({syn['target_dir']}) is the input folder input.dir ({config['input']['dir']}) - "
              f"it would be deleted. Set input.dir to the folder with the stress fields (e.g. daten) for generating.",
              file=sys.stderr)
        return 2
    if target.exists():
        shutil.rmtree(target)
    (target / "poren").mkdir(parents=True)
    (target / "risse").mkdir()
    shutil.copytree(project_path(config["input"]["dir"]) / "spannungsfelder", target / "spannungsfelder")

    pore_models, stress_model, field, _ = build(config)
    rng = np.random.default_rng(syn["seed"])
    q = float(syn["q_true"])
    source_id = source.name[: -len("_results")]
    images, notes = _load_images(source)
    for note in notes:
        print("skip", note)
    rows = read_json_table(source / "images.json").set_index("image")

    excel_rows, n = [], 0
    for image in images.values():
        if image.labels.max() == 0:
            print("skip", image.name, "- no pores")
            continue
        n += 1
        sample_id = f"S{n:03d}"
        new_name = f"{sample_id}_{image.name[len(source_id) + 1:]}"
        folder = target / "poren" / f"{sample_id}_results"
        (folder / new_name).mkdir(parents=True)
        shutil.copyfile(source / image.name / "labels.tif", folder / new_name / "labels.tif")
        row = rows.loc[image.name].to_dict()
        row = {k: None if isinstance(v, float) and np.isnan(v) else v for k, v in row.items()}
        row["image"] = new_name
        (folder / "images.json").write_text(json.dumps({k: [v] for k, v in row.items()}, default=_plain),
                                            encoding="utf-8")

        # Schliff pores through the same chain as in a run, severity at q_true
        sample = _sample_without_crack(sample_id, image)
        apply_pore_models(sample, pore_models)
        apply_stress(sample, field, stress_model)
        pores = sample.pores[sample.pores["kind"] == "pore"]
        g = pores["g"].to_numpy(float)
        ln_pores = np.log(pores["A_um2"].to_numpy(float))[g > 0] + q * np.log(g[g > 0])   # ln severity at q_true
        area_max = float(pores["A_um2"].max())

        if syn["k_true"] is None:
            crack = _draw_crack(rng, syn, area_max, ln_pores, q, sample, field, stress_model)
        else:
            crack = _choose_failing(rng, syn, area_max, pores, q, sample, field, stress_model)
            if crack is not None and crack["labels"]:          # a Schliff pore failed: it is the crack origin now
                labels_file = folder / new_name / "labels.tif"
                labels = cv2.imread(str(labels_file), cv2.IMREAD_UNCHANGED)
                labels[np.isin(labels, crack["labels"])] = 0
                cv2.imwrite(str(labels_file), labels, [cv2.IMWRITE_TIFF_COMPRESSION, cv2.IMWRITE_TIFF_COMPRESSION_PACKBITS])
        if crack is None:
            print(f"{sample_id}: no winning crack origin in {syn['max_tries']} draws - sample dropped")
            shutil.rmtree(folder)
            continue
        crack_folder = target / "risse" / f"{sample_id}_results"
        crack_folder.mkdir()
        (crack_folder / "cracks.json").write_text(json.dumps(
            {"image": [f"{sample_id}_fracture"], "crack_no": [1], "xi": [crack["xi"]], "zeta": [crack["zeta"]],
             "stress_field": [field.key]}), encoding="utf-8")
        excel_rows.append({"ID": sample_id, "A0_um2": crack["A0"], "A0_schliff_um2": None,
                           "bemerkung": f"synthetic, q_true = {q:g}, k_true = {syn['k_true']}, source {image.name}"})
        print(f"{sample_id}: {len(pores)} pores, crack xi={crack['xi']:.3f} zeta={crack['zeta']:.3f} "
              f"A0={crack['A0']:.4g} um2 ({crack['tries']} draws)")

    pd.DataFrame(excel_rows).to_excel(target / "rissausgaenge.xlsx", sheet_name="Rissausgaenge", index=False)
    (target / "wahrheit.json").write_text(json.dumps(
        {"q_true": q, "k_true": syn["k_true"], "stress_field": field.key, "stress_model": stress_model.describe(),
         "pore_models": [m.describe() for m in pore_models], "source": str(source)}, indent=2), encoding="utf-8")
    print(f"{len(excel_rows)} samples -> {target}  (set input.dir: {syn['target_dir']} in config.yaml)")
    return 0


def _sample_without_crack(sample_id, image) -> Sample:
    table = image.label_table()
    xis, zetas = image.to_xi_zeta(table["y"].to_numpy(), table["x"].to_numpy())
    areas = table["count"].to_numpy() * image.pixel_area_um2
    rows = [dict(pore_id="crack", kind="crack", image="", labels=(), A_raw_um2=1.0, A_um2=1.0, xi=0.5, zeta=0.5,
                 excluded=False, note="placeholder")]
    rows += [dict(pore_id=f"{image.name}:{label}", kind="pore", image=image.name, labels=(int(label),),
                  A_raw_um2=float(a), A_um2=float(a), xi=float(x), zeta=float(z), excluded=False, note="")
             for label, a, x, z in zip(table["label"], areas, xis, zetas)]
    return Sample(sample_id, pd.DataFrame(rows, columns=PORE_COLUMNS), {image.name: image}, {})


def _candidates(rng, syn, area_max, n, sample, field, stress_model, q):
    """n virtual crack origins: xi, zeta uniform, A0 = factor x largest Schliff pore; ln severity at q."""
    lo, hi = np.log(syn["area_factor"][0]), np.log(syn["area_factor"][1])
    cand = pd.DataFrame({"kind": "crack", "xi": rng.uniform(*syn["xi"], n), "zeta": rng.uniform(*syn["zeta"], n),
                         "A_um2": area_max * np.exp(rng.uniform(lo, hi, n))})
    cand["A_raw_um2"] = cand["A_um2"]
    cand["g_field"] = field.evaluate(cand["xi"].to_numpy(), cand["zeta"].to_numpy())
    g = np.asarray(stress_model.stress(cand, sample), dtype=float)
    with np.errstate(divide="ignore"):
        ln_s = np.log(cand["A_um2"].to_numpy()) + q * np.log(np.clip(g, 0, None))
    return cand, ln_s


def _choose_failing(rng, syn, area_max, pores, q, sample, field, stress_model):
    """k_true = k (M2 model, noisy data): one virtual candidate + all Schliff pores compete; the pore
    that fails is drawn with probability S^k / sum S^k. If it is a Schliff pore, it becomes the crack
    origin and is removed from the Schliff (labels.tif). No pore is drawn and then thrown away -
    otherwise the data would be selected by the outcome and every likelihood would be biased."""
    k = syn["k_true"]
    cand, ln_c = _candidates(rng, syn, area_max, 1, sample, field, stress_model, q)
    g = pores["g"].to_numpy(float)
    with np.errstate(divide="ignore"):
        ln_p = np.log(pores["A_um2"].to_numpy(float)) + q * np.log(np.clip(g, 0, None))
    ln_all = np.concatenate([ln_c, ln_p]) * k
    weights = np.exp(ln_all - ln_all[np.isfinite(ln_all)].max())
    winner = rng.choice(len(weights), p=weights / weights.sum())
    if winner == 0:
        return {"xi": float(cand["xi"].iloc[0]), "zeta": float(cand["zeta"].iloc[0]), "A0": float(cand["A_um2"].iloc[0]),
                "tries": 1, "labels": ()}
    pore = pores.iloc[winner - 1]
    return {"xi": float(pore["xi"]), "zeta": float(pore["zeta"]), "A0": float(pore["A_um2"]), "tries": 1,
            "labels": tuple(pore["labels"])}


def _draw_crack(rng, syn, area_max, ln_pores, q, sample, field, stress_model):
    """k_true null: a virtual candidate is kept only if it is the most severe pore (M1 holds exactly)."""
    ln_max = float(ln_pores.max()) if len(ln_pores) else -np.inf
    tries = 0
    while tries < syn["max_tries"]:
        k = min(BATCH, syn["max_tries"] - tries)
        cand, ln_s0 = _candidates(rng, syn, area_max, k, sample, field, stress_model, q)
        wins = np.flatnonzero(ln_s0 > ln_max + 1e-9)
        if len(wins):
            i = wins[0]
            return {"xi": float(cand["xi"].iloc[i]), "zeta": float(cand["zeta"].iloc[i]),
                    "A0": float(cand["A_um2"].iloc[i]), "tries": tries + i + 1}
        tries += k
    return None


def _plain(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    raise TypeError(type(value))


if __name__ == "__main__":
    sys.exit(main())
