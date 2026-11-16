# Geometrie-Check: passen Bruchfläche und Schliffe zusammen?

Start: `.venv\Scripts\python geometry_main.py` (eigenes Fenster, unabhängig vom q fitter).
Einstellungen: `config.yaml` → `geometry` (Toleranz, Keilwinkel, Ausgabeordner). Code:
`q_fitter/geometry.py` (Daten, Prüfungen), `q_fitter/geometry_view.py` (Fenster, Plots).

## Warum

Der q fitter rechnet in **relativen** Koordinaten: $\xi = x / L$ entlang der Probe und
$\zeta = z / T$ über die Dicke, jeweils im Probenrahmen des Bildes. Ein Riss bei $(\xi, \zeta)$ auf
der Bruchfläche wird an derselben Stelle $(\xi, \zeta)$ in jeden Schliff übertragen, und auch die
Spannung $g(\xi, \zeta)$ wird relativ berechnet. Das ist nur richtig, wenn alle Rahmen einer ID
**dieselbe Geometrie** beschreiben. Ist die Bruchfläche z. B. 25 % dicker als der Schliff (anderer
Ort der Probe, schräger Schnitt, falsch erkannter Rahmen), liegt ein Riss bei $\zeta = 0{,}9$ auf der
Bruchfläche physikalisch woanders als $\zeta = 0{,}9$ im Schliff.

## Was dafür vorhanden ist

Beide Programme schreiben denselben Probenrahmen (Ursprung, Winkel, Länge und Dicke in px) und den
Maßstab (µm/px aus dem Maßstabsbalken):

| | Schliffe (Pore_Detection) | Bruchflächen (Fatigue_crack_labeler) |
|---|---|---|
| Rahmen | `images.json` (von Hand gesetzte Rahmen sind schon eingetragen) | `images.json`, darüber `frames.json` (von Hand gesetzt, gilt vorrangig) |
| Maßstab | `pixel_size_um`, `scale_label` | `pixel_size_um` (auch in der Excel, Blatt *Images*) |
| Umriss der Probe | `<Bild>/roi_mask.tif` | `<Bild>/roi_mask.tif` |

**Was fehlen kann:**
- Liegt in `input/cracks` nur die Excel-Datei statt des ganzen Ergebnisordners des Labelers, gibt
  es Länge, Dicke und Maßstab, aber **keinen Umriss**. Deshalb am besten den ganzen Ordner
  `<ID>_results` hineinziehen.
- Ohne lesbaren Maßstabsbalken (`pixel_size_um` leer) kann ein Bild nur **relativ** (Seitenverhältnis,
  Umriss) verglichen werden, nicht in µm.

## Was das Fenster zeigt

**Tab „Frames“:** eine Zeile pro Rahmen (Schliffe und Bruchflächen) mit Länge, Dicke, Länge/Dicke,
der Abweichung vom **Median der ID** in %, dem Maßstab, ob der Rahmen von Hand gesetzt ist, und dem
Keilwinkel. Rot hinterlegt ist eine Zeile, wenn eine Abweichung die Toleranz übersteigt (Standard
±10 %), der Maßstab fehlt oder der Keilwinkel groß ist (ein Hinweis auf einen schlecht erkannten
Rahmen). Bei mehr als dem 3-fachen bzw. weniger als einem Drittel des Medians steht die Abweichung
als Faktor da (z. B. `×1.6e+09`): Das ist dann fast immer ein falsch gelesener Maßstab.

**Tab „Cracks“:** für jeden Riss und jeden Schliff, wo dasselbe $\zeta$ physikalisch landet:

- `below_outer_fracture_um`: Tiefe unter der Außenfläche auf der Bruchfläche, $(1-\zeta)\,T_\text{Bruch}$
- `below_outer_section_um`: dieselbe Tiefe im Schliff, $(1-\zeta)\,T_\text{Schliff}$
- `d_below_outer_um`, `d_above_inner_um`, `d_along_um`: die Differenzen in µm, also der Fehler, den das
  Rechnen in relativen Koordinaten an dieser Stelle macht

**Tab „Plots per ID“:** pro ID drei Bilder:

| Bild | Was man sieht | Woran man Probleme erkennt |
|---|---|---|
| **absolut (µm)** | alle Rahmen mittig übereinander, Umrisse gefüllt, Risse an ihrer Stelle auf der Bruchfläche | Rechtecke unterschiedlich groß → unterschiedliche Geometrie; Rahmen ohne oder mit falschem Maßstab fehlen hier (in der Legende vermerkt) |
| **relativ (ξ, ζ)** | jeder Rahmen auf das Einheitsquadrat gestreckt, so wie der q fitter rechnet | Umrisse füllen das Quadrat unterschiedlich (z. B. ein Umriss nur bis ξ = 0,6) → der Rahmen passt nicht zur Probe |
| **Abweichungen** | Länge, Dicke, Länge/Dicke jedes Rahmens gegen den Median, Toleranz grün | Balken außerhalb des grünen Bands |

„Save report“ schreibt `output/geometry/<ID>.png` und `geometry_check.xlsx` (beide Tabellen).

## Was daraus folgt

| Befund | Bedeutung | Was tun |
|---|---|---|
| Länge und Dicke gleich stark daneben, **Länge/Dicke passt** | Maßstab falsch gelesen (Bild an sich in Ordnung) | Maßstab im jeweiligen Programm prüfen; für den q fitter unkritisch, solange er nur relativ rechnet |
| **Länge/Dicke** weicht ab | Die Form ist anders: anderer Schnittort, schräger Schnitt oder falscher Rahmen | Rahmen im Programm ansehen und ggf. von Hand setzen; sonst ist $\zeta$ zwischen Bruchfläche und Schliff nicht vergleichbar |
| Umriss füllt das Einheitsquadrat nicht | Rahmen falsch erkannt | Rahmen von Hand setzen (beide Programme können das) |
| Nur die **Bruchfläche** weicht ab, die Schliffe untereinander passen | Bruch an anderer Stelle als die Schliffe, oder Rahmen des Labelers falsch | Rahmen im Labeler prüfen; die Fehler in µm im Tab „Cracks“ abschätzen |
| `d_below_outer_um` klein gegen die Porengrößen und den Spannungsgradienten | Relative Rechnung unkritisch | – |
| `d_below_outer_um` groß (z. B. > 5 % der Dicke) | Riss liegt im Schliff an anderer Tiefe, $g$ am Riss ist entsprechend falsch, der Fit von q verschoben | Geometrie klären; die ID ggf. aus dem Fit nehmen |

## Testdaten

`test_data/make_cracks.py` schreibt für die Test-IDs Ergebnisordner im Format des Labelers. Die
Bruchfläche ist dabei der erste Schliff, bewusst verändert:

| ID | Bruchfläche gegen Schliff A | Erwartung im Check |
|---|---|---|
| S001 | gleich | F1 = A; Schliff B hat einen unsinnigen Maßstab (×1,6·10⁹) |
| S002 | Länge +3 %, Dicke +5 % | F1 Dicke +16 % gegen den Median (Schliff C hat einen falschen Rahmen und fällt heraus) |
| S003 | Dicke +25 % | F1 Dicke +25 %, Länge/Dicke −20 % |
| S005 | automatischer Rahmen zu klein, von Hand gesetzter Rahmen (`frames.json`) korrigiert | F1 „by hand“, passt zu Schliff A |

Die Maßstäbe der synthetischen Schliffbilder sind zufällig (0,0007 µm/px bis 1,26 m/px). Deshalb
schlägt der Check in µm bei vielen Schliffen an. Das zeigt gut, dass genau solche Fehler gefunden
werden; mit echten Bildern sollte das nicht vorkommen.
