# Fit von q an gemessene Risskurven

Code: `q_fitter/fit.py` (Rechnung), `q_fitter/fitplot.py` (Panel). Einstellungen: `config.yaml` → `fit`.

## Idee

Gemessen: wie oft Anrisse bei welcher relativen Spannung $g$ entstehen, kumuliert von 0 % bei der
Mittelspannung $g_\min = 0{,}5$ bis 100 % bei der vollen Spannung $g_\max = 1$, mit einer Kurve
$C(g)$ (z. B. kubische Trendlinie aus Excel) geglättet.

Modell: Die Anrisse verteilen sich über die Spannung so wie $\sum A\,g^q$ der Poren. Für ein $q$ ist
die Modellkurve der Anteil von $\sum A\,g^q$, der bei einer Spannung $\le g$ liegt, gezählt nur im
Bereich $[g_\min, g_\max]$:

$$F_q(g) = \frac{\sum_{g_k \le g} w_k\, g_k^{\,q}}{\sum_{g_\min \le g_k \le g_\max} w_k\, g_k^{\,q}}$$

$w_k, g_k$ sind die Teile der Poren nach der gewählten Porenspannung ([PORENSPANNUNG.md](PORENSPANNUNG.md)).
Mit `weight: id` ist $F_q$ der Mittelwert der $F_q$ aller IDs (jede ID zählt gleich, die Schliffe
einer ID werden summiert); mit `weight: pore` werden alle IDs zusammengezählt.

Gefittet wird pro Kurve das $q$ mit dem kleinsten mittleren quadratischen Abstand

$$\mathrm{RMS}(q) = \sqrt{\tfrac{1}{n}\sum_j \big(F_q(g_j) - C(g_j)\big)^2}$$

auf `points` gleichmäßig verteilten Spannungen $g_j$: Suche über den q-Bereich des Schiebers, dann
verfeinert (goldener Schnitt, auf 10⁻⁴ genau). Großes $q$ schiebt die Modellkurve nach rechts
(die hoch belasteten Poren zählen mehr), $q = 0$ ist die reine Flächenverteilung der Poren.

## Kurven eingeben

```yaml
fit:
  curves:
    - name: Serie A
      formula: "y = -1600x^3 + 3600x^2 - 2400x + 500"
```

Die Formel ist in $g$ (oder $x$). Erlaubt sind `^`, `²`, `³` und `x3` (Excel verliert beim
Kopieren die Hochstellung) für Potenzen, `3x` für `3*x`, Dezimalkomma zwischen Ziffern, ein
führendes `y =` und NumPy-Funktionen (`exp`, `log`, `sqrt`, …). Die Kurve wird auf 0 bei $g_\min$ und
1 am Ende des Vergleichsbereichs skaliert: Prozent oder Anteil ist dann egal, und kleine Abweichungen
der Trendlinie an den Enden spielen keine Rolle. Fällt die Kurve irgendwo, steht eine Warnung im
Panel (eine kumulierte Häufigkeit muss steigen).

## Nur so weit, wie das Spannungsfeld reicht

Ein FEM-Feld erreicht am Rand oft nicht genau 1, sondern z. B. 0,98. Darüber gibt es keine Poren, das
Modell ist bei 0,98 schon bei 100 %, die Kurve erst bei 1. Ohne Korrektur treibt das q stark nach oben
(an den Testdaten: wahres q = 8 → 9,8 bei 0,98, → 14 bei 0,95).

Deshalb wird nur bis $g_\text{top} = \min(g_\max,\ \text{höchste Spannung der Felder})$ verglichen,
und **beide** Kurven sind auf diesen Bereich bedingt: die gemessene Kurve wird auf 0 % bei $g_\min$
und 100 % bei $g_\text{top}$ skaliert,

$$C'(g) = \frac{C(g) - C(g_\min)}{C(g_\text{top}) - C(g_\min)}$$

und das Modell zählt nur Poren in $[g_\min, g_\text{top}]$. Verglichen wird also die Verteilung der
Anrisse zwischen 0,5 und 0,98; über den Bereich darüber wird nichts angenommen. Die höchste Spannung
eines Feldes wird über den ganzen Probenrahmen bestimmt (Formel: Raster 401 × 401, Gitter: an den
Stützstellen); bei mehreren Feldern zählt das niedrigste Maximum, damit jeder Schliff den ganzen
Bereich abdeckt. Das Panel zeigt $g_\text{top}$ im Titel, wenn es unter `g_max` liegt.

Die Lage der neutralen Faser spielt keine Rolle: gezählt wird überall, wo $g \ge g_\min$ ist.

## Panel

- links: die Kurven (gestrichelt), das Modell beim gefitteten q (gleiche Farbe), das Modell beim q
  des Schiebers (schwarz) und zum Vergleich die Anrisse aus `input/cracks` (graue Treppe, geht
  nicht in den Fit ein)
- rechts: RMS über q, Minimum markiert; „am Rand des q-Bereichs“ heißt: Minimum liegt bei `q.min`
  oder `q.max`, den Bereich vergrößern
- „q → fit“ setzt den Schieber auf das gefittete q (bei mehreren Kurven die gewählte)

## Grenzen

- Die kubische Kurve ist schon eine Glättung: Eine echte Modellkurve lässt sich mit einem kubischen
  Polynom nur auf etwa 1–3 % genau abbilden. Ein RMS in dieser Größe ist also kein schlechter Fit.
- Nur die Form zählt, nicht die Zahl der Anrisse.
- Das Modell kennt nur die Poren in den Schliffen im Input. Die Kurve und die Poren sollten
  aus derselben Gruppe von Proben stammen.

Prüfung: `.venv\Scripts\python test_data\check_fit.py` (eine aus dem Modell erzeugte Kurve mit
bekanntem q wird wiedergefunden, auch als kubische Näherung).
