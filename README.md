# q fitter

Shows for every ID and every section the **critical pores** (Pareto of the contributions A·g^q
to Φ_q, as `critical_pores` of Pore_Detection) next to the straightened sample, with **one q
slider for all IDs**. The crack origins of the Fatigue_crack_labeler are drawn on the samples
as cyan rings with a cross (C1, C2, …) at their ξ / ζ.

## Installation (once)

```powershell
.venv\Scripts\python -m pip install -r requirements.txt
```

## Start

```powershell
.venv\Scripts\python main.py
```

All settings are in `config.yaml` (q limits, step, start value, number of bars, plot size).

## Input (drag the program outputs in)

```
input/
├── pores/            Pore_Detection: the <ID>_results folders as written by the program
│   ├── S001_results/ images.json + <ID>_<image>/labels.tif (+ the rest, not needed)
│   └── …
├── cracks/           Fatigue_crack_labeler: the <ID>_results folders (or only <ID>_cracks.xlsx)
│   ├── S001_results/S001_cracks.xlsx      sheet "Cracks": xi, zeta per crack
│   └── …
└── stress_fields/    stress field YAMLs (same files as in Pore_Detection/stress_fields)
```

- The ID connects both: `S001_results` (pores) ↔ `S001_cracks.xlsx` (cracks).
- Every crack of an ID is drawn on every section of the ID (at the same ξ, ζ).
- A g^q is computed for any q from `labels.tif`, the sample frame and the stress field, with the
  `pore_stress` and stress field of the run (images.json) – identical to Pore_Detection
  (checked: `test_data/check_contributions.py`).
- **Pore stress** (switch in the window, start value `stress.pore_stress` in `config.yaml`): how the
  stress of a pore is taken – `run` (as in the Pore_Detection run), `area` (every pixel with its own
  stress), `centroid` (stress at the centroid, per zone), `max` (highest stress, per zone) or `mean`
  (stress averaged over the whole pore; only in q fitter, not in Pore_Detection).
- The sample picture is taken from the original image (path in images.json). If it is not
  found (other computer), a picture is made from the masks of the results (pores dark).
- Sections without sample frame or without pore_index are listed with the reason.

## Test data

`input/` contains a test run: synthetic images of Pore_Detection (`test_data/source_images/`,
5 IDs), processed by Pore_Detection (`test_data/run_pore_detection.py`), and crack reports in the
format of the labeler (`test_data/make_cracks.py`, cracks placed on chosen pores; S004 has no
crack file). Replace the contents of `input/` with real data.
