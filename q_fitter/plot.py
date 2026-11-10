"""The plot of one section, as critical_pores of Pore_Detection, but for any q:

left   Pareto: the `top` pores with the largest contribution A g^q (share of the sum in %, colour =
       zone), cumulative share on a second axis
right  the straightened sample (outer surface on top), the top pores numbered, the cracks of the
       labeler as cyan rings with a cross at their xi / zeta

The picture is drawn once; set_q() only redraws the bars and the numbers.
"""

import numpy as np
from matplotlib.figure import Figure

from .data import ZONE_BOUNDARY, Image, Sample

OUTER, INNER = "#d9480f", "#0f6d8c"
CRACK = "#00e5ff"
LABEL, LABEL_TOP = "#ffff00", "#ff1a1a"     # pore numbers: yellow, the 3 largest red
LABEL_PT = (7.0, 11.0)                      # font size of the smallest / largest contribution
LEADER_PT = (12, 20, 30)                    # tried lengths of the line from the number to the pore
TURNS_DEG = (0, 30, -30, 60, -60, 90, -90, 135, -135, 180)
LABEL_ROOM = 0.04
# plot margins in screen px: Pareto (axis labels, two-line title), picture (crack line on top, info below),
# gap = room for the right axis of the Pareto
MARGIN_PX = {"left": 75, "right": 4, "top": 62, "bottom": 78, "gap": 80, "picture_top": 26, "picture_bottom": 22}                         # free border around the picture, share of its long side

STYLE = {
    "axes.edgecolor": "black", "axes.linewidth": 0.8, "axes.grid": False,
    "xtick.direction": "in", "ytick.direction": "in", "xtick.top": True, "ytick.right": True,
    "ytick.minor.visible": True, "legend.frameon": True, "legend.fancybox": False,
    "legend.edgecolor": "black", "legend.framealpha": 1.0, "figure.facecolor": "white",
}


class ImagePlot:
    def __init__(self, figure: Figure, sample: Sample, image: Image, plot: dict):
        self.figure, self.sample, self.image, self.top = figure, sample, image, plot["top"]
        if not image.ok:
            figure.text(0.01, 0.5, f"{image.name}:  {image.note}", va="center", fontsize="large", color="#868e96")
            return
        self.bars = figure.add_subplot()
        self.line = self.bars.twinx()
        self.picture = figure.add_subplot()
        self.numbers = []
        self._draw_picture()

    def _draw_picture(self) -> None:
        ax, image = self.picture, self.image
        ax.imshow(image.picture, interpolation="antialiased")
        height, width = image.picture.shape[:2]
        pad = LABEL_ROOM * max(width, height)
        ax.set_xlim(-pad, width + pad)
        ax.set_ylim(height + pad, -pad)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.minorticks_off()
        ax.tick_params(which="both", top=False, right=False, bottom=False, left=False)
        for crack in self.sample.cracks:
            x, y = image.to_picture(crack.xi, crack.zeta)
            # ring with a cross in the middle: the crack origin itself stays visible
            ax.plot(x, y, marker="o", markersize=11, markerfacecolor="none", markeredgecolor=CRACK,
                    markeredgewidth=1.8, zorder=5)
            ax.plot(x, y, marker="+", markersize=6, color=CRACK, markeredgewidth=1.2, zorder=5)
            ax.annotate(crack.label, (x, y), xytext=(8, 8), textcoords="offset points", color=CRACK,
                        fontsize="medium", fontweight="bold", zorder=5,
                        bbox=dict(boxstyle="round,pad=0.12", facecolor="black", alpha=0.6, linewidth=0))
        cracks = "   ".join(f"{c.label}: ξ {c.xi:.2f}, ζ {c.zeta:.2f}" for c in self.sample.cracks)
        ax.set_title(cracks or "no crack from the labeler", fontsize="medium")
        ax.annotate(image.info, (0.0, 0.0), xycoords="axes fraction", xytext=(0, -2), textcoords="offset points",
                    ha="left", va="top", fontsize="small", color="#495057")

    def set_q(self, q: float) -> None:
        if not self.image.ok:
            return
        image = self.image
        self._layout()
        weighted = image.contributions(q)
        total = weighted.sum()
        phi = total / image.sample_area_px2
        self.bars.cla()
        self.line.cla()
        for number in self.numbers:
            number.remove()
        self.numbers = []
        if len(weighted) == 0 or not np.isfinite(total) or total <= 0:
            self.bars.text(0.5, 0.5, "No pore contributes", ha="center", va="center", transform=self.bars.transAxes)
            self.bars.set_title(f"{image.name}     q = {q:g}", loc="left", fontsize="x-large")
            return
        order = np.argsort(weighted)[::-1]
        shown = order[:self.top]
        share = 100 * weighted[shown] / total
        x = np.arange(len(shown))
        zeta = image.pore_zeta
        self.bars.bar(x, share, color=[OUTER if zeta[i] >= ZONE_BOUNDARY else INNER for i in shown],
                      edgecolor="white", linewidth=0.5)
        self.bars.bar([0], [0], color=OUTER, label="outer zone")
        self.bars.bar([0], [0], color=INNER, label="inner zone")
        self.bars.set_xticks(x, [str(image.pore_ids[i]) for i in shown], rotation=90, fontsize="small")
        self.bars.set_xlim(-0.6, len(shown) - 0.4)
        self.bars.set_xlabel("pore (sorted by contribution)")
        self.bars.set_ylabel("contribution to Σ A g^q (%)")
        self.bars.tick_params(axis="y", which="both", right=False)
        self.bars.tick_params(axis="x", which="both", top=False)

        cumulative = np.cumsum(100 * weighted[order] / total)[:len(shown)]
        self.line.plot(x, cumulative, "o-", color="black", markersize=3.5, linewidth=1.3, label="cumulative")
        self.line.set_ylim(0, 105)
        self.line.yaxis.tick_right()                    # cla() puts the twin axis back to the left
        self.line.yaxis.set_label_position("right")
        self.line.set_ylabel("cumulative share (%)")
        self.line.tick_params(axis="y", which="both", direction="in", right=True, left=False)
        handles = [h + l for h, l in zip(self.bars.get_legend_handles_labels(), self.line.get_legend_handles_labels())]
        self.bars.legend(*handles, loc="center right")
        five = min(5, len(order))
        self.bars.set_title(
            f"{image.name}     q = {q:g}     Φ_q = {phi:.4g}\n{len(weighted)} pores     "
            f"top {five} = {cumulative[five - 1]:.0f} %  ·  top {len(shown)} = {cumulative[-1]:.0f} %",
            loc="left", fontsize="x-large")
        self._number_pores(weighted)

    def _layout(self) -> None:
        """Margins in screen px (independent of the plot size): the picture gets the full height and
        exactly the width its aspect needs (at most half of the plot), the Pareto the rest."""
        width, height = self.figure.get_size_inches() * self.figure.dpi
        m = MARGIN_PX
        xlim, ylim = self.picture.get_xlim(), self.picture.get_ylim()
        aspect = abs(xlim[1] - xlim[0]) / abs(ylim[0] - ylim[1])
        picture_h = height - m["picture_top"] - m["picture_bottom"]
        picture_w = min(aspect * picture_h, 0.5 * width)
        self.picture.set_position([(width - m["right"] - picture_w) / width, m["picture_bottom"] / height,
                                   picture_w / width, picture_h / height])
        left, right = m["left"], width - m["right"] - picture_w - m["gap"]
        box = [left / width, m["bottom"] / height, (right - left) / width, (height - m["top"] - m["bottom"]) / height]
        self.bars.set_position(box)
        self.line.set_position(box)

    def _number_pores(self, weighted: np.ndarray) -> None:
        """Top pores numbered next to them (thin line to the pore); each number takes the first free
        place (direction, line length) – as critical_pores of Pore_Detection."""
        ax, image = self.picture, self.image
        top_share = weighted.max()
        shown = [(rank, i) for rank, i in enumerate(np.argsort(weighted)[::-1][:self.top]) if weighted[i] > 0]
        ax.apply_aspect()
        per_pt = self.figure.dpi / 72
        to_pt = lambda xy: ax.transData.transform(xy) / per_pt          # noqa: E731
        centre = np.array(image.picture.shape[1::-1]) / 2
        taken = [_box(to_pt(image.pore_xy[i]), 4, 4) for _, i in shown]
        for rank, i in shown:
            x, y = image.pore_xy[i]
            size = LABEL_PT[0] + (LABEL_PT[1] - LABEL_PT[0]) * np.sqrt(weighted[i] / top_share)
            text = str(image.pore_ids[i])
            half = (0.31 * size * len(text) + 1, 0.4 * size + 1)
            away = np.array([x, y]) - centre
            away = away / (np.linalg.norm(away) or 1.0) * (1, -1)
            pore = to_pt((x, y))
            offset = None
            for length in LEADER_PT:
                for turn in np.radians(TURNS_DEG):
                    c, s = np.cos(turn), np.sin(turn)
                    candidate = length * np.array([c * away[0] - s * away[1], s * away[0] + c * away[1]])
                    if not any(_overlap(_box(pore + candidate, *half), other) for other in taken):
                        offset = candidate
                        break
                if offset is not None:
                    break
            if offset is None:
                offset = LEADER_PT[0] * away
            taken.append(_box(pore + offset, *half))
            color = LABEL_TOP if rank < 3 else LABEL
            self.numbers.append(ax.annotate(
                text, (x, y), xytext=tuple(offset), textcoords="offset points", ha="center", va="center",
                fontsize=size, color=color,
                arrowprops=dict(arrowstyle="-", color=color, linewidth=0.7, shrinkA=1, shrinkB=2)))


def _box(centre, half_width, half_height):
    x, y = centre
    return x - half_width, y - half_height, x + half_width, y + half_height


def _overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
