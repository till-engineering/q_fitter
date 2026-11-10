# Porenspannung: wie die Spannung einer Pore in A·g^q eingeht

Dieses Dokument beschreibt, wie der q fitter für jede Pore einen Beitrag $B_i$ zum Porenindex
$\Phi_q$ berechnet, und die vier umschaltbaren Methoden (`area`, `centroid`, `max`, `mean`).
Die Auswahl erfolgt im Fenster („Pore stress“), der Startwert steht in `config.yaml` unter
`stress.pore_stress`. Code: `q_fitter/data.py` (`load_image`, `_parts`, `Image.contributions`).

**Alles gilt pro Schnitt** (ein Unterordner `<ID>_results/<Bild>/`). Über die Bilder einer ID wird
nichts zusammengefasst; die ID-Zusammenfassung von Pore_Detection (`id_values.json`,
`<ID>_results.xlsx`, `plots/` auf ID-Ebene) wird nicht gelesen.

---

## 1. Bezeichnungen

| Zeichen | Bedeutung |
|---|---|
| $i$ | Pore (Nummer aus `labels.tif`) |
| $p$ | Pixel |
| $P_i$ | Menge der Pixel von Pore $i$ |
| $A_i = \lvert P_i \rvert \cdot 1\,\mathrm{px}^2$ | Fläche von Pore $i$ |
| $\xi_p,\ \zeta_p$ | Lage des Pixels im Probenrahmen: $\xi$ entlang der Probe, $\zeta$ über die Dicke ($0$ innen, $1$ außen) |
| $g(\xi,\zeta)$ | relative Spannung aus dem Spannungsfeld |
| $g_p = g(\xi_p, \zeta_p)$ | Spannung am Pixel $p$ |
| $q$ | Exponent (Schieberegler) |
| $A_\mathrm{Probe}$ | Probenfläche des Schnitts (`sample_area_outer_px2 + sample_area_inner_px2`) |

## 2. Von der Pore zur Spannung am Pixel

**Lage im Probenrahmen.** Für jedes Porenpixel (Zeile $r$, Spalte $c$) wird mit Rahmenursprung
$(o_y, o_x)$, Rahmenwinkel und den Achsen $\mathbf{e}_x$, $\mathbf{e}_z$ gerechnet:

$$
x_p = (c - o_x)\,e_{x,x} + (r - o_y)\,e_{x,y}, \qquad
z_p = (c - o_x)\,e_{z,x} + (r - o_y)\,e_{z,y}
$$

$$
\xi_p = \mathrm{clip}\!\left(\frac{x_p}{L},\,0,\,1\right), \qquad
\zeta_p = \mathrm{clip}\!\left(\frac{z_p}{T},\,0,\,1\right)
$$

mit Rahmenlänge $L$ und Rahmendicke $T$ (aus `images.json`).

**Spannungsfeld.** $g(\xi,\zeta)$ ist eine Formel aus `input/stress_fields/<feld>.yaml`, z. B.

| Feld | Formel | Verlauf |
|---|---|---|
| `bending` | $g = \lvert 2\zeta - 1 \rvert$ | V-förmig: 1 an beiden Oberflächen, 0 in der Mitte |
| `pulsating` | $g = \zeta$ | linear: 0 innen, 1 außen |

Welches Feld ein Schnitt verwendet, steht in seiner Zeile in `images.json` (`stress_field`).

## 3. Zonen (innere / äußere Hälfte)

Die Probe ist über die Dicke an $\zeta = 0{,}5$ (`ZONE_BOUNDARY`) in zwei Hälften geteilt. Jede
Pore wird pixelgenau in höchstens zwei Teile zerlegt:

$$
P_i^\mathrm{in} = \{\, p \in P_i : \zeta_p < 0{,}5 \,\}, \qquad
P_i^\mathrm{out} = \{\, p \in P_i : \zeta_p \ge 0{,}5 \,\}
$$

Liegt eine Pore ganz in einer Hälfte, ist der andere Teil leer und fällt weg. Die Teilung wirkt nur
bei `centroid` und `max` (wie in Pore_Detection). `area` braucht sie nicht, `mean` verwendet sie
bewusst nicht.

## 4. Die vier Methoden

### `area`: jedes Pixel mit seiner eigenen Spannung

$$
B_i^\mathrm{area} = \sum_{p \in P_i} g_p^{\,q} \cdot 1\,\mathrm{px}^2
\;\approx\; \int_{\text{Pore } i} g(\xi,\zeta)^q \,\mathrm{d}A
$$

Das ist eine Riemann-Summe, also eine diskrete Näherung des Flächenintegrals von $g^q$ über die Pore.
Jedes Pixel trägt seinen eigenen „Sub-Porenindex“ $g_p^{\,q}$ bei; die Pore ist die Summe ihrer
Pixel. Der Fehler kommt nur von der Pixelauflösung.

### `centroid`: Spannung am Schwerpunkt, je Hälfte

$$
B_i^\mathrm{centroid} = \sum_{k \in \{\mathrm{in},\,\mathrm{out}\}} A_i^k \cdot g\!\left(\bar\xi_i^{\,k},\ \bar\zeta_i^{\,k}\right)^{q},
\qquad
\bar\xi_i^{\,k} = \frac{1}{\lvert P_i^k \rvert}\sum_{p \in P_i^k} \xi_p,\quad
\bar\zeta_i^{\,k} = \frac{1}{\lvert P_i^k \rvert}\sum_{p \in P_i^k} \zeta_p
$$

Gemittelt wird die **Lage**, nicht die Spannung; das Feld wird je Teil nur an einem Punkt
ausgewertet (Mittelpunktregel). Bei einer gekrümmten Pore (C-, L-Form) kann der Schwerpunkt
außerhalb der Pore liegen; die Spannung wird dann an einer Stelle ohne Pore genommen.

### `max`: höchste Spannung, je Hälfte

$$
B_i^\mathrm{max} = \sum_{k \in \{\mathrm{in},\,\mathrm{out}\}} A_i^k \cdot \left(\max_{p \in P_i^k} g_p\right)^{q}
$$

Die ganze Teilfläche bekommt die Spitzenspannung. Konservativ: Ein Riss startet an der
höchstbelasteten Stelle. Eine große Pore, die nur mit einem Zipfel in den hoch belasteten Bereich
reicht, wird aber mit ihrer ganzen Fläche hoch bewertet.

### `mean`: Spannung über die ganze Pore gemittelt

$$
B_i^\mathrm{mean} = A_i \cdot \bar g_i^{\,q}, \qquad \bar g_i = \frac{1}{\lvert P_i \rvert} \sum_{p \in P_i} g_p
$$

Erst mitteln, dann potenzieren, ohne Teilung an der Mitte. Die Spannung wird nur an Stellen der Pore
ausgewertet (kein Problem mit gekrümmten Poren wie bei `centroid`). Nur im q fitter, nicht in
Pore_Detection.

### `run`

Keine eigene Methode: Jeder Schnitt nimmt die Methode aus seiner Zeile in `images.json`
(`pore_stress`), also so, wie Pore_Detection gelaufen ist.

## 5. Vom Beitrag zum Pareto und zum Porenindex

$$
\text{Anteil}_i = \frac{B_i}{\sum_j B_j} \cdot 100\,\%, \qquad
\Phi_q = \frac{\sum_i B_i}{A_\mathrm{Probe}}
$$

- Das Pareto sortiert die Poren nach $B_i$; die Balken zeigen $\text{Anteil}_i$, die Linie den
  kumulierten Anteil. Die obersten Poren sind die kritischen Poren (im Bild nummeriert).
- $\Phi_q$ ist dimensionslos, eine **spannungsgewichtete Porosität**: bei $q = 0$ ist
  $g^0 = 1$ und $\Phi_0$ genau die Porosität.
- Die Balkenfarbe (außen/innen) richtet sich nach dem mittleren $\zeta$ der ganzen Pore.

**Rolle von q.** $q$ steuert, wie stark die Spannung gegenüber der Fläche zählt. Beispiel: bei
$q = 10$ ist $0{,}9^{10} \approx 0{,}35$, aber $0{,}5^{10} \approx 0{,}001$; kleine Poren nahe der
Oberfläche schlagen dann große Poren in der Mitte.

## 6. Vergleich der Methoden

**Ordnung (für $q \ge 1$).** Weil $g^q$ für $q \ge 1$ konvex ist (Jensen-Ungleichung) und kein Pixel
mehr als die Spitzenspannung hat, gilt für jede Pore bzw. jeden Teil:

$$
A \cdot \bar g^{\,q} \;\le\; \sum_{p} g_p^{\,q} \;\le\; A \cdot g_\mathrm{max}^{\,q}
\qquad\Longrightarrow\qquad
\text{mean} \;\le\; \text{area} \;\le\; \text{max}
$$

- `mean` unterschätzt, umso mehr, je ungleichmäßiger die Spannung über die Pore und je größer $q$.
- `max` überschätzt immer.
- `centroid`: Ist $g$ innerhalb einer Hälfte linear, ist die Schwerpunktspannung gleich dem
  Mittelwert; `centroid` entspricht dann `mean` je Hälfte und unterschätzt ebenfalls.
- Für $0 < q < 1$ ist $g^q$ konkav, die linke Ungleichung kehrt sich um. Bei $q = 1$ und linearem
  Feld fallen `area`, `mean` und `centroid` zusammen.

Testdaten S001 (`S001_synth_002`, Feld `bending`, $q = 10$): `mean` 58,20 = `centroid` 58,20
< `area` 59,34 < `max` 85,36. Bei $q = 1$: `area` = `mean` = `centroid` = 3099,07.

**Abhängigkeit von der Porenabgrenzung.** Bei `area` ist alles eine reine Summe, daher

$$
\Phi_q^\mathrm{area} = \frac{1}{A_\mathrm{Probe}} \sum_{p \,\in\, \text{alle Porenpixel}} g_p^{\,q}
$$

$\Phi_q$ hängt also **nicht** davon ab, wie die Pixel zu Poren gruppiert sind (zwei Poren als eine
erkannt oder eine geteilt: gleiches $\Phi_q$). Die Gruppierung bestimmt nur das Pareto. Bei
`centroid`, `max` und `mean` bekommt jede Pore bzw. jeder Teil **einen** Spannungswert für die ganze
Fläche; dort hängt $\Phi_q$ von der Segmentierung und von der Teilung an der Mitte ab.

| Methode | Näherung von $\int g^q\,\mathrm{d}A$ | Zonenteilung | Tendenz ($q \ge 1$) | unabhängig von Segmentierung |
|---|---|---|---|---|
| `area` | Summe über Pixel | – (nicht nötig) | genau | ja |
| `centroid` | $A \cdot g(\text{Schwerpunkt})^q$ | ja | unterschätzt | nein |
| `max` | $A \cdot g_\mathrm{max}^q$ | ja | überschätzt | nein |
| `mean` | $A \cdot \bar g^{\,q}$ | nein | unterschätzt | nein |

## 7. Prüfung

- `area`, `centroid`, `max`: identisch zu Pore_Detection (`weighted_area_q…_px2` in `pores.json`),
  geprüft mit `test_data/check_contributions.py` (größte relative Abweichung ~1e-16).
- `mean`: Mittelwert und Fläche je Pore gegen die Pixelwerte nachgerechnet.
