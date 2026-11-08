"""Figures of the quality control (used by validation.py).

    plot_q_stability    the fitted q interval of every split (x = split), median and mean of its ends
    plot_hit_rate       hit rate of the splits vs. the rate of a blind guess
    plot_per_sample     per sample: share of its test predictions that were hits
    plot_split_matrix   split x sample: training / test hit / test miss
"""

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt                  # noqa: E402
from matplotlib.colors import ListedColormap     # noqa: E402
import numpy as np                               # noqa: E402

BLUE, ORANGE, CRIT = "#2a78d6", "#eb6834", "#d03b3b"
INK, MUTED, GRID, FAINT, NEUTRAL = "#0b0b0b", "#52514e", "#e4e3df", "#e2e1dc", "#b4b3ad"
MAX_MATRIX_SPLITS = 300


def _style(ax, grid_axis="both"):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelcolor=INK)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def plot_q_stability(splits, full, names):
    """x = split number, y = q: lower and upper end of the fitted q interval of every split as points;
    horizontal lines = median (solid) and mean (dashed) of the lower and of the upper end."""
    fig, axes = plt.subplots(len(names), 1, figsize=(11, 4.2 * len(names)), squeeze=False)
    for ax, name in zip(axes[:, 0], names):
        s = splits[(splits["fit"] == name) & splits["q_low"].notna()]
        if len(s):
            width = 1.0
            size = max(2, min(5, 500 / len(s)))
            for column, color, label in (("q_low", BLUE, "lower end"), ("q_high", ORANGE, "upper end")):
                ax.plot(s["split"], s[column], "o", color=color, markersize=size, linestyle="none",
                        label=f"{label} of the split")
                med, mean = float(s[column].median()), float(s[column].mean())
                ax.axhline(med, color=INK, linewidth=0.7, label=f"{label}: median {med:.3g}")
                ax.axhline(mean, color=INK, linewidth=0.7, linestyle="--", label=f"{label}: mean {mean:.3g}")
            ax.set_xlim(0.5 - width, s["split"].max() + 0.5 + width)
        kind = "V minimal" if name == "m1" else "95 % interval" if name == "m2" else "fitted range"
        ax.set_title(f"{name}: q interval ({kind}) fitted on the training samples of each split",
                     loc="left", fontsize=10, color=INK)
        ax.set_xlabel("split")
        ax.set_ylabel("q")
        ax.legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(1.0, 1.0))
        _style(ax, "y")
    fig.tight_layout()
    return fig


def plot_hit_rate(splits, names, n_test):
    fig, axes = plt.subplots(1, len(names), figsize=(6.5 * len(names), 4.5), squeeze=False)
    bins = (np.arange(n_test + 2) - 0.5) / n_test
    for ax, name in zip(axes[0], names):
        s = splits[(splits["fit"] == name) & splits["hit_rate"].notna()]
        ax.hist(s["hit_rate"], bins=bins, color=BLUE, rwidth=0.85)
        chance, mean = s["chance_rate"].mean(), s["hit_rate"].mean()
        ax.axvline(chance, color=MUTED, linestyle="--", linewidth=1.2, label=f"blind guess {chance:.0%}")
        ax.axvline(mean, color=INK, linewidth=1.5, label=f"mean hit rate {mean:.0%}")
        ax.set_xlim(-0.5 / n_test, 1 + 0.5 / n_test)
        ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
        ax.set_xlabel(f"hit rate of a split ({n_test} test samples)")
        ax.set_ylabel("splits")
        ax.set_title(f"{name}: crack origin predicted as the most severe pore", loc="left", fontsize=10, color=INK)
        ax.legend(frameon=False, fontsize=8, loc="upper left")
        _style(ax, "y")
    fig.tight_layout()
    return fig


def plot_per_sample(per_sample, names):
    ids = list(dict.fromkeys(per_sample["ID"]))
    fig, ax = plt.subplots(figsize=(9, max(3, 0.32 * len(ids) * max(1, len(names) * 0.7) + 1.2)))
    height = 0.8 / len(names)
    colors = [BLUE, "#eb6834", "#5a9e4b", "#8a5ac2"]
    y0 = np.arange(len(ids))[::-1]
    for j, name in enumerate(names):
        t = per_sample[per_sample["fit"] == name].set_index("ID").loc[ids]
        y = y0 + 0.4 - height * (j + 0.5)
        ax.barh(y, t["hit_rate"].fillna(0), height=height * 0.9, color=colors[j % len(colors)], label=name)
        for yi, (rate, count) in zip(y, zip(t["hit_rate"], t["test_count"])):
            text = "never test" if count == 0 else f"{rate:.0%} of {count}"
            ax.text(1.01, yi, text, va="center", fontsize=7, color=MUTED)
    chance = per_sample.drop_duplicates("ID").set_index("ID").loc[ids, "chance"]
    ax.plot(chance, y0, "|", color=INK, markersize=10, label="blind guess")
    ax.set_yticks(y0, ids, fontsize=8)
    ax.set_xlim(0, 1.15)
    ax.set_xticks(np.linspace(0, 1, 6))
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_xlabel("share of the test predictions of this sample that were hits")
    ax.set_title("Hits per sample (low = sample does not fit the q of the others)", loc="left", fontsize=10, color=INK)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    _style(ax, "x")
    fig.tight_layout()
    return fig


def plot_split_matrix(membership, predictions, names):
    ids = list(dict.fromkeys(membership["ID"]))
    n_splits = int(membership["split"].max())
    shown = min(n_splits, MAX_MATRIX_SPLITS)
    fig, axes = plt.subplots(1, len(names), figsize=(max(5, 0.28 * len(ids) + 2) * len(names), max(4, 0.03 * shown + 2.5)),
                             squeeze=False)
    cmap = ListedColormap([FAINT, BLUE, CRIT])
    col = {sample_id: i for i, sample_id in enumerate(ids)}
    for ax, name in zip(axes[0], names):
        grid = np.zeros((shown, len(ids)))
        p = predictions[(predictions["fit"] == name) & (predictions["split"] <= shown)]
        grid[p["split"].to_numpy() - 1, p["ID"].map(col).to_numpy()] = np.where(p["hit"], 1, 2)
        ax.imshow(grid, cmap=cmap, vmin=0, vmax=2, aspect="auto", interpolation="nearest")
        ax.set_xticks(range(len(ids)), ids, rotation=90, fontsize=7)
        ax.set_ylabel("split")
        title = f"{name}: grey = training, blue = test hit, red = test miss"
        if shown < n_splits:
            title += f"  (first {shown} of {n_splits} splits)"
        ax.set_title(title, loc="left", fontsize=10, color=INK)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    fig.tight_layout()
    return fig
