"""Figures of M1 (used by m1.py; no method of its own).

    plot_bounds     one row per sample: allowed q, contradictions marked
    plot_v          V(q)
    plot_pore_map   all competitors relative to their crack origin: ln(g/g0) vs ln(A/A0)
    plot_sample     the Schliff image(s) of one sample, pores coloured by their M1 role
"""

import matplotlib

matplotlib.use("Agg")
import cv2                          # noqa: E402
import matplotlib.pyplot as plt     # noqa: E402
from matplotlib import patheffects  # noqa: E402
import numpy as np                  # noqa: E402
import pandas as pd                 # noqa: E402

BLUE, ORANGE = "#2a78d6", "#eb6834"             # lower bound, upper bound
BAND, INK, MUTED, GRID = "#cde2fb", "#0b0b0b", "#52514e", "#e4e3df"
CRIT = "#d03b3b"                               # status colour "critical": contradictions
CRIT_BAND, CRIT_HATCH = "#fbecec", "#efb9b9"   # light versions for zones
NEUTRAL, FAINT = "#b4b3ad", "#e2e1dc"          # not informative, excluded

ROLE_COLORS = {"lower": BLUE, "upper": ORANGE, "contradiction": CRIT,
               "not informative": NEUTRAL, "no stress": NEUTRAL, "excluded": FAINT}
ROLE_LABELS = {"lower": "gives lower bound", "upper": "gives upper bound", "contradiction": "contradiction",
               "not informative": "not informative", "excluded": "excluded (near crack origin / model)"}


def _style(ax, grid_axis="x"):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelcolor=INK)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


# ----------------------------------------------------------------------------------------------

def plot_bounds(per_sample: pd.DataFrame, overall: pd.DataFrame, q_max: float):
    """One row per sample: bar from q_u to q_o, lower bound > blue, upper bound < orange.
    Contradictions are drawn, not hidden:
      - contradicting pores in a sample: label "x n contradicting pores" at the right (the bar shows
        the bounds of the other pores)
      - lower > upper in a sample: hatched red between the two bounds
      - samples without contradiction that do not overlap: light red zone over all rows"""
    values = dict(zip(overall["quantity"], overall["value"]))
    table = per_sample.iloc[::-1].reset_index(drop=True)            # first ID on top
    fig, ax = plt.subplots(figsize=(10.5, 1.4 + 0.32 * len(table)))
    lo_ok, hi_ok = values["q lower (samples without contradiction)"], values["q upper (samples without contradiction)"]
    all_ok = values["samples with contradicting pores"] == 0 and values["samples with lower > upper"] == 0
    bold = set()
    if np.isfinite(lo_ok) and lo_ok <= hi_ok:
        ax.axvspan(lo_ok, min(hi_ok, q_max), color=BAND, zorder=0,
                   label="allowed q (all samples)" if all_ok else "allowed q (samples without contradiction)")
    elif np.isfinite(lo_ok):                                         # ok samples do not overlap
        ax.axvspan(hi_ok, min(lo_ok, q_max), facecolor=CRIT_BAND, edgecolor=CRIT_HATCH, hatch="//", linewidth=0,
                   zorder=0, label=f"conflict between samples ({hi_ok:.3g} < q < {lo_ok:.3g})")
        ok = table["m1_status"] == "ok"
        bold = {table.loc[ok, "m1_q_lower"].idxmax(), table.loc[ok, "m1_q_upper"].idxmin()}

    for y, row in table.iterrows():
        q_lo, q_hi = row.m1_q_lower, row.m1_q_upper
        if q_lo <= q_hi:
            ax.plot([q_lo, min(q_hi, q_max)], [y, y], color=MUTED, linewidth=2, solid_capstyle="round", zorder=1)
        else:                                                        # lower > upper within the sample
            ax.add_patch(plt.Rectangle((q_hi, y - 0.25), min(q_lo, q_max) - q_hi, 0.5, facecolor="none",
                                       edgecolor=CRIT, hatch="///", linewidth=1, zorder=1))
        if row.m1_lower_bounds:
            ax.plot([q_lo], [y], ">", color=BLUE, markersize=8, markeredgecolor="white", markeredgewidth=1, zorder=3)
        if q_hi <= q_max:
            ax.plot([q_hi], [y], "<", color=ORANGE, markersize=8, markeredgecolor="white", markeredgewidth=1, zorder=3)
        elif q_lo <= q_max:                                          # no upper bound or beyond the plot
            ax.annotate("", xy=(q_max, y), xytext=(q_max * 0.97, y),
                        arrowprops=dict(arrowstyle="->", color=MUTED, lw=1.5))
        problems = []
        if row.m1_contradictions:
            problems.append(f"{row.m1_contradictions} contradicting pore" + ("s" if row.m1_contradictions > 1 else ""))
        if q_lo > q_hi:
            problems.append("lower > upper")
        if problems:
            ax.text(1.01, y, "✕ " + ", ".join(problems), transform=ax.get_yaxis_transform(), va="center",
                    fontsize=8, color=CRIT, clip_on=False)

    ax.plot([], [], ">", color=BLUE, markersize=8, label="lower bound q_u")
    ax.plot([], [], "<", color=ORANGE, markersize=8, label="upper bound q_o")
    if values["samples with lower > upper"]:
        ax.add_patch(plt.Rectangle((0, 0), 0, 0, facecolor="none", edgecolor=CRIT, hatch="///", label="lower > upper"))
    ax.set_yticks(range(len(table)), table["ID"])
    for index in bold:
        ax.get_yticklabels()[index].set_fontweight("bold")
    ax.set_xlim(0, q_max)
    ax.set_ylim(-0.7, len(table) - 0.3)
    ax.set_xlabel("q")
    if values["status"] == "ok":
        title = (f"M1: allowed q per sample - intersection {values['q lower (max over samples)']:.3g} ... "
                 f"{values['q upper (min over samples)']:.3g}")
    else:
        title = f"M1: allowed q per sample - {values['status']}"
    ax.set_title(title, loc="left", fontsize=11, color=INK, pad=28)
    _style(ax)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=4, frameon=False, fontsize=8)
    fig.tight_layout()
    fig.subplots_adjust(right=0.8)
    return fig


def plot_v(v_table: pd.DataFrame, n: int):
    fig, ax = plt.subplots(figsize=(9, 3.2))
    ax.step(v_table["q"], v_table["V"], where="mid", color=BLUE, linewidth=2)
    v_min = v_table["V"].min()
    at_min = v_table["V"] == v_min
    ax.fill_between(v_table["q"], 0, max(n, 1) + 0.5, where=at_min, step="mid", color=BAND, zorder=0,
                    label=f"V = {v_min} (minimum)")
    ax.set_xlim(v_table["q"].iloc[0], v_table["q"].iloc[-1])
    ax.set_ylim(0, max(n, 1) + 0.5)
    ax.yaxis.get_major_locator().set_params(integer=True)
    ax.set_xlabel("q")
    ax.set_ylabel("samples violated")
    ax.set_title(f"M1: V(q) - samples whose crack origin does not win (of {n})", loc="left", fontsize=11, color=INK)
    _style(ax)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.legend(loc="upper right", frameon=False, fontsize=8)
    fig.tight_layout()
    return fig


# ----------------------------------------------------------------------------------------------

def plot_pore_map(pores: pd.DataFrame, overall: pd.DataFrame, label_max: int = 25):
    """Every competitor of every sample as a point relative to ITS crack origin:
        x = ln(g_i / g0)   > 0: competitor under higher stress than the crack origin
        y = ln(A_i / A0)   > 0: competitor larger than the crack origin
    At a given q the crack origin wins against the pore if y < -q x: below the line through the origin
    with slope -q. Top right (larger AND higher stress) the pore wins at every q -> contradiction."""
    values = dict(zip(overall["quantity"], overall["value"]))
    data = pores[pores["m1_bound"].isin(["lower", "upper", "contradiction", "not informative"])].copy()
    data["x"], data["y"] = -data["m1_s"], data["m1_a"]
    data = data[np.isfinite(data["x"]) & np.isfinite(data["y"])]
    fig, ax = plt.subplots(figsize=(8.5, 6.5))
    if data.empty:
        ax.text(0.5, 0.5, "no competitors", ha="center", transform=ax.transAxes)
        return fig
    span_x = max(np.percentile(np.abs(data["x"]), 99.5), 0.05) * 1.15
    span_y = max(np.percentile(np.abs(data["y"]), 99.5), 0.5) * 1.1
    ax.add_patch(plt.Rectangle((0, 0), span_x, span_y, facecolor=CRIT_BAND, edgecolor="none", zorder=0))
    ax.axhline(0, color=MUTED, linewidth=0.8, zorder=1)
    ax.axvline(0, color=MUTED, linewidth=0.8, zorder=1)
    for role in ("not informative", "lower", "upper", "contradiction"):
        part = data[data["m1_bound"] == role]
        if len(part):
            ax.scatter(part["x"], part["y"], s=14 if role == "not informative" else 26, color=ROLE_COLORS[role],
                       edgecolors="white", linewidths=0.5, zorder=3 if role != "not informative" else 2,
                       label=f"{ROLE_LABELS[role]} ({len(part)})")
    xs = np.array([-span_x, span_x])
    for key, color, name in (("q lower (samples without contradiction)", BLUE, "q_u"),
                             ("q upper (samples without contradiction)", ORANGE, "q_o")):
        q = values.get(key)
        if q is not None and np.isfinite(q) and q > 0:
            ax.plot(xs, -q * xs, color=color, linestyle="--", linewidth=1.2, zorder=2,
                    label=f"crack origin wins below the line: {name} = {q:.3g}")
    contra = data[data["m1_bound"] == "contradiction"]
    if 0 < len(contra) <= label_max:
        for _, p in contra.iterrows():
            ax.annotate(f"{p['ID']} {p['pore_id'].split(':')[-1]}", (p["x"], p["y"]), xytext=(4, 3),
                        textcoords="offset points", fontsize=7, color=INK)
    kw = dict(fontsize=8, color=MUTED, transform=ax.transAxes)
    ax.text(0.99, 0.98, "larger AND higher stress\n= contradiction (no q works)", ha="right", va="top", **kw)
    ax.text(0.01, 0.98, "larger, lower stress\n= lower bound", ha="left", va="top", **kw)
    ax.text(0.99, 0.02, "smaller, higher stress\n= upper bound", ha="right", va="bottom", **kw)
    ax.text(0.01, 0.02, "smaller, lower stress\n= no information", ha="left", va="bottom", **kw)
    ax.set_xlim(-span_x, span_x)
    ax.set_ylim(-span_y, span_y)
    ax.set_xlabel("ln(g_i / g_0)   (> 0: competitor under higher stress)")
    ax.set_ylabel("ln(A_i / A_0)   (> 0: competitor larger)")
    ax.set_title("M1: every competitor relative to its crack origin (all samples)", loc="left", fontsize=11, color=INK)
    _style(ax, grid_axis="both")
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.11), ncol=2, frameon=False, fontsize=8)
    fig.tight_layout()
    return fig


# ----------------------------------------------------------------------------------------------

def plot_sample(sample, pores: pd.DataFrame, row: dict, max_px: int):
    """The Schliff image(s) of one sample: every pore coloured by its role in M1, the pores that set
    the bounds and the contradicting pores ringed and labelled, the crack origin as cross + circle of
    its area A0 (it lies in the fracture plane, shown at its xi, zeta), the sample frame."""
    images = list(sample.images.values())
    fig, axes = plt.subplots(len(images), 1, figsize=(10, 1.6 + 7.5 * len(images)), squeeze=False)
    crack = pores[pores["kind"] == "crack"].iloc[0]
    order = ["excluded", "not informative", "lower", "upper", "contradiction"]
    colors = ["#ffffff"] + [ROLE_COLORS[r] for r in order]
    lut_rgb = np.array([tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in colors], np.uint8)

    for ax, image in zip(axes[:, 0], images):
        height, width = image.labels.shape
        category = np.zeros(int(image.labels.max()) + 1, np.uint8)
        mine = pores[(pores["kind"] == "pore") & (pores["image"] == image.name)]
        for _, p in mine.iterrows():
            role = "not informative" if p["m1_bound"] == "no stress" else p["m1_bound"]
            category[list(p["labels"])] = order.index(role) + 1
        scale = min(1.0, max_px / max(height, width))
        view = category[image.labels] if scale == 1.0 else cv2.resize(
            category[image.labels], (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_NEAREST)
        ax.imshow(lut_rgb[view], extent=(-0.5, width - 0.5, height - 0.5, -0.5), interpolation="nearest")

        corners = np.array([[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]], float)
        fy, fx = image.to_image_px(corners[:, 0], corners[:, 1])
        ax.plot(fx, fy, color=MUTED, linewidth=1)
        for zeta, text in ((1.0, "outer"), (0.0, "inner")):
            ty, tx = image.to_image_px(0.5, zeta)
            ax.text(tx, ty, text, fontsize=8, color=MUTED, ha="center", va="bottom" if zeta else "top")

        cy, cx = image.to_image_px(crack["xi"], crack["zeta"])
        ring_min = 0.012 * max(height, width)
        special = {row.get("m1_lower_by"): f"q ≥ {row['m1_q_lower']:.3g}",
                   row.get("m1_upper_by"): f"q ≤ {row['m1_q_upper']:.3g}"}
        for _, p in mine.iterrows():
            if p["m1_bound"] != "contradiction" and p["pore_id"] not in special:
                continue
            py, px = image.to_image_px(p["xi"], p["zeta"])
            radius = max(np.sqrt(p["A_um2"] / np.pi) / image.pixel_size_um * 1.4, ring_min)
            color = ROLE_COLORS.get(p["m1_bound"], INK)
            ax.add_patch(plt.Circle((px, py), radius, fill=False, edgecolor=color, linewidth=1.5))
            text = special.get(p["pore_id"], "✕ contradiction")
            if crack["g"] > 0:
                text += f"\nA/A0 ={p['A_um2'] / crack['A_um2']:.2g}, g/g0 = {p['g'] / crack['g']:.2g}"
            # label on the side facing away from the crack origin, so it never covers it
            dx, dy = px - cx, py - cy
            norm = np.hypot(dx, dy) or 1.0
            ux, uy = dx / norm, dy / norm
            ax.annotate(text, (px + ux * radius, py + uy * radius), xytext=(ux * 18, -uy * 18),
                        textcoords="offset points", ha="left" if ux >= 0 else "right",
                        va="bottom" if uy <= 0 else "top", fontsize=7, color=INK,
                        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor=color, linewidth=0.8),
                        arrowprops=dict(arrowstyle="-", color=color, linewidth=0.8))

        r0 = np.sqrt(crack["A_um2"] / np.pi) / image.pixel_size_um
        halo = [patheffects.withStroke(linewidth=4, foreground="white")]     # visible on top of everything
        ax.add_patch(plt.Circle((cx, cy), r0, fill=False, edgecolor=INK, linewidth=1.2, linestyle="--", zorder=10,
                                path_effects=halo))
        ax.plot([cx], [cy], "+", color=INK, markersize=16, markeredgewidth=2, zorder=11, path_effects=halo)
        ax.annotate("crack origin", (cx, cy), xytext=(8, -14), textcoords="offset points", fontsize=8,
                    fontweight="bold", color=INK, zorder=11, path_effects=halo)
        ax.set_xlim(min(-0.5, fx.min()) - 0.02 * width, max(width - 0.5, fx.max()) + 0.02 * width)
        ax.set_ylim(max(height - 0.5, fy.max()) + 0.02 * height, min(-0.5, fy.min()) - 0.02 * height)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_title(image.name, loc="left", fontsize=9, color=MUTED)

    status = row["m1_status"]
    q_text = f"q_u = {row['m1_q_lower']:.3g}, q_o = " + (f"{row['m1_q_upper']:.3g}" if np.isfinite(row["m1_q_upper"]) else "none")
    fig.suptitle(f"{sample.id}: {status} - {q_text} - {row['m1_contradictions']} contradicting pores",
                 x=0.02, ha="left", fontsize=11, color=CRIT if status != "ok" else INK)
    handles = [plt.Line2D([], [], marker="s", linestyle="", markersize=8, color=ROLE_COLORS[r], label=ROLE_LABELS[r])
               for r in ("lower", "upper", "contradiction", "not informative", "excluded")]
    handles.append(plt.Line2D([], [], marker="+", linestyle="--", color=INK, markersize=10,
                              label="crack origin: position xi, zeta + circle of area A0"))
    fig.legend(handles=handles, loc="lower left", ncol=3, frameon=False, fontsize=8, bbox_to_anchor=(0.02, 0.0))
    fig.tight_layout(rect=(0, 0.05, 1, 0.97))
    return fig
