# q_fitter – Projektplan

> Stand: 2026-11-05 · umgesetzt: M1 und M2
> Theorie: `zusammenfassung_porenmodell.md` · Eigene Methoden schreiben: `METHODEN.md`

---

## 1. Ziel

q_fitter kalibriert den Exponenten q der Porenschwere **S = A · g^q** aus Schwingversuchen.
Grundidee: Der Rissausgang (Index 0) war die schwerste Pore der Probe. Alle anderen Poren waren
belastet und haben **nicht** versagt. Also gilt für jede Konkurrenzpore i:

```
A0 · g0^q  ≥  Ai · gi^q
```

Jede Probe liefert daraus Schranken für q, und die Schnittmenge über alle Proben ist der zulässige
Bereich (Methode M1).

Versuchsablauf:
1. Schwingversuch bis zum Bruch.
2. Bruchfläche fotografieren → Anrissstelle im **Fatigue_crack_labeler** markieren (ξ, ζ).
3. Fläche der Anrisspore **von Hand** im Bruchbild messen (A0, projizierte Fläche) → Excel.
4. Etwas abschleifen und polieren → Schliff → **Pore_Detection** findet die Konkurrenzporen.
5. q_fitter: Rohdaten → Porenmodelle → Spannung → M1.

---

## 2. Festgelegte Entscheidungen

| Punkt | Entscheidung |
|---|---|
| Eingabe | **Feste Ordner im Projekt** (`daten/`). Du kopierst die Daten hinein, q_fitter liest nie aus anderen Projekten. |
| Was eingelesen wird | **Nur Rohdaten.** Alles Gerechnete (A, g, Schwere, Fit) rechnet q_fitter selbst neu. |
| Von Pore_Detection | pro Schliffbild `labels.tif` (= Ground Truth, Richtigkeit liegt bei dir) + aus `images.json` nur Pixelgröße und KOS-Zahlen. `pores.json` wird **nicht** gelesen. |
| Vom Labeler | aus `cracks.json` **nur ξ und ζ**. Spannung und Feldname des Labelers werden ignoriert. |
| A0 | aus `rissausgaenge.xlsx` (`A0_um2`, wahlweise `A0_schliff_um2`) |
| Zuordnung | über die **ID**. Eine ID wird nur ausgewertet, wenn sie in allen drei Quellen vorkommt und `cracks.json` **genau einen** Anriss hat. Sonst wird sie übersprungen und mit Grund aufgeführt. |
| Mehrere Schliffe pro ID | alle Poren werden zusammengelegt |
| Spannungsfeld | **ein Feld pro Lauf** (Config), für Rissausgang und Poren gleich. In einem Lauf nur gleich belastete Proben. |
| KOS | wird nicht neu bestimmt; ξ, ζ und die KOS-Zahlen werden nur gelesen und umgerechnet. Die Umrechnung stimmt mit Pore_Detection überein (geprüft: Fläche exakt, ξ bis 1e-15, ζ bis 0,0013 bei Randporen, weil Pore_Detection pixelweise auf 0..1 begrenzt). |
| Porenmodelle | **Kette**, austauschbar, laufen **vor** der Spannungsberechnung (sie ändern A **und** Lage) |
| Spannungsmodell | **genau eins pro Lauf**, austauschbar; bekommt g_feld fertig und gibt g zurück |
| Rissausgang in den Modellen | läuft durch dieselben Modelle; hat aber keine Form (nur A0 und Punkt). Die mitgelieferten Porenmodelle lassen ihn unverändert. |
| Flächenkorrektur der Schliffporen | **keine** in v1. Zu kleine Schliffflächen machen die M1-Schranken nur breiter (zu beiden Seiten), das wahre q bleibt drin – sofern A0 nicht zu groß gemessen ist (z. B. Cluster). |
| Rest der Anrisspore im Schliff | Schliffporen näher als `exclusion.radius_um` am Rissausgang werden ausgeschlossen (Abstand zum nächsten Porenpixel). Sie würden falsche Schranken erzeugen. |
| Fit-Methoden | **M1** (Schranken) und **M2** (Konkurrenz-Likelihood). M3 später als eigenes Modul. Bekannte Schwäche von M2: Schliff- und Bruchflächenmessung verschieden, nur ein Schnitt im Nenner (siehe Abschnitt 6b). |
| Config | eine `config.yaml`, einzige Quelle aller Einstellungen, keine Standardwerte im Code |
| Sprache | Dokumente deutsch; Code, Spaltennamen und Grafiken englisch (wie Pore_Detection und Labeler) |

---

## 3. Installation und Start

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

.venv\Scripts\python main.py            # Lauf: daten/ -> ergebnisse/
.venv\Scripts\python main.py methods    # alle verfügbaren Methoden auflisten
.venv\Scripts\python tools\test_synthetic.py          # Test: Testdaten erzeugen + auswerten, ohne Rauschen
.venv\Scripts\python tools\test_synthetic.py --k 3    # Test mit Rauschen (für M2), Ergebnisse in ergebnisse/
```

---

## 4. Ordner

```
q_fitter/
├── PLAN.md, METHODEN.md, zusammenfassung_porenmodell.md
├── config.yaml                 # ALLE Einstellungen
├── main.py                     # Kommandozeile
├── requirements.txt
│
├── daten/                      # EINGABE (feste Struktur)
│   ├── poren/<ID>_results/             von Pore_Detection kopiert:
│   │   ├── images.json                    Pixelgröße + KOS je Bild
│   │   └── <ID>_<Bild>/labels.tif         Poren (Pixel = Porennummer)
│   ├── risse/<ID>_results/cracks.json  vom Labeler kopiert (nur xi, zeta)
│   ├── spannungsfelder/<name>.yaml     Spannungsfelder (Format wie Labeler / Pore_Detection)
│   └── rissausgaenge.xlsx              eine Zeile je ID: A0_um2 (+ A0_schliff_um2, bemerkung, eigene Spalten)
│
├── ergebnisse/                 # AUSGABE (wird bei jedem Lauf überschrieben)
│
├── q_fitter/                   # Code
│   ├── core/                   # Gerüst – musst du normalerweise nicht anfassen
│   │   ├── config.py           config.yaml lesen
│   │   ├── registry.py         @register, Methoden finden
│   │   ├── methods.py          Basisklassen PoreModel, StressModel, Fit
│   │   ├── data.py             Sample, SchliffImage, Einlesen der Ordner
│   │   ├── stress_field.py     YAML-Spannungsfelder auswerten
│   │   ├── pipeline.py         der Ablauf
│   │   └── output.py           Excel / JSON / PNG
│   ├── pore_models/            # HIER eigene Porenmodelle (eine Datei je Modell)
│   │   ├── merge_clusters.py, ellipse.py, convex_hull.py
│   │   └── _template.py        Vorlage (wird nicht geladen)
│   ├── stress_models/          # HIER eigene Spannungsmodelle
│   │   ├── field.py
│   │   └── _template.py        Vorlage mit Beispiel-Kerbterm
│   └── fits/
│       ├── m1.py, m1_figures.py    M1 + seine Grafiken
│       └── m2.py                   M2
│
├── tools/make_synthetic.py     # Testdaten mit bekanntem q (Config-Abschnitt synthetic)
├── tools/test_synthetic.py     # ein Befehl: Testdaten erzeugen + auswerten + mit der Wahrheit vergleichen
├── testdaten/synth_results/    # 48 synthetische Schliffe, durch Pore_Detection gelaufen (Quelle für make_synthetic)
├── daten_synth/                # erzeugte Testdaten ohne Rauschen (q_true = 6), Layout wie daten/
└── daten_synth_k3/             # erzeugte Testdaten mit Rauschen (q_true = 6, k_true = 3)
```

---

## 5. Ablauf eines Laufs

```
1. Einlesen je ID     labels.tif + images.json → eine Zeile je Pore: A_raw_um2 = Pixel × Pixelgröße²,
                      xi, zeta = Schwerpunkt; Rissausgang = eigene Zeile (kind = "crack") mit A0, xi, zeta
2. Porenmodelle       Kette aus config: pore_models        → ändern A_um2, xi, zeta, fassen zusammen
3. Ausschluss         Schliffporen < exclusion.radius_um am Rissausgang → excluded
4. g_feld             Spannungsfeld(xi, zeta)              → Spalte g_field
5. Spannungsmodell    config: stress.model                 → Spalte g
6. M1                 mit A_um2 und g
7. Ausgabe            ergebnisse/
```

Die Porentabelle mit allen Spalten ist in `METHODEN.md` beschrieben.

---

## 6. M1 – paarweise Schranken

Für jede Konkurrenzpore: s = ln(g0/gi), a = ln(Ai/A0), q* = a/s.

| Fall | Bedeutung |
|---|---|
| s > 0, a > 0 | Untergrenze q ≥ q* |
| s < 0, a < 0 | Obergrenze q ≤ q* |
| s > 0, a ≤ 0 (oder s = 0, a ≤ 0) | nicht informativ |
| s < 0, a ≥ 0 (oder s = 0, a > 0) | Widerspruch |
| gi ≤ 0 | ohne Spannung, nicht informativ |

Pro Probe: q_u = größte Untergrenze (0, wenn keine), q_o = kleinste Obergrenze (leer, wenn keine).
Über alle Proben: Schnittmenge max q_u … min q_o. V(q) auf einem Raster: Anzahl Proben, deren
Rissausgang bei q nicht gewinnt; V = 0 ist genau die Schnittmenge.

---

## 6b. M2 – Konkurrenz-Likelihood

Jede Pore j der Probe hätte versagen können, mit Wahrscheinlichkeit ∝ Schwere^k:

```
P(Rissausgang | q, k) = (A0·g0^q)^k / Σ_j (Aj·gj^q)^k        ℓ(q, k) = Σ_Proben ln P
```

- k = Schärfe des Versagens (k → ∞: immer die schwerste Pore = M1).
- Schätzung auf einem Raster (q linear, k logarithmisch); 95-%-Intervall von q aus der
  Profil-Likelihood: 2·[ℓ_max − ℓ_p(q)] ≤ 3,84. Im q-k-Bild ist die gemeinsame 95-%-Region (5,99) eingezeichnet.
- **Warnung „best k at the upper end“**: Alle Proben vertragen sich (M1-Schnittmenge nicht leer) →
  M2 sagt nicht mehr als M1.
- Je Probe: Wahrscheinlichkeit und Rang des Rissausgangs beim besten (q, k) (Blatt Proben).

Bekannte Schwächen (im Hinterkopf behalten):
1. A0 (Bruchfläche, größter Querschnitt) und Schliffporen (zufälliger Anschnitt) sind verschieden
   gemessen → bei M2 verschiebt sich der Schätzwert (bei M1 wird der Bereich nur breiter). Abhilfe:
   Faktor aus `A0_schliff_um2 / A0_um2` abschätzen und als Porenmodell einsetzen.
2. Im Nenner stehen nur die Poren eines Schnitts, nicht des ganzen Volumens.
3. Ohne Streuung in den Daten → k am Rasterende, M2 = M1.

---

## 7. Ausgabe (`ergebnisse/`)

| Datei | Inhalt |
|---|---|
| `ergebnis.xlsx` | Blätter **Proben**, **Uebersprungen**, **m1_overall**, **m1_V_q**, **m1_contradictions**, **Poren** |
| `proben.json` | je Probe: Anzahl Bilder / Poren / ausgeschlossen / außerhalb des Rahmens (`outside_frame`, `crack_outside_frame`), A0, ξ0, ζ0, g0, Excel-Spalten, M1: q_lower, q_upper, Anzahl Schranken, Widersprüche, welche Pore die engste Schranke liefert, Status |
| `poren.json` | je Pore: Rohwerte, Werte nach den Modellen, dist_um, g_field, g, M1: s, a, q*, Art der Schranke |
| `uebersprungen.json` | IDs mit Grund |
| `m1_overall.json` | Gesamtergebnis: Schnittmenge, Status, V-Minimum und die q-Bereiche dazu |
| `m1_V_q.json` | V(q) auf dem Raster |
| `m1_bounds.png` | Balken je Probe: Untergrenze ▶ blau, Obergrenze ◀ orange, Schnittmenge hellblau. **Widersprüche werden gezeigt, nicht verworfen** (siehe unten). |
| `m1_V_q.png` | V(q) |
| `m1_contradictions.json` | Auswertung der Widersprüche (siehe unten) |
| `m1_pore_map.png` | Porenkarte: jeder Konkurrent aller Proben relativ zu seinem Rissausgang |
| `m2_overall.json`, `m2_profile.json` | M2: bestes q, k, 95-%-Intervalle, Warnungen; Profil-Likelihood über q |
| `m2_profile.png`, `m2_likelihood.png` | M2: Profil-Likelihood von q (+ bestes k je q); Likelihood über q und k |
| `m1_samples/<ID>.png` | Schliffbild je Probe mit farbigen Poren (`sample_images`: contradictions / all / none) |
| `config_used.yaml` | Kopie der Config |
| `.q_fitter_files.txt` | Dateien dieses Laufs; der nächste Lauf löscht genau diese zuerst (kein veraltetes `m2_*`/`val_*`) |

### Widersprüche – Hinweis, dass das Modell für A oder g nicht passt

Drei Arten werden unterschieden, gezählt (`m1_overall`, `proben`) und im Plot gezeigt:

| Art | Bedeutung | im Plot |
|---|---|---|
| Widerspruchspore | eine Pore ist größer **und** weiter außen als der Rissausgang → kein q passt | rechts „✕ n contradicting pores“; der Balken zeigt die Schranken der übrigen Poren |
| leer innerhalb der Probe | Untergrenze > Obergrenze (Poren der Probe widersprechen sich) | rot schraffierter Bereich zwischen beiden Grenzen, rechts „✕ lower > upper“ |
| leer zwischen Proben | jede Probe für sich ok, aber die Intervalle überlappen nicht | hellrote Zone über alle Zeilen; die beiden Proben, die sie festlegen, fett |

Der hellblaue Bereich zeigt die Schnittmenge der Proben **ohne** Widerspruch.

**Tabelle `m1_contradictions`** – eine Zeile je beteiligter Pore:

| Spalte | Bedeutung |
|---|---|
| `type` | contradicting pore / lower > upper / between samples |
| `role` | was die Pore tut (gewinnt immer / setzt Untergrenze / setzt Obergrenze) |
| `A_ratio`, `g_ratio` | A/A0 und g/g0 – **wie stark** der Widerspruch ist (knapp über 1 = evtl. Messrauschen, deutlich = Modell) |
| `q_star`, `gap_q` | Grenze der Pore und Lücke zwischen den gekreuzten Grenzen |
| `xi`, `zeta`, `dist_um` | Lage der Pore, Abstand zum Rissausgang |
| `hint` | automatische Hinweise: nahe am Rissausgang (Rest der Anrisspore? → `exclusion.radius_um`), außerhalb des Probenrahmens (Spannung vom Rand übernommen → KOS/ROI prüfen) |

**Porenkarte `m1_pore_map.png`** – jeder Konkurrent als Punkt: x = ln(g/g0), y = ln(A/A0). Oben rechts
(größer **und** höher belastet) gewinnt die Pore bei jedem q → Widerspruch. Bei einem q gewinnt der
Rissausgang unterhalb der Geraden y = −q·x; eingezeichnet für q_u und q_o.

**Schliffbilder `m1_samples/<ID>.png`** – alle Poren nach ihrer Rolle gefärbt (blau Untergrenze,
orange Obergrenze, rot Widerspruch, grau nicht informativ), die Poren mit der engsten Schranke und die
Widerspruchsporen umkreist und beschriftet (A/A0, g/g0), Rissausgang als Kreuz mit Kreis der Fläche A0
an seiner Stelle (ξ, ζ), Probenrahmen mit außen/innen.

---

## 8. Testdaten mit bekanntem q

`tools/make_synthetic.py` nimmt einen Ergebnisordner von Pore_Detection mit vielen Schliffbildern
(z. B. aus dessen `syntetic_test/generate.py`) und macht daraus **eine Probe je Bild**. Für jede
Probe wird ein **künstlicher Rissausgang außerhalb des Schliffs** gezogen (ξ, ζ gleichverteilt,
A0 = Faktor × größte Schliffpore, Faktor log-gleichverteilt) und nur behalten, wenn er bei `q_true`
gewinnt – mit den Porenmodellen und dem Spannungsmodell aus der Config.

Mit Rauschen (`--k`): ein künstlicher Kandidat **und** alle Schliffporen konkurrieren, die versagende
Pore wird mit Wahrscheinlichkeit S^k/ΣS^k gezogen (trifft es eine Schliffpore, wird sie zum Rissausgang
und aus dem Schliff entfernt). **Nie** Kandidaten nach dem Ergebnis behalten/verwerfen – das verzerrt
jede Likelihood (erste Version tat das: q systematisch zu klein).

Ein Befehl: `python tools/test_synthetic.py [--k 3] [--q 6] [--seed 1]` → Ergebnisse in `ergebnisse/`.

Geprüft (2026-11-05), 28 Proben aus den synthetischen Bildern von Pore_Detection:

| Einstellung | q_true | M1-Bereich |
|---|---|---|
| keine Porenmodelle, Feld `bending` | 6 | 3,99 … 7,10 ✔ |
| `merge_clusters` → `convex_hull`, Kerbmodell aus `_template.py` | 9 | 5,98 … 9,46 ✔ |
| M2 ohne Rauschen | 6 | 3,7 … 7,1, Warnung „k am Rasterende“ ✔ |
| M2 mit Rauschen k_true = 3, 12 Seeds | 6 | q_true im 95-%-Intervall in 11 von 12 ✔ (M1 zerfällt jedes Mal in Widersprüche) |

Hinweis: Die synthetischen Bilder haben zufällige Maßstabsbalken (Test der Maßstabserkennung),
deshalb sind die µm-Werte dort unsinnig. Für M1 ist das egal, denn A0 wird relativ zu den Poren
gezogen. Den Ausschlussradius bei diesen Daten auf 0 setzen.

---

## 8b. Qualitätskontrolle (`validation`)

Abschaltbar (`enabled: false` = läuft gar nicht). Je Split werden zufällig `test_fraction` der Proben
als Test gezogen (gerundet, mindestens 1 Test- und 1 Trainingsprobe). Jeder Fit aus `fits` läuft nur
auf den Trainingsproben, dann wird für jede Testprobe mit diesem q S = A·g^q aller Poren berechnet:

| Maß | Bedeutung |
|---|---|
| Treffer | Rissausgang ist die schwerste Pore (Rang 1) |
| Rang | 1 + Anzahl Konkurrenten, die schwerer sind |
| q_share | Anteil des trainierten q-Bereichs, in dem der Rissausgang gewinnt |
| p_crack | nur M2: vorhergesagte Wahrscheinlichkeit S0^k / ΣS^k |
| chance | Trefferquote bei blindem Raten: 1 / (1 + Konkurrenten) |

Welches q: **M1** = mittlerer Rasterpunkt des Bereichs mit V minimal (Bereich = alle Punkte mit V min;
ohne Obergrenze endet er bei `q_stop`), **M2** = q best, k best, Bereich = 95-%-Intervall.
Neue Fits nehmen teil, wenn sie `prediction()` liefern (`q_fitter/core/methods.py`).
Splits sind unabhängige Zufallszüge (derselbe Split kann doppelt vorkommen); kein „alle Kombinationen“.
M2 merkt sich das Likelihood-Raster je Probe, dadurch kostet ein Split nur eine Summe (~0,1 s bei 28 Proben).

Ausgabe: `val_overall` (je Fit: q Median, 5–95 %, Streuung, Trefferquote vs. Raten …), `val_splits`
(je Split und Fit), `val_predictions` (je Split, Fit, Testprobe), `val_per_sample`, `val_membership`
(je Split und Probe: train/test + Bildnamen); in `Proben` die Spalten `val_<fit>_test_count`,
`val_<fit>_hit_rate`. Plots: `val_q_stability`, `val_hit_rate`, `val_per_sample`, `val_split_matrix`
(zeigt die ersten 300 Splits).

---

## 9. Später / offen

1. **M3** (Schwellenregression) als weiteres Modul in `fits/`.
2. Sensitivität: M1 mit `A0_schliff_um2` bzw. mit verschiedenen Porenmodellen vergleichen.
3. Spannung pixelweise statt am Schwerpunkt (z. B. Maximum über die Porenpixel) – geht als Spannungsmodell, die Pixel sind über `sample.pixels(p)` erreichbar.
4. Prüfen, ob Bruchbild und Schliff dieselbe Orientierung haben (außen oben, nicht gespiegelt) – bei `pulsating` wäre ein Vertauschen oben/unten ein echter Fehler.
