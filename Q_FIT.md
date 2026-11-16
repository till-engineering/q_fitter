# Fit von q aus der Spannung an den Rissursprüngen

Der q fitter bestimmt **ein** q für alle IDs aus den gelabelten Rissursprüngen, als **Schranke** (Hauptergebnis, Abschnitt 2) und als **typischen** Wert (Abschnitt 3). Code:
`q_fitter/fit.py` (Rechnung), `q_fitter/fitplot.py` (Panel „Fit q“ im Fenster), Einstellungen in
`config.yaml` unter `fit`. Die Beiträge $B_i = w_i\, g_i^{\,q}$ und die Methoden (`area`,
`centroid`, `max`, `mean`) sind in [PORENSPANNUNG.md](PORENSPANNUNG.md) beschrieben; der Fit
verwendet dieselbe Methode wie das Pareto (Schalter „Pore stress“).

## 1. Idee

Pro Riss wird nur **eine Zahl** verwendet: die Spannung am Rissursprung

$$
g_c = g(\xi_c, \zeta_c)
$$

aus dem Spannungsfeld der Schliffe der ID (dasselbe Feld wie für die Poren, neu berechnet; die
Spalte `stress` der Labeler-Datei wird nicht gelesen). **Nicht** verwendet werden die Lage des
Risses (Schliff und Bruchfläche sind verschiedene Ebenen) und die Fläche der Anrisspore (nicht
bekannt).

Das Porenmodell sagt mit $q$ voraus, bei welcher Spannung Risse starten: Pore (bzw. Teil) $i$ ist
Ursprung mit der Wahrscheinlichkeit $B_i / \sum_j B_j$ (Weakest Link: $q$ spielt die Rolle des
Weibull-Moduls). Für jeden Riss wird gefragt, wie viel von $\sum B$ der ID **höher** belastet ist
als sein Ursprung:

$$
u_c(q) = \frac{\sum_{i:\ g_i > g_c} B_i(q) \;+\; \tfrac12 \sum_{i:\ g_i = g_c} B_i(q)}{\sum_i B_i(q)}
$$

Summiert wird über alle Teile aller Schliffe der ID.

## 2. Schranke (Hauptergebnis)

Gesucht ist das **kleinste** $q$, bei dem die kritischen Poren über den Rissursprüngen liegen, also
mindestens der Anteil $p$ (`fit.bound.share`, Standard 90 %) von $\sum B$ bei höherer Spannung als
der Ursprung liegt:

$$
u_c(q) \ge p
$$

Weil $u_c$ mit $q$ wächst, hat jeder Riss ein eigenes $q_c$, ab dem er „abgedeckt“ ist. Die Schranke
ist das kleinste $q$, bei dem ein Anteil `fit.bound.cracks` (Standard 100 %) der Risse abgedeckt ist,
also das entsprechende Quantil der $q_c$ (bei 100 %: das größte $q_c$).

- `reference: every_crack`: jeder Riss zählt einzeln. Die Schranke setzt der am **höchsten**
  belastete Riss.
- `reference: lowest_crack_per_id`: je ID zählt nur der am **niedrigsten** belastete Riss, also
  „alles, was mindestens so hoch belastet ist wie dort, wo in dieser Probe schon ein Riss startete“.

Eigenschaften:
- Größeres $q$ deckt immer mehr ab. „Möglichst viele Poren über den Rissen“ hat daher nur als
  „kleinstes $q$, das reicht“ eine Lösung.
- Die Schranke hängt an **einem** Riss und hat kein statistisches Intervall. Neue Risse können sie
  nur erhöhen (bei `cracks: 1.0`).
- Ausreißer nach unten (Riss in der Mitte, $u \approx 1$ bei jedem $q$) stören nicht. Ausreißer an der
  Oberfläche bestimmen sie; mit `cracks` < 1 bleibt ein Anteil davon unberücksichtigt.
- Liegt ein Riss an der höchsten Spannung der ID, wird er nie abgedeckt: „bound q > q max“.

## 3. Typisches q̂

Stimmt $q$, dann ist jedes $u_c$ eine gleichverteilte Zufallszahl auf $[0, 1]$, also im Mittel $0{,}5$.
Mit größerem $q$ wandert das Gewicht zu hoher Spannung, jedes $u_c$ wächst mit $q$. Daher gibt es
genau ein $\hat q$ mit

$$
\bar u(\hat q) = \frac{\sum_c a_c\, u_c(\hat q)}{\sum_c a_c} = 0{,}5
$$

mit Gewichten $a_c = 1$ (`fit.weight: crack`, jeder Riss zählt gleich) oder
$a_c = 1/(\text{Risse der ID})$ (`fit.weight: id`, jede ID zählt gleich). Gesucht wird auf dem
Raster des Schiebereglers, zwischen zwei Rasterpunkten linear interpoliert.

- $\bar u < 0{,}5$ bei allen $q$ bis `q.max`: Die Risse starten höher belastet, als jedes $q$ im
  Bereich erklärt → „q̂ > max“.
- $\bar u \ge 0{,}5$ schon bei `q.min`: Die Risse starten tiefer, als selbst $q = $ `q.min` erwartet
  → „q̂ ≤ min“.

## 4. Unsicherheit (typisches q̂)

**95 %-Bereich (Modell).** Alle $q$, bei denen $\bar u$ nicht signifikant von $0{,}5$ abweicht:

$$
\lvert \bar u(q) - 0{,}5 \rvert \le c, \qquad
c = \text{95 %-Quantil von } \Big\lvert \tfrac{\sum_c a_c U_c}{\sum_c a_c} - 0{,}5 \Big\rvert,\ U_c \sim \mathcal U(0,1)
$$

$c$ wird simuliert (20 000 Ziehungen) und ist damit auch für 1–3 Risse exakt. Dieser Bereich gilt,
wenn ein gemeinsames $q$ für alle IDs das richtige Modell ist.

**Streuung über die IDs (Bootstrap).** IDs werden mit Zurücklegen gezogen und $\hat q$ jeweils neu
bestimmt (`fit.bootstrap` Ziehungen, ab `fit.min_ids` IDs). Das zeigt, wie stark das Ergebnis an
einzelnen IDs hängt; mit wenigen IDs ist dieser Bereich zu eng (siehe 6.).

## 5. Was q̂ bedeutet – und was nicht

- $\hat q$ ist **keine Untergrenze**. Es ist das $q$, bei dem die Rissursprünge **im Mittel** in der
  Mitte der vorhergesagten Verteilung liegen: Die Hälfte von $\sum A g^q$ ist höher belastet als ein
  typischer Ursprung, die Hälfte niedriger.
- Ein einzelner Anriss bei niedriger Spannung (tief in der Probe) hat $u_c$ nahe 1 und zieht $q$
  nach unten. Er macht seine Tiefe **nicht** zum Gipfel der Verteilung; er ist ein Riss unter vielen.
- Starten alle Risse tief: $\hat q \to 0$, nur die Fläche zählt ($\Phi_0$ = Porosität). Starten alle
  an der höchsten Spannung: $\hat q$ geht an die obere Grenze.
- Im Histogramm des Panels (aktuelles $q$): Blau ist $\sum A g^q$ über der Spannung, Rot sind die
  Rissursprünge. Beim richtigen $q$ liegen die roten Striche **über die blaue Masse verteilt**, nicht
  alle an ihrem Gipfel oder an ihrem Rand.
- Am Bild steht bei jedem Riss sein $u$ beim aktuellen $q$ (z. B. `C1  u 0.38`): 0 = höchstbelastete
  Stelle der ID, 1 = niedrigstbelastete (gemessen an $\sum A g^q$).

## 6. Prüfung (`test_data/check_fit.py`)

Risse werden aus dem Modell selbst gewürfelt, mit bekanntem $q_\text{wahr}$ (Ursprung = Teil $i$ mit
Wahrscheinlichkeit $B_i/\sum B$, an die Stelle mit genau dieser Spannung gesetzt), 40 Läufe je Zeile,
Porendaten aus `input/pores` (5 IDs, Methode `centroid`):

| $q_\text{wahr}$ | Risse je ID | Median $\hat q$ | $\hat q$ 10…90 % | Breite 95 %-Bereich | Bereich trifft | Bootstrap trifft |
|---|---|---|---|---|---|---|
| 1 | 1 | 1,19 | 0,00 … 3,34 | 5,0 | 92 % | 80 % |
| 3 | 3 | 2,87 | 1,98 … 5,66 | 4,7 | 92 % | 80 % |
| 6 | 20 | 6,06 | 5,47 … 7,24 | 3,2 | 100 % | 88 % |
| 12 | 1 | 12,03 | 6,29 … 19,69 | 22,0 | 95 % | 82 % |
| 12 | 20 | 12,46 | 10,78 … 14,24 | 5,6 | 100 % | 88 % |

- $\hat q$ ist unverzerrt; der 95 %-Bereich trifft in 92–100 % der Läufe (etwas vorsichtig).
- Der Bootstrap über nur 5 IDs ist zu eng (78–90 %), daher nur als Zusatzangabe.
- Mit einem Riss je ID ist $q$ nur grob bestimmt (Bereichsbreite 5–22); bei großem $q$ braucht man
  deutlich mehr Risse, weil dann wenige Poren das ganze Gewicht tragen.

## 7. Grenzen

- Ein gemeinsames $q$ für alle IDs und Spannungsfelder ist eine Modellannahme.
- Eine Pore im Schliff ist nicht die Anrisspore; verglichen wird nur, ob die Spannung am Ursprung zur
  **Population** der Poren der ID passt. Die Schliffe sollten daher für die Probe repräsentativ sein.
- Liegen viele Ursprünge exakt an derselben Spannung (z. B. Oberfläche, $g = 1$ bei Biegung), sind
  sie untereinander nicht unterscheidbar; sie zählen über die Halbregel bei Gleichstand.
