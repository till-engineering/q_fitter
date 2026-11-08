# Eigene Methoden schreiben

Es gibt zwei Stellen, an denen du A und g veränderst:

```
Rohdaten ─► [ Porenmodelle ] ─► g_feld = Feld(xi, zeta) ─► [ Spannungsmodell ] ─► M1
              Kette, ändern A_um2,                            genau eins,
              xi, zeta, fassen zusammen                       macht aus g_field das g
```

- **Porenmodell**: alles, was die Pore selbst betrifft, also Fläche, Lage, Zusammenfassen, Form.
  Es läuft **vor** der Spannung. Verschiebst du eine Pore, wird ihre Spannung danach an der neuen
  Stelle berechnet.
- **Spannungsmodell**: alles, was die Spannung betrifft, z. B. Kerbwirkung, Randschicht oder Härte.
  Es bekommt g_feld fertig und gibt g zurück.

Eine neue Methode ist **eine neue Datei**. Am übrigen Code änderst du nichts.

---

## 1. In drei Schritten zur eigenen Methode

1. Vorlage kopieren:
   - Porenmodell: `q_fitter/pore_models/_template.py` → `q_fitter/pore_models/mein_modell.py`
   - Spannungsmodell: `q_fitter/stress_models/_template.py` → `q_fitter/stress_models/mein_modell.py`

   (Dateien, die mit `_` beginnen, werden nicht geladen. Deshalb ist die Vorlage nie aktiv.)
2. In der Datei den Namen in `@register("...")` ändern, `params` anpassen und die Rechnung schreiben.
3. In `config.yaml` auswählen und Parameter eintragen. Mit `python main.py methods` siehst du, ob die
   Methode gefunden wurde.

---

## 2. Die Porentabelle `pores`

Beide Modellarten bekommen die Porentabelle **einer Probe** (pandas DataFrame). Eine Zeile ist eine
Pore. **Der Rissausgang ist auch eine Zeile** (`kind == "crack"`).

| Spalte | Inhalt | ändern? |
|---|---|---|
| `kind` | `"crack"` = Rissausgang, `"pore"` = Schliffpore | – |
| `pore_id` | `"crack"` oder `"<Bild>:<Label>"` | – |
| `image` | Schliffbild der Pore (`""` beim Rissausgang) | – |
| `labels` | Tupel der Porennummern in `labels.tif` (mehrere nach dem Zusammenfassen) | beim Zusammenfassen |
| `A_raw_um2` | Fläche wie eingelesen (Pixel × Pixelgröße² bzw. A0 aus der Excel) | nein |
| `A_um2` | **Fläche, die M1 benutzt** | **ja** (Porenmodell) |
| `xi`, `zeta` | **Lage** im Proben-KOS, 0..1 (ζ = 1 außen) | **ja** (Porenmodell) |
| `excluded` | `True` = zählt nicht als Konkurrent | ja |
| `note` | Text, steht im Ergebnis | ja |
| `dist_um` | Abstand zum Rissausgang (nach den Porenmodellen ergänzt) | – |
| `g_field` | Spannungsfeld an (xi, zeta) – **nur im Spannungsmodell vorhanden** | – |
| `g` | **Spannung, die M1 benutzt** – Rückgabe des Spannungsmodells | – |

Zugriff in pandas, kurz:

```python
poren = pores["kind"] == "pore"                  # Maske: nur Schliffporen
pores.loc[poren, "A_um2"] *= 1.5                 # Fläche aller Schliffporen ändern
a = pores["A_um2"].to_numpy()                    # als numpy-Array
for i, p in pores[poren].iterrows():             # Pore für Pore
    pores.at[i, "A_um2"] = ...
```

---

## 3. Rohdaten: `sample`

Jede Methode bekommt zusätzlich `sample`, also alles zu der Probe:

| Ausdruck | Inhalt |
|---|---|
| `sample.id` | ID der Probe |
| `sample.crack` | Zeile des Rissausgangs (`sample.crack["A_um2"]`, `["xi"]`, `["zeta"]`) |
| `sample.excel` | die Zeile aus `rissausgaenge.xlsx` als dict, **auch eigene Spalten** (`sample.excel["Haerte_HBW"]`) |
| `sample.pixels(p)` | `(y, x)`: alle Bildpixel einer Porenzeile `p` |
| `sample.images[p["image"]]` | das Schliffbild der Pore (siehe unten) |

Ein Schliffbild `image = sample.images[name]`:

| Ausdruck | Inhalt |
|---|---|
| `image.labels` | das ganze `labels.tif` (numpy, 0 = keine Pore, n = Pore n) |
| `image.pixel_size_um`, `image.pixel_area_um2` | Maßstab |
| `image.thickness_um`, `image.length_um` | Probendicke und -länge in µm |
| `image.to_xi_zeta(y, x)` | Bildpixel → (ξ, ζ) |
| `image.to_image_px(xi, zeta)` | (ξ, ζ) → Bildpixel (y, x) |

Beispiel: Pixel einer Pore in µm-Koordinaten des Proben-KOS:

```python
y, x = sample.pixels(p)
image = sample.images[p["image"]]
xi, zeta = image.to_xi_zeta(y, x)
z_um = zeta * image.thickness_um        # Höhe jedes Pixels in µm
```

---

## 4. Beispiel Porenmodell

```python
# q_fitter/pore_models/aufschlag.py
import pandas as pd
from q_fitter import PoreModel, Sample, register


@register("aufschlag")
class Aufschlag(PoreModel):
    """Schliffporen-Fläche × Faktor (z. B. weil der Schliff die Poren zu klein anschneidet)."""

    params = {"faktor": "Flächenfaktor für Schliffporen"}

    def apply(self, pores: pd.DataFrame, sample: Sample) -> pd.DataFrame:
        poren = pores["kind"] == "pore"
        pores.loc[poren, "A_um2"] *= self.faktor          # Parameter aus der Config: self.<name>
        return pores
```

```yaml
pore_models:
  - name: aufschlag
    faktor: 1.5
```

Regeln für Porenmodelle:
- Die Tabelle zurückgeben. Du bekommst eine Kopie und darfst sie frei ändern.
- **Genau eine** Zeile mit `kind == "crack"` muss bleiben.
- Zusammenfassen bzw. Aufteilen: einfach eine Tabelle mit anderen Zeilen zurückgeben, siehe
  `merge_clusters.py`.
- Ein Formmodell (Ellipse, Hülle) rechnet aus `sample.pixels(p)` und überschreibt `A_um2`. Was ein
  früheres Modell an `A_um2` geändert hat, geht dabei verloren. Die **Reihenfolge in der Kette zählt**.

---

## 5. Beispiel Spannungsmodell

```python
# q_fitter/stress_models/kerbe.py
import numpy as np
import pandas as pd
from q_fitter import Sample, StressModel, register


@register("kerbe")
class Kerbe(StressModel):
    """g = g_feld × K, K fällt von k_rand an der Außenseite auf 1 im Inneren."""

    params = {"k_rand": "Kerbfaktor direkt an der Oberfläche",
              "abkling_um": "Abklinglänge in µm"}

    def stress(self, pores: pd.DataFrame, sample: Sample) -> np.ndarray:
        dicke_um = next(iter(sample.images.values())).thickness_um
        tiefe_um = (1 - pores["zeta"].to_numpy()) * dicke_um         # Abstand zur Außenseite
        k = 1 + (self.k_rand - 1) * np.exp(-tiefe_um / self.abkling_um)
        return pores["g_field"].to_numpy() * k                        # ein g je Zeile, gleiche Reihenfolge
```

```yaml
stress:
  field: bending
  model:
    name: kerbe
    k_rand: 1.5
    abkling_um: 200
```

Regeln für Spannungsmodelle:
- Ein `g` je Zeile zurückgeben, als numpy-Array in derselben Reihenfolge.
- Der **Rissausgang läuft durch dieselbe Formel** wie die Schliffporen. Unterscheiden kannst du die
  beiden über `pores["kind"]`, aber überlege dir gut, ob das physikalisch Sinn ergibt.
- **Was bei M1 wirkt:** Nur Terme, die sich zwischen den Poren unterscheiden (Lage, Größe). Ein
  Faktor, der für alle Poren gleich ist, kürzt sich in s = ln(g0/gi) heraus.
- g ≤ 0 bedeutet "keine Spannung": Eine solche Pore ist nie ein Konkurrent.

---

## 6. Prüfen, ob die Methode stimmt

1. `python main.py methods`: Taucht sie in der Liste auf?
2. In `ergebnisse/poren.json` bzw. im Blatt **Poren** stehen für jede Pore `A_raw_um2` und `A_um2`
   sowie `g_field` und `g` nebeneinander. Dort siehst du direkt, was deine Methode verändert hat.
3. Gegenprobe mit bekanntem q: In `config.yaml` deine Methode einstellen, dann
   `python tools/make_synthetic.py` ausführen und `input.dir: daten_synth` setzen (Ausschlussradius 0).
   Danach `python main.py`. Das `q_true` muss im M1-Bereich liegen.
