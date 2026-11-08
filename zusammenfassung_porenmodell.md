# Porenmodell: Zusammenfassung der Diskussion

Stand: 5. November 2026

---

## 1. Modell und Notation

Der Porenkoeffizient einer Probe ist

$$
\Phi = \sum_i A_i \, z_i^{\,q}, \qquad q > 0
$$

| Symbol | Bedeutung |
|---|---|
| $A_i$ | Fläche der Pore $i$ (aus äquivalentem Durchmesser: $A = \frac{\pi}{4} d^2$) |
| $z_i \in [0,1]$ | dimensionslose Position, $0$ = Mitte, $1$ = Rand |
| $q$ | Gewichtungsexponent, noch nicht kalibriert |
| Index $0$ | rissauslösende Pore (Rissausgang), alle anderen Poren $i = 1 \dots n$ |
| $\sigma_a$ | Randspannungsamplitude |

Unter Biegung gilt $\sigma(z) = \sigma_a z$, sofern $z$ proportional zur Spannung definiert ist (Umlaufbiegung: $z = r/R$; Planbiegung: normierter Abstand zur neutralen Faser, Druckzone ausgenommen). Damit ist $z^q$ eine **Spannungsgewichtung**, und die absolute Schwere einer Pore lautet

$$
S_i = A_i \, (\sigma_a z_i)^q .
$$

---

## 2. Teil A: Wie kritisch sind übersehene Poren? (Detektion)

### Ausgangsfrage

Die Porendetektion findet kleine Poren nicht zuverlässig (Beispiel: 50 % Detektion bei 5 px Äquivalentdurchmesser, 100 % ab 100 px; positionsunabhängig). Wie stark kann eine übersehene Pore den Koeffizienten verfälschen?

### Erkenntnisse

- Bei positionsunabhängiger Detektion ist eine **übersehene Pore am Rand immer der Worst Case**, weil dort $z^q = 1$.
- Für einen Anteil in Prozent braucht man immer eine Bezugsgröße. Statt eines externen $\Phi$ wurde das **Zwei-Poren-System** gewählt: eine übersehene Randpore ($d_m$, $z = 1$) und eine gefundene Pore ($d$, Position $z$). Das ist ein Worst Case; echte Proben mit mehr Poren sind unkritischer.

### Formeln

Anteil der übersehenen Pore am wahren Gesamtwert:

$$
r = \frac{d_m^2}{d_m^2 + d^2 z^q} = \frac{1}{1 + b^2 z^q}, \qquad b = \frac{d}{d_m}
$$

Höhenlinien (Äquivalenzkurven) für einen festen Anteil $r$:

$$
\boxed{\; \frac{d}{d_m}(z) = \sqrt{\frac{1-r}{r}} \cdot z^{-q/2} \;}
$$

| $r$ | Vorfaktor $\sqrt{(1-r)/r}$ | Bedeutung |
|---|---|---|
| 50 % | 1 | reine Äquivalenzkurve: beide Poren tragen gleich viel bei |
| 25 % | 1,73 | |
| 10 % | 3 | typische Gefahrengrenze |
| 5 % | 4,36 | |

- $r$ wird als Dezimalzahl eingegeben (0,1 für 10 %). Bei $r = 1$ wird die Kurve 0, bei $r \to 0$ unendlich; sinnvoll ist $0 < r < 1$.
- 50 % heißt gleicher **Beitrag**, nicht gleiche Größe. Gleich groß und gleich viel Beitrag fallen nur am Rand zusammen.
- Beispiel $q = 2$: Eine doppelt so große Pore zählt bei $z = 2^{-2/q} = 0{,}5$ so viel wie die übersehene Randpore.

### Varianten der Darstellung

- **Normiert** (y-Achse $d/d_m$): gilt für jede Größe der übersehenen Pore. Detektionsgrenzen lassen sich hier nicht eindeutig einzeichnen, weil ihre Lage vom gewählten $d_m$ abhängt.
- **In Pixeln** (y-Achse $d$ in px): mit $d(z) = d_m \sqrt{(1-r)/r} \, z^{-q/2}$, eine Kurve pro übersehbarer Größe $d_m$ (z. B. 5, 10, 20, 50 px). Poren ab 100 px werden nie übersehen und brauchen keine Kurve.
- Detektionsgrenzen betreffen die **übersehene** Pore, nicht die gefundene. Ein Abschneiden des kritischen Bereichs an einer Detektionslinie der gefundenen Pore ist physikalisch falsch.

### Wichtigste Aussagen

- Bei einer gefundenen Pore bis 120 px reicht die Detektion im Zwei-Poren-Worst-Case **nie für garantierte Sicherheit** (bei 10 %), da Randporen knapp unter 100 px übersehen werden können.
- Großes $q$ verschärft das Problem: Das Modell wird randdominiert, und genau dort schaden übersehene Poren am meisten.
- Viele gefundene Poren entschärfen es: Bei $N$ gleichartigen Poren wächst die kritische übersehene Größe etwa mit $\sqrt{N}$.
- Ob ein relativer Fehler relevant ist, hängt davon ab, wie nah $\Phi$ an einer Entscheidungsgrenze liegt.

### Werkzeuge aus diesem Teil

- `zwei_poren_modell.md`: Herleitung und Excel-Anleitung
- `zwei_poren_plot.py`, `zwei_poren_aequivalenz.py`: Python-Plots der Äquivalenzkurven
- Kurzfassungen zum Abtippen (Äquivalenzkurven normiert und in Pixeln)

Excel-Formel für Äquivalenzkurven (r in Zeile 1, z in Spalte A, q in H1):

```
=WURZEL((1-B$1)/B$1)*$A2^(-$H$1/2)
```

---

## 3. Teil B: Kalibrierung von q

### Grundbedingung

Die rissauslösende Pore hat den größten Beitrag:

$$
A_0 \, z_0^{\,q} \ge A_i \, z_i^{\,q}
\quad\Longleftrightarrow\quad
q \, s_i \ge a_i,
\qquad s_i = \ln\frac{z_0}{z_i}, \quad a_i = \ln\frac{A_i}{A_0}, \quad q^*_i = \frac{a_i}{s_i}
$$

- $s_i$: Lagevorteil des Rissausgangs (positiv, wenn er randnäher ist)
- $a_i$: Größenvorteil der Pore $i$ (positiv, wenn sie größer ist)
- $q^*_i$: Wert, bei dem beide Poren gleich viel beitragen (Grenzpunkt). $q^*_i$ ist eine feste Zahl aus Messwerten, keine Unbekannte.

### Fallunterscheidung

| Lage von Pore 0 | Größe von Pore 0 | Vorzeichen | Aussage | Bedeutung |
|---|---|---|---|---|
| randnäher ($z_0 > z_i$) | kleiner ($A_0 < A_i$) | $s_i > 0,\ a_i > 0$ | $q \ge q^*_i$ | Untergrenze |
| weiter innen ($z_0 < z_i$) | größer ($A_0 > A_i$) | $s_i < 0,\ a_i < 0$ | $q \le q^*_i$ | Obergrenze |
| randnäher | größer/gleich | $s_i > 0,\ a_i \le 0$ | – | nicht informativ |
| weiter innen | kleiner/gleich | $s_i < 0,\ a_i \ge 0$ | – | Widerspruch zum Modell |

- Bei gleicher Lage ($s_i = 0$) gibt es keine Aussage über $q$; es muss $a_i \le 0$ gelten.
- **Nur positive $q^*_i$ sind informativ.** Nicht informative Paare und Widersprüche ergeben $q^*_i \le 0$.
- Kompakt: $\operatorname{sgn}(s_i)\,(q - q^*_i) \ge 0$.
- Information entsteht nur, wenn Größe und Lage **gegeneinander arbeiten**. Poren mit gleicher Spannung (gleichem $z$) sagen nichts über $q$.
- Den engsten Bereich liefern Konkurrenzporen auf beiden Seiten, die fast so viel beitragen wie der Rissausgang.

### Kombination über Proben

- Pro Probe: $q_u$ = größte Untergrenze, $q_o$ = kleinste Obergrenze.
- Über alle Proben: **Schnittmenge**, nicht das kleinste Einzelintervall:

$$
\max_{\text{Proben}} q_u \;\le\; q \;\le\; \min_{\text{Proben}} q_o
$$

- Beispiel: Intervalle 5–14, 8–20, 3–11 ergeben 8–11.
- Ist die Schnittmenge leer, widersprechen sich Proben → Zählmethode $V(q)$ und Einzelbetrachtung der Ausreißer.

### Gleichwertige Alternative: systematisches Durchprobieren

Für jedes $q$ auf einem Raster (z. B. 0 bis 20 in 0,05er-Schritten) prüfen, ob der Rissausgang den größten Beitrag hat, und die Fehler zählen:

$$
V(q) = \text{Anzahl Proben, bei denen der Rissausgang nicht gewinnt}
$$

- $V(q) = 0$ entspricht genau der Schnittmenge.
- Vorteile: einfach, robust bei Widersprüchen, funktioniert auch bei erweiterten Modellen ohne geschlossene Formel für $q^*$.
- Systematisch, nicht zufällig raten.

### Darstellung der Bereiche

- Eine Zeile pro Probe, x-Achse $q$: Untergrenzen blau, Obergrenzen rot, Balken für den zulässigen Bereich. Die Überlappung aller Balken ist das zulässige $q$.
- Ergänzend $V(q)$ als Kurve über $q$.

---

## 4. Die Methoden im Plan (M1 bis M4)

| Methode | Idee | Benötigte Daten |
|---|---|---|
| **M1** Paarweise Schranken | Ungleichungen oben, Schnittmenge bzw. $V(q)$ | Rissausgang + alle Poren der Bruchfläche |
| **M2** Konkurrenz-Likelihood | nutzt alle nicht versagten Poren, auch knappe Fälle | Rissausgang + alle Poren der Bruchfläche |
| **M3** Schwellenregression | absolute Spannung über Proben hinweg | nur Rissausgang + $\sigma_a$ |
| **M4** Serienvalidierung | Rangfolge $\bar\Phi_s$ vs. Dauerfestigkeit | Serienwerte, mindestens 5 Serien |

### M2: Likelihood

$$
P(0 \mid q, k) = \frac{(A_0 z_0^q)^k}{\sum_j (A_j z_j^q)^k}, \qquad \ell(q,k) = \sum_{\text{Proben}} \ln P
$$

- $k$ = Schärfe des Versagens ($k \to \infty$ entspricht M1).
- Konfidenzintervall über Profil-Likelihood: $2[\ell_p(\hat q) - \ell_p(q)] \le 3{,}84$.
- Hier zahlen sich die vielen nicht versagten Poren wirklich aus. Bei der harten Methode zählt pro Probe nur die strengste Grenze.

### M3: Schwellenregression (Idee mit lokaler Spannung)

Im Dauerfestigkeitsbereich versagt der Rissausgang bei einer kritischen Schwere:

$$
\ln A_0 = \ln S_{\mathrm{krit}} - q \, \ln(\sigma_a z_0) + \varepsilon
$$

- Steigung der Auftragung $\ln A_0$ über $\ln(\sigma_a z_0)$ ist $-q$.
- Jede gebrochene Probe ist informativ.
- Gebrochene Proben liegen über der Schwelle → zusätzlich Quantilregression der unteren Einhüllenden.
- Braucht ausreichende Spannweite von $\sigma_a z_0$.

### Absicherung (V1 bis V9)

1. Physikalische Plausibilität: $q \approx 4$ (Spannungsintensität $\sigma A^{1/4}$) bis $q \approx 12$ (Murakami $\sigma A^{1/12}$)
2. Methodenkonsistenz M1/M2/M3
3. Gleiches $q$ in Untergruppen (Serie, Lastniveau)
4. Kreuzvalidierung: Rissausgang vorhersagen, Vergleich mit $q = 0$, $q \to \infty$ und Zufall
5. Bootstrap
6. Sensitivität ($A_{\min}$, Bezugspunkt für $z$, unsichere Ursprünge)
7. Simulationsstudie mit bekanntem $q$ (testet die Methode und den nötigen Stichprobenumfang)
8. Residuenanalyse der Widersprüche (Form, Cluster, Oberflächenanschnitt)
9. Summe vs. Maximum vergleichen

### Stichprobenumfang

- Informativ sind nur Proben mit Konfliktpaaren; bei Ermüdung oft nur 20–50 %. Man braucht Unter- **und** Obergrenzen.
- Richtwerte für informative Proben: < 5 grober Bereich, 10–15 brauchbares Intervall, 20–30 belastbarer Wert.
- Mit aktuell ca. 6 Bruchflächen: nur grober Bereich. Empfehlung: Durchläufer hochsetzen, Ziel ca. 30 Bruchflächen, bis dahin mit dem Bereich 4–12 rechnen und Ergebnisse für mehrere $q$ angeben.
- Bei Dauerfestigkeit nach Treppenstufenverfahren (ein Wert pro Serie) ist M1/M2 die Hauptmethode, M4 nur Bestätigung.

### Werkzeuge aus diesem Teil

- `q_kalibrierung.tex` (+ Vorschau-PDF): wissenschaftlicher Plan mit allen Methoden
- `faelle_tabelle.pdf/.tex`: Fallunterscheidung mit Formeln
- `q_grenzen_spielwiese.xlsx`: Einzelprobe (Grenzen live sehen) und Simulation (Konvergenz mit Probenzahl, Regler für Rauschen). Ergebnis: ohne Rauschen haben nur ca. 30–40 % der Proben beide Grenzen; schon bei Rauschen 0,3 kreuzen sich die Grenzen → Likelihood nötig.

---

## 5. Grundsatzfragen

### Summe oder einzelne Pore?

- Für Dauerfestigkeit spricht viel für die **einzelne kritischste Pore** (schwächstes Glied, Murakami $\sqrt{\text{area}_{\max}}$).
- Eine Summe ist sinnvoll bei Porenclustern, statischer Festigkeit oder als Maß bei der Vorhersage ohne Bruchfläche.
- Die Kalibrierung von $q$ bleibt gültig: M1/M2 kalibrieren das Schweremaß $A z^q$ einer einzelnen Pore.
- Bei großem $q$ liegen Summe und Maximum oft nah beieinander.
- Zwischenform zum Mitkalibrieren: $\Phi_p = \left(\sum_i (A_i z_i^q)^p\right)^{1/p}$ mit $p = 1$ (Summe) bis $p \to \infty$ (Maximum).

### Welche Daten braucht man wofür?

| Zweck | Rissausgang | Fläche/Lage Rissausgang | übrige Poren | $\sigma_a$ |
|---|---|---|---|---|
| M1/M2 | ja | ja | ja | nein |
| M3 | ja | ja | nein | ja |
| Ein-Poren-Modell auf geprüfte Proben | ja | ja | nein | ja |
| Ungeprüftes Bauteil bewerten | – | – | – | ja |

### Bruchfläche vs. Schliff

- **Bruchfläche:** richtige Ebene, Rissausgang sichtbar, projizierte Fläche senkrecht zur Spannung (wie bei Murakami). Schwieriger Kontrast; unregelmäßige Poren mit glatter Umhüllenden messen; benachbarte Poren ggf. zusammenfassen.
- **Schliff:** sauberes $A$, aber andere Ebene und zufälliger Anschnitt → Fläche meist zu klein (runde Poren im Mittel etwa 2/3 des größten Querschnitts).
- Typischer Abtrag bei Alu-Druckguss (Erfahrungswerte): Planschleifen 0,1 bis über 1 mm, Feinschleifen 30–100 µm, Polieren wenige µm. Bei Ursprungsporen von einigen hundert µm kann ein großer Teil weggeschliffen sein.
- Gezielte Präparation: in kleinen Schritten schleifen und den größten Wert nehmen; Abtrag mit Messschraube oder Vickers-Eindrücken kontrollieren (Eindrucktiefe ≈ Diagonale/7).
- **Für M1/M2 alle Poren mit demselben Maß messen.** Rissausgang aus Schliff und Konkurrenz aus Bruchfläche verfälscht $q$.
- Empfehlung: Fläche des Rissausgangs primär von der Bruchfläche, Schliffe zur Kontrolle.

### Serienproduktion und Mikro-CT

- Schliffe taugen schlecht für die Serienbewertung (zerstörend, nur eine Ebene).
- **Mikro-CT vor dem Schwingversuch** ist das stärkere Versuchsdesign: alle Poren in 3D im ganzen Prüfvolumen, Rissausgang nach dem Bruch der CT-Pore zuordnen, echte Größe ohne Schleifabtrag, Vorhersage vor dem Versuch als Validierung.
- Auflösung grob 1/1000 bis 1/2000 des Durchmessers (5–10 mm Messstrecke → ca. 5–10 µm Voxel). Detektionsgrenze von etwa 2–3 Voxeln beachten, die Überlegungen aus Teil A bleiben relevant.
- Die bisherigen Daten sind ein Vorversuch: reichen für eine erste M3-Auswertung und einen groben $q$-Bereich und helfen, die CT-Reihe zu planen.

---

## 6. Offene Punkte

1. Umlauf- oder Planbiegung? Davon hängt die korrekte Definition von $z$ ab.
2. Wofür wird $\Phi$ am Ende genutzt: Erklärung geprüfter Proben oder Vorhersage ungeprüfter Bauteile?
3. Wie genau wurden die vorhandenen Schliffe präpariert (Richtung, Abtragstiefe)?
4. Mehr Bruchflächen gewinnen (Durchläufer hochsetzen) oder neue Reihe mit CT planen.
5. Für das kalibrierte $q$ die Detektionsbewertung aus Teil A erneut durchführen.
