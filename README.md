# q fitter

Shows for every ID **one plot**: on the left a compact Pareto of the **critical pores** of every
section of the ID, **overlaid** (contributions A·g^q to Φ_q, as `critical_pores` of Pore_Detection),
on the right the straightened pictures of **all sections of the ID**, as large as the window
allows, with **one q slider for all IDs**. All crack origins of the ID from the
Fatigue_crack_labeler are drawn on every section as cyan rings with a cross (C1, C2, …) at their ξ / ζ.

- Sections are lettered A, B, C, … (colour = section, also the frame of its picture).
- Pareto: x = rank of the pore **in its own section**. At every rank one bar per section side by
  side, always in the order A, B, C, … (at rank 1 the largest pore of A, of B, of C). A bar is the
  share of the pore in Σ A g^q of **its** section; inner-zone pores hatched; one cumulative line
  per section.
- On every picture its `numbered` largest pores are numbered with their rank (= position on the x
  axis; `picture_labels: pore` shows the pore number of Pore_Detection instead); the `red_top` largest (default 5) in red.
- Pareto title: Φ_q of the ID = Σ A g^q of all sections / Σ sample area of all sections. Below each
  picture: Φ_q of the section, top 5 / top N share, field, picture source, pore stress method.
- Layout: the pictures get the room first (grid chosen automatically, at most `max_height_ratio`
  of the visible height), the Pareto takes the rest (at least `pareto_min_px` / `pareto_min_share`).

## Installation (once)

```powershell
.venv\Scripts\python -m pip install -r requirements.txt
```

## Start

```powershell
.venv\Scripts\python main.py
```

All settings are in `config.yaml` (q limits, step, start value, number of bars, plot size).

Layout check without window: `.venv\Scripts\python test_data\render_plots.py [q] [method]` renders
every ID at three widths to `test_data/rendered/` and reports cut-off or overlapping parts.

## Fit of q (panel "Fit q", buttons "q → bound" and "q → q̂")

One q for all IDs from the **stress at the crack origins** (not their position, not the size of the
origin pore): for every crack u = share of Σ A g^q of its ID that is loaded higher than the crack
origin.

- **Bound (main result):** the smallest q at which the critical pores lie above the crack origins,
  i.e. u ≥ `fit.bound.share` (90 %) for every crack (or the least loaded crack of every ID,
  `fit.bound.reference`), for `fit.bound.cracks` of them (100 %).
- **Typical q̂:** the q where the mean of u is 0.5 (u is uniform if the model with q is right), with
  a 95 % range.

The panel shows both over q, and at the q of the slider how Σ A g^q is spread over the stress
together with the stresses of the crack origins. Every crack on the pictures shows its u (green
background: covered by the bound). Maths,
interpretation and limits: [Q_FIT.md](Q_FIT.md) (German); step-by-step explanation with figures, how
to read the plots and what follows from them: [Q_FIT_ERKLAERT.md](Q_FIT_ERKLAERT.md) (German; figures
made by `docs\make_figures.py`). Settings: `fit` in `config.yaml`.
Check with synthetic cracks of known q: `.venv\Scripts\python test_data\check_fit.py [method]`.

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
  The methods with their maths: [PORENSPANNUNG.md](PORENSPANNUNG.md).
- The sample picture is taken from the original image (path in images.json). If it is not
  found (other computer), a picture is made from the masks of the results (pores dark).
- Sections without sample frame or without pore_index are listed with the reason.

## Geometry check (standalone)

`.venv\Scripts\python geometry_main.py` opens its own window: for every ID the sample frames of
all fracture surfaces (labeler) and all sections (Pore_Detection) side by side in µm and in
relative ξ / ζ, with the outlines of the samples, the deviations from the median of the ID and the
error in µm of every crack position caused by working in relative coordinates. "Save report"
writes `output/geometry/`. For the outlines of the fracture surfaces drag the whole labeler
`<ID>_results` folder into `input/cracks` (images.json, frames.json, `<image>/roi_mask.tif`), not only
the Excel. Explanation (German): [GEOMETRIE.md](GEOMETRIE.md). Settings: `geometry` in `config.yaml`.

## Test data

`input/` contains a test run: synthetic images of Pore_Detection (`test_data/source_images/`,
5 IDs), processed by Pore_Detection (`test_data/run_pore_detection.py`), and crack reports in the
format of the labeler (`test_data/make_cracks.py`, cracks placed on chosen pores, with the frame and
outline of a fracture surface that differs on purpose from the sections for the geometry check, S005
with a frame set by hand; S004 has no crack file). S001–S005 have 2–3 sections each (S004_synth_010 without sample frame); in S002_synth_009
Pore_Detection found a wrong frame (length 2169 px, origin outside the image), so its picture is
off. Replace the contents of `input/` with real data.
