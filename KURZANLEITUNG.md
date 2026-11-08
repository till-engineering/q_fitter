# q_fitter – Kurzanleitung

Fittet den Exponenten **q** in S = A·g^q. Alle Einstellungen nur in `config.yaml` (keine Defaults im Code, keine Kommandozeilen-Optionen). Details: `PLAN.md`, eigene Methoden: `METHODEN.md`.

## Installation (einmalig)
```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## Starten
```powershell
.venv\Scripts\python main.py                        # Lauf: daten/ -> ergebnisse/ (wird überschrieben!)
.venv\Scripts\python main.py methods                # verfügbare Methoden auflisten
.venv\Scripts\python tools\test_synthetic.py        # Test mit bekanntem q, ohne Rauschen (M1)
.venv\Scripts\python tools\test_synthetic.py --k 3  # Test mit Rauschen (M2); optional --q 8 --seed 5
.venv\Scripts\python tools\make_synthetic.py        # nur Testdaten erzeugen (Abschnitt synthetic)
```
Test schreibt nach `daten_synth/` bzw. `daten_synth_k<k>/`, setzt dafür intern `exclusion.radius_um = 0` und überschreibt ebenfalls `ergebnisse/`.

## Eingabe (`input.dir`, Standard `daten/`)
| Pfad | Inhalt |
|---|---|
| `poren/<ID>_results/` | Pore_Detection: `images.json` + `<ID>_<bild>/labels.tif` |
| `risse/<ID>_results/cracks.json` | labeler (nur xi, zeta) |
| `spannungsfelder/<name>.yaml` | Formel in xi/zeta, z. B. `bending` = abs(2·zeta−1), `pulsating` = zeta |
| `rissausgaenge.xlsx` | Spalten `ID`, `A0_um2`, `A0_schliff_um2`, `bemerkung` |

## Wichtige Einstellungen (`config.yaml`)
| Schlüssel | Aktuell | Bedeutung |
|---|---|---|
| `input.dir` | `daten` | Eingabeordner (für Tests z. B. `daten_synth`) |
| `input.crack_area_column` | `A0_um2` | A0 aus Bruchfläche; `A0_schliff_um2` zum Vergleich |
| `pore_models` | `[]` | Kette, in Reihenfolge: `merge_clusters` (`gap_um`), `convex_hull`, `ellipse` (`fit: moments\|contour`) |
| `exclusion.radius_um` | `50.0` | Schliffporen näher am Rissausgang ignorieren; 0 = aus |
| `stress.field` | `bending` | Datei in `spannungsfelder/` |
| `stress.model.name` | `field` | g = g_field unverändert (eigene: `stress_models/_template.py`) |
| `fits[m1]` | q 0…30, Schritt 0.05 | `sample_images`: `contradictions\|all\|none`, `image_max_px` |
| `fits[m2]` | q 0…30, Schritt 0.1; k 0.1…1000, 41 Werte | k_min = k_max → k fest |
| `validation.enabled` | `false` | Qualitätskontrolle an/aus (aus = läuft gar nicht) |
| `validation.test_fraction` | `0.2` | Anteil Testproben je Split (80 % fitten, 20 % vorhersagen) |
| `validation.splits` / `seed` | `200` / `1` | Anzahl zufälliger Splits; gleicher Seed = gleiche Splits |
| `output.dir` | `ergebnisse` | Ausgabe, bei jedem Lauf überschrieben |
| `logging.level` | `INFO` | DEBUG / INFO / WARNING / ERROR |
| `synthetic.*` | q_true 6, k_true null, seed 1 | nur für Testdaten; `source: testdaten/synth_results` |

## Ausgabe (`ergebnisse/`)
- `ergebnis.xlsx` – alles in Tabellen (Proben, Übersprungen, M1, Poren)
- `m1_overall.json`, `m1_bounds.png`, `m1_V_q.png` – q-Bereich aus M1
- `m1_contradictions.json`, `m1_pore_map.png`, `m1_samples/<ID>.png` – Widersprüche prüfen
- `m2_overall.json`, `m2_profile.png`, `m2_likelihood.png` – bestes q, k, 95-%-Intervall
- `val_*` (nur mit `validation.enabled`): `val_q_stability.png` (q je Split), `val_hit_rate.png` (Trefferquote vs. Raten), `val_per_sample.png` (Treffer je Probe), `val_split_matrix.png` (Probe × Split: Training/Treffer/Fehler); Tabellen `val_overall`, `val_splits`, `val_predictions`, `val_per_sample`, `val_membership` (welche Probe/Bilder in welchem Split Training oder Test waren)
- `proben.json`, `poren.json`, `uebersprungen.json`, `config_used.yaml`
- `proben.json` → `outside_frame` / `crack_outside_frame`: Poren bzw. Rissausgang außerhalb des Probenrahmens (bekommen die Spannung des nächsten Rands; Rahmen prüfen)
- Jeder Lauf löscht zuerst die Dateien des vorigen Laufs (Liste in `.q_fitter_files.txt`), fremde Dateien bleiben

## Eigene Methoden
Vorlage kopieren (ohne `_` im Dateinamen, sonst nicht geladen): `q_fitter/pore_models/_template.py` bzw. `q_fitter/stress_models/_template.py`, Namen per `@register` vergeben, in `config.yaml` eintragen. Siehe `METHODEN.md`.
