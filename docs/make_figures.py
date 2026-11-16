"""Erzeugt die Abbildungen für Q_FIT_ERKLAERT.md (docs/figures/*.png) aus den Testdaten in input/
und aus synthetischen Rissen (aus dem Porenmodell gewürfelt, wie test_data/check_fit.py).
    .venv\\Scripts\\python docs\\make_figures.py
Gibt die Zahlen aus, die im Text stehen.
"""
import dataclasses
import sys
from pathlib import Path

import matplotlib
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from q_fitter.data import Crack, load_all, load_config  # noqa: E402
from q_fitter.fit import Fitter  # noqa: E402
from q_fitter.fitplot import FitPlot  # noqa: E402
from q_fitter.plot import STYLE, SamplePlot  # noqa: E402

OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(exist_ok=True)
METHOD = "area"
EXAMPLE = "S002"                    # ID für die Beispielbilder (3 Schliffe, Biegung)
BLUE, RED, GREY = "#4dabf7", "#e03131", "#868e96"
Q_COLORS = {0: "#adb5bd", 2: "#74c0fc", 5: "#1c7ed6", 10: "#5f3dc4", 20: "#c2255c"}
rng = np.random.default_rng(3)
ZETA = np.linspace(0, 1, 20001)

config = load_config()
config["fit"]["bootstrap"] = 400
samples = load_all(config, report=lambda text: None)
with_stress = [s for s in samples if any(image.ok for image in s.images)]
example = next(s for s in samples if s.id == EXAMPLE)
matplotlib.rcParams.update({**STYLE, "font.size": 10})


def figure(width, height):
    fig = Figure(figsize=(width, height), dpi=130, layout="constrained")
    FigureCanvasAgg(fig)
    return fig


def save(fig, name):
    fig.savefig(OUT / name)
    print("  ", name)


def parts(sample, method=METHOD):
    """(w, g) aller Teile aller Schliffe der ID."""
    images = [image for image in sample.images if image.ok]
    ws, gs = zip(*[(image.parts[method][1], image.parts[method][2]) for image in images])
    return np.concatenate(ws), np.concatenate(gs)


def share_over_g(sample, q, bins):
    w, g = parts(sample)
    v = w * g ** q
    return np.histogram(g, bins, weights=v)[0] / v.sum()


def zeta_with(stress, g):
    """zeta (bei xi = 0.5, äußere Hälfte bevorzugt) mit Spannung g."""
    profile = stress.evaluate(np.full(len(ZETA), 0.5), ZETA) - g
    outer = ZETA >= 0.5
    j = np.flatnonzero(outer)[np.argmin(np.abs(profile[outer]))]
    lo, hi = ZETA[max(j - 1, 0)], ZETA[min(j + 1, len(ZETA) - 1)]
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if (float(stress.evaluate(0.5, lo)) - g) * (float(stress.evaluate(0.5, mid)) - g) <= 0:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def model_cracks(sample, q, n, method=METHOD):
    """n Rissursprünge aus dem Modell mit q (Teil mit Wahrscheinlichkeit w g^q / Σ, gleiche Methode
    wie der Fit)."""
    images = [image for image in sample.images if image.ok]
    w, g = parts(sample, method)
    v = w * g ** q
    chosen = rng.choice(len(v), size=n, p=v / v.sum())
    stress = images[0].stress
    return [Crack(f"C{k + 1}", "synthetic", 0.5, zeta_with(stress, g[i])) for k, i in enumerate(chosen)]


def fixed_cracks(sample, g_values):
    stress = next(image for image in sample.images if image.ok).stress
    return [Crack(f"C{k + 1}", "synthetic", 0.5, zeta_with(stress, g)) for k, g in enumerate(g_values)]


def fit_with(cracks_of, method=METHOD):
    synthetic = [dataclasses.replace(s, cracks=cracks_of(s)) for s in with_stress]
    return Fitter(synthetic, config).fit(method)


print("Abbildungen nach", OUT)

# 1 -------------------------------------------------------------- Spannungsfeld und Poren
fig = figure(10, 3.6)
left, right = fig.subplots(1, 2, width_ratios=[1, 1.3])
zeta = np.linspace(0, 1, 201)
left.plot(zeta, np.abs(2 * zeta - 1), color="black", label="Biegung: g = |2ζ − 1|")
left.plot(zeta, zeta, color=GREY, linestyle="--", label="Zugschwellend: g = ζ")
left.set_xlabel("ζ (0 = innen, 1 = außen)")
left.set_ylabel("relative Spannung g")
left.set_title("Spannungsfeld über die Dicke", loc="left")
left.legend(loc="upper center", fontsize="small")
images = [image for image in example.images if image.ok]
for k, image in enumerate(images):
    area = np.bincount(np.arange(len(image.pore_ids)), minlength=len(image.pore_ids))
    w, g = image.parts["mean"][1], image.parts["mean"][2]
    right.scatter(g, w, s=10, alpha=0.6, label=image.name)
right.set_yscale("log")
right.set_xlabel("Spannung der Pore g (Mittel über die Pore)")
right.set_ylabel("Porenfläche A (px²)")
right.set_title(f"Porenpopulation von {EXAMPLE} (alle Schliffe)", loc="left")
right.legend(fontsize="small", loc="upper left")
save(fig, "1_spannungsfeld_poren.png")

# 2 -------------------------------------------------------------- Gewichtung mit q
fig = figure(10, 3.8)
ax = fig.subplots()
bins = np.linspace(0, 1, 26)
centres = 0.5 * (bins[1:] + bins[:-1])
for q, color in Q_COLORS.items():
    ax.plot(centres, 100 * share_over_g(example, q, bins), "o-", color=color, markersize=3,
            label=f"q = {q}" + ("  (nur Fläche = Porosität)" if q == 0 else ""))
ax.set_xlabel("Spannung g")
ax.set_ylabel("Anteil an Σ A g^q (%)")
ax.set_title(f"Wo liegt das Gewicht Σ A g^q? ({EXAMPLE}, Methode {METHOD})", loc="left")
ax.legend(fontsize="small")
save(fig, "2_gewichtung_q.png")

# 3 -------------------------------------------------------------- u eines Risses
q_demo, g_crack = 5, 0.75
fig = figure(10, 3.8)
left, right = fig.subplots(1, 2)
w, g = parts(example)
v = w * g ** q_demo
hist = np.histogram(g, bins, weights=v)[0] / v.sum()
above = centres >= g_crack
left.bar(bins[:-1], 100 * hist, width=bins[1] - bins[0], align="edge", color=np.where(above, "#ffa8a8", BLUE),
         edgecolor="white")
left.axvline(g_crack, color=RED, linewidth=2)
u_demo = (v[g > g_crack].sum() + 0.5 * v[g == g_crack].sum()) / v.sum()
left.text(g_crack - 0.02, left.get_ylim()[1] * 0.92, f"Rissursprung\ng_c = {g_crack}", color=RED, va="top",
          ha="right")
left.set_xlabel("Spannung g")
left.set_ylabel("Anteil an Σ A g^q (%)")
left.set_title(f"q = {q_demo}: rot = höher belastet als der Riss → u = {u_demo:.2f}", loc="left")
order = np.argsort(g)[::-1]
cumulative = np.cumsum(v[order]) / v.sum()
right.plot(g[order], cumulative, color="black")
right.axvline(g_crack, color=RED, linewidth=2)
right.axhline(u_demo, color=RED, linestyle="--", linewidth=1)
right.plot([g_crack], [u_demo], "o", color=RED)
right.set_xlim(1, 0)
right.set_xlabel("Spannung g (von hoch nach tief)")
right.set_ylabel("Anteil mit Spannung > g")
right.set_title("dasselbe kumuliert: u ablesen", loc="left")
save(fig, "3_u_eines_risses.png")
print(f"   Abb. 3: q = {q_demo}, g_c = {g_crack}, u = {u_demo:.3f}")

# 4 -------------------------------------------------------------- u über q für einen Riss
fig = figure(10, 3.6)
ax = fig.subplots()
qs = np.arange(0, 30.01, 0.1)
for g_c, color in ((0.95, "#c2255c"), (0.75, RED), (0.5, "#f08c00"), (0.25, "#2b8a3e")):
    u = [(w * g ** q)[g > g_c].sum() / (w * g ** q).sum() for q in qs]
    ax.plot(qs, u, color=color, label=f"Riss bei g_c = {g_c}")
ax.axhline(0.5, color="black", linestyle="--", linewidth=0.8)
ax.set_ylim(0, 1)
ax.set_xlim(0, 30)
ax.set_xlabel("q")
ax.set_ylabel("u")
ax.set_title(f"u steigt mit q – umso später, je höher der Riss belastet ist ({EXAMPLE})", loc="left")
ax.legend(fontsize="small", loc="lower right")
save(fig, "4_u_ueber_q.png")

# 5 -------------------------------------------------------------- Gleichverteilung beim richtigen q
q_true = 6
fit = fit_with(lambda s: model_cracks(s, q_true, 60))
fig = figure(10, 3.2)
axes = fig.subplots(1, 3, sharey=True)
for ax, q in zip(axes, (2, q_true, 15)):
    u = fit.u[:, int(np.argmin(np.abs(fit.q - q)))]
    ax.hist(u, bins=np.linspace(0, 1, 11), color=BLUE, edgecolor="white")
    ax.axhline(len(u) / 10, color="black", linestyle="--", linewidth=0.8)
    ax.set_xlabel("u")
    ax.set_title(f"q = {q}: ū = {u.mean():.2f}" + ("  ← richtig" if q == q_true else ""), loc="left")
axes[0].set_ylabel("Anzahl Risse")
save(fig, "5_gleichverteilung.png")
print(f"   Abb. 5: {len(fit.labels)} Risse aus dem Modell mit q = {q_true}; Fit: {fit.describe()}")

# 6 -------------------------------------------------------------- drei Szenarien
scenarios = [
    ("A: alle Risse an der Oberfläche", lambda s: fixed_cracks(s, [0.97, 0.95, 0.98])),
    ("B: Risse wie das Modell mit q = 6", lambda s: model_cracks(s, 6, 3)),
    ("C: Risse tief in der Probe", lambda s: fixed_cracks(s, [0.35, 0.3, 0.45])),
]
fig = figure(12, 6.4)
grid = fig.subplots(2, 3)
for col, (title, cracks_of) in enumerate(scenarios):
    fit = fit_with(cracks_of)
    curve, histogram = grid[0, col], grid[1, col]
    curve.plot(fit.q, fit.u.T, color="#ced4da", linewidth=0.7)
    curve.plot(fit.q, fit.mean, color="black", linewidth=2)
    curve.axhline(0.5, color="black", linestyle="--", linewidth=0.8)
    low = fit.q[0] if fit.low_side else fit.low
    high = fit.q[-1] if fit.high_side else fit.high
    curve.axvspan(low, high, color=RED, alpha=0.12, linewidth=0)
    if not fit.side:
        curve.axvline(fit.q_hat, color=RED)
    curve.set_ylim(0, 1)
    curve.set_xlim(fit.q[0], fit.q[-1])
    curve.set_xlabel("q")
    curve.set_title(title, loc="left", fontsize="medium")
    shown = fit.q_hat if not fit.side else (fit.q[-1] if fit.side == "above" else fit.q[0])
    label = {"": f"q̂ = {fit.q_hat:.1f}", "above": f"q̂ > {fit.q[-1]:g}", "below": f"q̂ ≤ {fit.q[0]:g}"}[fit.side]
    curve.text(0.97, 0.05, label, transform=curve.transAxes, ha="right", color=RED, fontweight="bold")
    hbins = np.linspace(0, 1, 21)
    pores, cracks = fit.distribution(shown, hbins)
    histogram.bar(hbins[:-1], 100 * pores, width=hbins[1] - hbins[0], align="edge", color=BLUE, edgecolor="white")
    histogram.stairs(100 * cracks, hbins, color=RED, linewidth=1.5)
    histogram.set_xlabel("Spannung g")
    histogram.set_title(f"bei q = {shown:.1f}", loc="left", fontsize="medium")
    print(f"   Abb. 6 {title}: {fit.describe()}")
grid[0, 0].set_ylabel("u (grau), ū (schwarz)")
grid[1, 0].set_ylabel("Anteil (%)")
save(fig, "6_szenarien.png")

# 7 -------------------------------------------------------------- wie viele Risse?
q_true, runs = 6, 30
per_id = (1, 2, 4, 10, 20)
estimates, widths = [], []
for n in per_id:
    e, wd = [], []
    for _ in range(runs):
        fit = fit_with(lambda s: model_cracks(s, q_true, n, "centroid"), method="centroid")
        e.append(fit.q_hat)
        wd.append((fit.q[-1] if fit.high_side else fit.high) - (fit.q[0] if fit.low_side else fit.low))
    estimates.append(e)
    widths.append(np.median(wd))
totals = [n * len(with_stress) for n in per_id]
fig = figure(10, 3.6)
left, right = fig.subplots(1, 2)
left.boxplot(estimates, tick_labels=[str(t) for t in totals], whis=(10, 90), showfliers=False)
left.axhline(q_true, color=RED, linestyle="--")
left.set_xlabel("Risse insgesamt")
left.set_ylabel("q̂")
left.set_title(f"q̂ bei q_wahr = {q_true} ({runs} Läufe je Box)", loc="left")
right.plot(totals, widths, "o-", color="black")
right.set_xscale("log")
right.set_xticks(totals, [str(t) for t in totals])
right.set_xlabel("Risse insgesamt")
right.set_ylabel("Breite des 95 %-Bereichs")
right.set_title("Unsicherheit sinkt mit der Rissanzahl", loc="left")
save(fig, "7_risszahl.png")
print("   Abb. 7: Risse", totals, "Breite", [round(float(w), 1) for w in widths])

# 8 -------------------------------------------------------------- das Panel im Programm (Testdaten)
fitter = Fitter(samples, config)
fit = fitter.fit(METHOD)
fig = Figure(figsize=(16, 3.6), dpi=110, layout="constrained")
FigureCanvasAgg(fig)
FitPlot(fig, config["fit"]["bins"]).show(fit, 10.0)
save(fig, "8_panel.png")
print(f"   Abb. 8: Testdaten {fit.describe()}")
for i, label, u in zip(fit.ids, fit.labels, fit.u[:, int(np.argmin(np.abs(fit.q - 10)))]):
    print(f"      {i} {label}: u(q=10) = {u:.2f}")

# 9 -------------------------------------------------------------- Riss mit u im Bild
sample = next(s for s in samples if s.id == "S001")
fig = Figure(dpi=100)
FigureCanvasAgg(fig)
fig.set_size_inches(16, 4)
plot = SamplePlot(fig, sample, config["plot"], fitter)
height = plot.height_for(1600, 700, config["plot"]["min_height_px"])
fig.set_size_inches(16, height / 100)
plot.set_q(10.0, METHOD)
save(fig, "9_riss_im_bild.png")

# 10 ------------------------------------------------------------- die Schranke (Testdaten)
fit = fitter.fit(METHOD)
bound = fit.bound
fig = figure(12, 3.9)
left, middle, right = fig.subplots(1, 3, width_ratios=[1.3, 1, 1])
for k, unit in enumerate(bound.units):
    left.plot(fit.q, bound.value[k], linewidth=1.2, label=unit)
    if np.isfinite(bound.unit_q[k]):
        left.plot(bound.unit_q[k], bound.share, "o", color="black", markersize=4)
left.axhline(bound.share, color="#2b8a3e", linestyle="--")
left.step(fit.q, bound.covered, where="post", color="#2b8a3e", linewidth=2.5, label="Anteil abgedeckter Risse")
left.axvline(bound.q, color="#2b8a3e", linewidth=2)
left.set_xlim(fit.q[0], fit.q[-1])
left.set_ylim(0, 1.02)
left.set_xlabel("q")
left.set_ylabel("u bzw. Anteil")
left.set_title(f"Schranke: q = {bound.q:.1f}, gesetzt von {bound.decisive}", loc="left")
left.legend(fontsize="x-small", loc="lower right")
g_bound = max(fit.crack_g)
hbins = np.linspace(0, 1, 26)
for ax, q, name in ((middle, fit.q_hat, "typisches q̂"), (right, bound.q, "Schranke")):
    pores, cracks = fit.distribution(q, hbins)
    centres_h = 0.5 * (hbins[1:] + hbins[:-1])
    ax.bar(hbins[:-1], 100 * pores, width=hbins[1] - hbins[0], align="edge",
           color=np.where(centres_h >= g_bound, "#8ce99a", BLUE), edgecolor="white")
    ax.plot(fit.crack_g, np.zeros(len(fit.crack_g)), "|", color=RED, markersize=16, markeredgewidth=2, clip_on=False)
    ax.axvline(g_bound, color="#2b8a3e", linewidth=2)
    above = pores[centres_h >= g_bound].sum()
    ax.set_title(f"{name} q = {q:.1f}: {above:.0%} oberhalb\ndes am höchsten belasteten Risses", loc="left")
    ax.set_xlabel("Spannung g")
middle.set_ylabel("Anteil an Σ A g^q (%)")
save(fig, "10_schranke.png")
print(f"   Abb. 10: {bound.describe()}")
