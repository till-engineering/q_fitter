"""The plot of one ID: all its sections in one figure.

left   compact Pareto as an overlay of the Paretos of the sections: x = rank in the section; at
       every rank one bar per section side by side, always in the order A, B, C, … (A = first
       section); bar = share of the pore in Σ A g^q of ITS section (%), colour = section, inner zone
       hatched; one cumulative line per section (second axis)
right  the straightened sections (outer surface on top) in a grid, as large as the room allows
       (focus on the pictures); in each its top pores are numbered (rank or pore number) and ALL
       cracks of the ID are drawn (cyan rings with a cross at their xi / zeta)

The layout is in screen px and the Pareto margins are measured from the real texts, so nothing is
cut off at any window size. The pictures are drawn once; set_q() redraws bars, numbers and texts.
"""

import math
import string

import numpy as np
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.transforms import Bbox

from .data import RUN, ZONE_BOUNDARY, Sample

SECTION_COLORS = ("#0f6d8c", "#d9480f", "#2b8a3e", "#7048e8", "#c2255c", "#e67700", "#1c7ed6", "#495057")
INNER_HATCH = "////"
GROUP_WIDTH = 0.82                          # width of the bars of one rank together (1 = no gap)
CRACK = "#00e5ff"
LABEL, LABEL_TOP = "#ffff00", "#ff1a1a"     # pore numbers: yellow, the red_top largest red
LABEL_PT = (7.0, 11.0)                      # font size of the smallest / largest contribution
LEADER_PT = (12, 20, 30)                    # tried lengths of the line from the number to the pore
TURNS_DEG = (0, 30, -30, 60, -60, 90, -90, 135, -135, 180)
LABEL_ROOM = 0.04                           # free border around a picture, share of its long side
# room in font heights (scales with font size): title above / three info lines below a picture
TITLE_LINES, INFO_LINES = 1.9, 4.2
GAP_PT = 12                                 # between the pictures and between Pareto and pictures
PAD_PT = 3                                  # free border at the edge of the figure
FEWER_ROWS_SHARE = 0.75                     # grid with fewer rows if its pictures keep this share of the area
MIN_FONT_PT = 6.0                           # texts that do not fit get smaller, down to this

STYLE = {
    "axes.edgecolor": "black", "axes.linewidth": 0.8, "axes.grid": False,
    "xtick.direction": "in", "ytick.direction": "in", "xtick.top": True, "ytick.right": True,
    "ytick.minor.visible": True, "legend.frameon": True, "legend.fancybox": False,
    "legend.edgecolor": "black", "legend.framealpha": 1.0, "figure.facecolor": "white",
    "hatch.color": "white", "hatch.linewidth": 0.8,
}


def section_letter(k: int) -> str:
    return string.ascii_uppercase[k % 26]


def section_color(k: int) -> str:
    return SECTION_COLORS[k % len(SECTION_COLORS)]


class SamplePlot:
    def __init__(self, figure: Figure, sample: Sample, plot: dict):
        self.figure, self.sample = figure, sample
        self.top, self.font, self.labels = plot["top"], plot["font_size"], plot["picture_labels"]
        self.numbered, self.red = plot["numbered"], plot["red_top"]
        if self.labels not in ("rank", "pore"):
            raise ValueError(f"config.yaml plot.picture_labels: '{self.labels}' – allowed: rank, pore")
        self.share, self.pareto_px = plot["pareto_min_share"], plot["pareto_min_px"]
        self.images = [image for image in sample.images if image.ok]
        if not self.images:
            figure.text(0.01, 0.5, "no section with stress (reasons above)", va="center",
                        fontsize="large", color="#868e96")
            return
        self.bars = figure.add_subplot()
        self.line = self.bars.twinx()
        self.pictures = [figure.add_subplot() for _ in self.images]
        self.infos, self.numbers = [], []
        self.cols = None                            # grid of the pictures, chosen by height_for
        # size of every picture incl. its free border, in picture px
        self.extents = []
        for ax, image in zip(self.pictures, self.images):
            self._draw_picture(ax, image)
            (x0, x1), (y1, y0) = ax.get_xlim(), ax.get_ylim()
            self.extents.append((x1 - x0, y1 - y0))

    @property
    def ok(self) -> bool:
        return bool(self.images)

    # ---------------------------------------------------------------- pictures (drawn once)

    def _draw_picture(self, ax, image) -> None:
        ax.imshow(image.picture, interpolation="antialiased")
        height, width = image.picture.shape[:2]
        pad = LABEL_ROOM * max(width, height)
        ax.set_xlim(-pad, width + pad)
        ax.set_ylim(height + pad, -pad)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.minorticks_off()
        ax.tick_params(which="both", top=False, right=False, bottom=False, left=False)
        k = len(self.infos)
        for spine in ax.spines.values():
            spine.set_edgecolor(section_color(k))
            spine.set_linewidth(2.0)
        for crack in self.sample.cracks:
            x, y = image.to_picture(crack.xi, crack.zeta)
            # ring with a cross in the middle: the crack origin itself stays visible
            ax.plot(x, y, marker="o", markersize=11, markerfacecolor="none", markeredgecolor=CRACK,
                    markeredgewidth=1.8, zorder=5)
            ax.plot(x, y, marker="+", markersize=6, color=CRACK, markeredgewidth=1.2, zorder=5)
            ax.annotate(
                crack.label, (x, y), xytext=(8, 8), textcoords="offset points", color=CRACK,
                fontsize="medium", fontweight="bold", zorder=5,
                bbox=dict(boxstyle="round,pad=0.12", facecolor="black", alpha=0.6, linewidth=0))
        ax.set_title(f"{section_letter(k)}   {image.name}", loc="left", fontsize="medium", fontweight="bold",
                     color=section_color(k), pad=4)
        self.infos.append(ax.annotate("", (0.0, 0.0), xycoords="axes fraction", xytext=(0, -3),
                                      textcoords="offset points", ha="left", va="top", fontsize="small",
                                      color="#495057", linespacing=1.3))

    # ---------------------------------------------------------------- size

    def _geometry(self, width: float, height: float, unit: float, cols: int | None = None) -> dict:
        """Grid of the pictures (cols x rows) right of the narrowest Pareto; every picture as large as
        its cell allows. Of the grids, the one with fewest rows whose pictures are at least
        FEWER_ROWS_SHARE of the largest possible picture area (flat plots, more IDs in view).
        The Pareto then gets all the width the pictures leave.
        cols given: that grid (the one height_for chose, so that the height fits the drawing).
        unit = figure px per logical px (device pixel ratio); `needed` = figure height for the pictures."""
        px_per_pt = self.figure.dpi / self._ratio() / 72 * unit
        font = self.font * px_per_pt
        gap, pad = GAP_PT * px_per_pt, PAD_PT * px_per_pt
        title, info = TITLE_LINES * font, INFO_LINES * font
        pareto = max(self.pareto_px * unit, self.share * width)
        room_w, room_h = width - pareto - gap - pad, height - 2 * pad
        n = len(self.extents)
        grids = []
        for cols in [cols] if cols else range(n, 0, -1):     # fewest rows first
            rows = math.ceil(n / cols)
            cell_w = (room_w - (cols - 1) * gap) / cols
            picture_h = (room_h - (rows - 1) * gap) / rows - title - info
            if cell_w <= 0 or picture_h <= 0:
                continue
            scales = [min(cell_w / w, picture_h / h) for w, h in self.extents]
            area = sum(s * s * w * h for s, (w, h) in zip(scales, self.extents))
            grids.append((area, cols, rows, scales))
        if not grids:
            grids = [(0.0, cols or n, math.ceil(n / (cols or n)), [1e-3] * n)]
        largest = max(area for area, *_ in grids)
        _, cols, rows, scales = next(grid for grid in grids if grid[0] >= FEWER_ROWS_SHARE * largest)
        sizes = [(s * w, s * h) for s, (w, h) in zip(scales, self.extents)]
        col_w = [max(sizes[k][0] for k in range(c, n, cols)) for c in range(cols)]
        row_h = [max(sizes[k][1] for k in range(r * cols, min(n, (r + 1) * cols))) + title + info for r in range(rows)]
        block_w = sum(col_w) + (cols - 1) * gap
        return dict(cols=cols, sizes=sizes, col_w=col_w, row_h=row_h, gap=gap, pad=pad, title=title,
                    x0=width - pad - block_w, needed=sum(row_h) + (rows - 1) * gap + 2 * pad)

    def _ratio(self) -> float:
        return getattr(self.figure.canvas, "device_pixel_ratio", 1) or 1

    def height_for(self, width: float, max_height: float, min_height: float) -> int:
        """Widget height (logical px) for the widget width: the pictures as large as the width and
        max_height allow, at least min_height (room for the Pareto)."""
        if not self.ok:
            return round(min_height / 4)
        geometry = self._geometry(width, max_height, 1.0)
        self.cols, needed = geometry["cols"], geometry["needed"]
        return math.ceil(max(min_height, min(max_height, needed)))

    def _layout(self) -> None:
        width, height = self.figure.get_size_inches() * self.figure.dpi
        g = self._geometry(width, height, self._ratio(), self.cols)
        gap, cols = g["gap"], g["cols"]
        col_x = [g["x0"] + sum(g["col_w"][:c]) + c * gap for c in range(cols)]
        free_h = height - g["needed"]
        renderer = self.figure.canvas.get_renderer()
        for k, (ax, info, (w, h)) in enumerate(zip(self.pictures, self.infos, g["sizes"])):
            row, col = divmod(k, cols)
            left = col_x[col] + (g["col_w"][col] - w) / 2
            top = height - g["pad"] - free_h / 2 - sum(g["row_h"][:row]) - row * gap - g["title"]
            ax.set_position([left / width, (top - h) / height, w / width, h / height])
            room = col_x[col] + g["col_w"][col] + gap / 2 - left       # texts start at the picture
            _shrink_to(info, room, renderer)
            _shrink_to(ax._left_title, room, renderer)
        self._fit_pareto(width, height, g["x0"] - gap, g["pad"], renderer)

    def _fit_pareto(self, width: float, height: float, right: float, pad: float, renderer) -> None:
        """Pareto box such that axes + tick labels + axis labels + title just fill [pad, right] x
        [pad, height - pad]: start with a guess, measure the real texts, correct (three times)."""
        font = self.font * self.figure.dpi / 72
        x0, y0, x1, y1 = 5 * font, 6 * font, right - 5 * font, height - 4 * font
        for _ in range(3):
            box = [x0 / width, y0 / height, max(x1 - x0, 1) / width, max(y1 - y0, 1) / height]
            self.bars.set_position(box)
            self.line.set_position(box)
            used = Bbox.union([ax.get_tightbbox(renderer, for_layout_only=True) for ax in (self.bars, self.line)])
            x0, x1 = x0 + pad - used.x0, x1 + right - used.x1
            y0, y1 = y0 + pad - used.y0, y1 + height - pad - used.y1
            if _ == 0:
                _shrink_to(self.bars._left_title, right - pad - 5 * font, renderer)

    # ---------------------------------------------------------------- per q

    def set_q(self, q: float, method: str = RUN) -> None:
        """Pareto as an overlay of the Paretos of the sections: at rank r the r-th largest pore of
        every section, bars side by side in the order of the sections (always A first, then B, …);
        share = share of the sum of ITS section, one cumulative line per section."""
        if not self.ok:
            return
        per_image = [image.contributions(q, method) for image in self.images]
        totals = np.array([w.sum() for w in per_image])
        area = sum(image.sample_area_px2 for image in self.images)
        usable = [len(w) > 0 and np.isfinite(t) and t > 0 for w, t in zip(per_image, totals)]
        orders = [np.argsort(w)[::-1][:self.top] if ok else np.array([], int) for w, ok in zip(per_image, usable)]

        for number in self.numbers:
            number.remove()
        self.numbers = []
        for image, w, total, order, ok, info in zip(self.images, per_image, totals, orders, usable, self.infos):
            used = image.method(method)
            differs = "" if used == image.run_method else f" (run: {image.run_method})"
            if ok:
                cumulative = np.cumsum(w[order]) / total * 100
                five = min(5, len(order))
                tops = f"top {five} = {cumulative[five - 1]:.0f} %  ·  top {len(order)} = {cumulative[-1]:.0f} %"
            else:
                tops = "no pore contributes"
            info.set_text(f"Φ_q = {total / image.sample_area_px2:.4g}  ·  {len(w)} pores\n{tops}\n"
                          f"{image.info}  ·  {used}{differs}")

        self.bars.cla()
        self.line.cla()
        methods = sorted({image.method(method) for image in self.images})
        title = f"q = {q:g}    Φ_q (ID) = {totals.sum() / area:.4g}\n{len(self.images)} sections  ·  {', '.join(methods)}"
        self.bars.set_title(title, loc="left", fontsize="medium", linespacing=1.3)
        ranks = max(len(order) for order in orders)
        if ranks == 0:
            self.bars.text(0.5, 0.5, "No pore contributes", ha="center", va="center", transform=self.bars.transAxes)
            self.line.set_yticks([])
            self._layout()
            return

        n = len(self.images)
        width = GROUP_WIDTH / n
        legend_room = []                                # (x, top in line coordinates) of everything drawn
        for k, (image, w, total, order) in enumerate(zip(self.images, per_image, totals, orders)):
            if len(order) == 0:
                continue
            x = np.arange(len(order)) + (k - (n - 1) / 2) * width     # section k always at the same place
            share = 100 * w[order] / total
            inner = image.pore_zeta[order] < ZONE_BOUNDARY
            color = section_color(k)
            self.bars.bar(x[~inner], share[~inner], width=width, color=color, edgecolor="white", linewidth=0.4)
            self.bars.bar(x[inner], share[inner], width=width, color=color, edgecolor="white", linewidth=0.4,
                          hatch=INNER_HATCH)
            cumulative = np.cumsum(share)
            self.line.plot(x, cumulative, "o-", color=color, markersize=2.5, linewidth=1.1)
            legend_room.append((x, share))
        for rank in range(1, ranks, 2):                 # every second rank shaded: groups easy to tell apart
            self.bars.axvspan(rank - 0.5, rank + 0.5, color="#f1f3f5", zorder=0, linewidth=0)
        self.bars.set_xticks(np.arange(ranks), minor=True)
        self._rank_labels(ranks)
        self.bars.set_xlim(-0.5, ranks - 0.5)
        self.bars.set_xlabel("rank in its section (bars: " + ", ".join(section_letter(k) for k in range(n)) + ")")
        self.bars.set_ylabel("contribution to Σ A g^q of the section (%)")
        self.bars.tick_params(axis="y", which="both", right=False)
        self.bars.tick_params(axis="x", which="both", top=False)

        self.line.set_ylim(0, 105)
        self.line.yaxis.tick_right()                    # cla() puts the twin axis back to the left
        self.line.yaxis.set_label_position("right")
        self.line.set_ylabel("cumulative share (%)")
        self.line.tick_params(axis="y", which="both", direction="in", right=True, left=False)

        bar_top = self.bars.get_ylim()[1]
        for x, share in legend_room:                    # invisible: lets loc="best" avoid the bars too
            for xb, yb in zip(x, share):
                self.line.plot([xb - width / 2, xb - width / 2, xb + width / 2, xb + width / 2],
                               [0, yb / bar_top * 105] * 2, alpha=0)
        handles = [Patch(color=section_color(k), label=section_letter(k)) for k in range(n)]
        handles += [Patch(facecolor="#868e96", hatch=INNER_HATCH, edgecolor="white", label="inner zone"),
                    Line2D([], [], color="#868e96", marker="o", markersize=2.5, linewidth=1.1, label="cumulative")]
        self.line.legend(handles=handles, loc="best", fontsize="small", ncols=2 if n > 3 else 1)

        self._layout()
        self._rank_labels(ranks)                        # now that the width of the axis is known
        for k, (ax, image, w, order) in enumerate(zip(self.pictures, self.images, per_image, orders)):
            shown = [(rank, i) for rank, i in enumerate(order[:self.numbered]) if w[i] > 0]
            if shown:
                self._number_pores(ax, image, shown, w, w[order[0]])

    def _rank_labels(self, ranks: int) -> None:
        """Rank 1, 2, 3, … under the groups; if they do not fit side by side only 1, 3, 5, … or
        1, 5, 10, … (a small tick at every rank)."""
        width = self.bars.get_position().width * self.figure.get_size_inches()[0] * self.figure.dpi
        needed = 1.6 * 0.6 * self.font * self.figure.dpi / 72 * len(str(ranks))     # px per label
        step = next((s for s in (1, 2, 5, 10, 20, 50) if width / ranks * s >= needed), 100)
        shown = list(range(0, ranks, step)) if step <= 2 else [0] + list(range(step - 1, ranks, step))
        self.bars.set_xticks(shown, [str(r + 1) for r in shown], fontsize="small")

    def _number_pores(self, ax, image, shown, weighted, top_value) -> None:
        """Top pores of the section numbered next to them (thin line to the pore): with their rank
        (= position on the x axis of the Pareto) or their pore number (plot.picture_labels); the red_top
        largest red. Each number takes the first free place (direction, line length) – as
        critical_pores of Pore_Detection."""
        ax.apply_aspect()
        per_pt = self.figure.dpi / 72
        to_pt = lambda xy: ax.transData.transform(xy) / per_pt          # noqa: E731
        centre = np.array(image.picture.shape[1::-1]) / 2
        taken = [_box(to_pt(image.pore_xy[i]), 4, 4) for _, i in shown]
        inside = ax.bbox.extents / per_pt                                # numbers stay on the picture
        for rank, i in shown:
            x, y = image.pore_xy[i]
            size = LABEL_PT[0] + (LABEL_PT[1] - LABEL_PT[0]) * np.sqrt(weighted[i] / top_value)
            text = str(rank + 1) if self.labels == "rank" else str(image.pore_ids[i])
            half = (0.31 * size * len(text) + 1, 0.4 * size + 1)
            away = np.array([x, y]) - centre
            away = away / (np.linalg.norm(away) or 1.0) * (1, -1)
            pore = to_pt((x, y))
            offset = None
            for length in LEADER_PT:
                for turn in np.radians(TURNS_DEG):
                    c, s = np.cos(turn), np.sin(turn)
                    candidate = length * np.array([c * away[0] - s * away[1], s * away[0] + c * away[1]])
                    box = _box(pore + candidate, *half)
                    if _within(box, inside) and not any(_overlap(box, other) for other in taken):
                        offset = candidate
                        break
                if offset is not None:
                    break
            if offset is None:
                offset = LEADER_PT[0] * away
            taken.append(_box(pore + offset, *half))
            color = LABEL_TOP if rank < self.red else LABEL
            self.numbers.append(ax.annotate(
                text, (x, y), xytext=tuple(offset), textcoords="offset points", ha="center", va="center",
                fontsize=size, color=color,
                arrowprops=dict(arrowstyle="-", color=color, linewidth=0.7, shrinkA=1, shrinkB=2)))


def _shrink_to(text, width_px: float, renderer) -> None:
    """Smaller font (down to MIN_FONT_PT) until the text is at most width_px wide; starts from the
    size it was made with, so it grows back when there is room again."""
    if not hasattr(text, "_q_fitter_size"):
        text._q_fitter_size = text.get_fontsize()
    text.set_fontsize(text._q_fitter_size)
    while text.get_window_extent(renderer).width > width_px and text.get_fontsize() > MIN_FONT_PT:
        text.set_fontsize(max(MIN_FONT_PT, text.get_fontsize() - 0.5))


def _box(centre, half_width, half_height):
    x, y = centre
    return x - half_width, y - half_height, x + half_width, y + half_height


def _within(a, b) -> bool:
    return a[0] >= b[0] and a[1] >= b[1] and a[2] <= b[2] and a[3] <= b[3]


def _overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
