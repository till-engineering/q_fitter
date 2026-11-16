"""Test only: renders the plot of every ID (as in the window) without a window, for several window
widths, to test_data/rendered/<ID>_w<width>.png – to check the layout (nothing cut off, pictures
large, Pareto compact). Also checks that every text lies inside the figure.
    .venv\\Scripts\\python test_data\\render_plots.py [q] [method]
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

import matplotlib
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.transforms import Bbox

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from q_fitter.data import RUN, load_all, load_config  # noqa: E402
from q_fitter.plot import STYLE, SamplePlot  # noqa: E402

WIDTHS = (1000, 1600, 2400)         # plot width in px (window width minus the margins)
VISIBLE_HEIGHT = 900                # visible height of the scroll area
OUT = Path(__file__).resolve().parent / "rendered"

q = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
method = sys.argv[2] if len(sys.argv) > 2 else RUN
config = load_config()
plot = config["plot"]
OUT.mkdir(exist_ok=True)
problems = 0
for sample in load_all(config, report=lambda text: None):
    for width in WIDTHS:
        with matplotlib.rc_context({**STYLE, "font.size": plot["font_size"]}):
            figure = Figure(dpi=100)
            canvas = FigureCanvasAgg(figure)
            figure.set_size_inches(width / 100, 4)
            sample_plot = SamplePlot(figure, sample, plot)
            max_height = max(plot["min_height_px"], plot["max_height_ratio"] * VISIBLE_HEIGHT)
            height = sample_plot.height_for(width, max_height, plot["min_height_px"])
            figure.set_size_inches(width / 100, height / 100)
            sample_plot.set_q(q, method)
            canvas.draw()
            renderer = canvas.get_renderer()
            # what is really drawn of every part (axes + its texts): inside the figure, no overlaps
            found = []
            if sample_plot.ok:
                parts = {"Pareto": Bbox.union([ax.get_tightbbox(renderer) for ax in (sample_plot.bars, sample_plot.line)])}
                parts.update({image.name: ax.get_tightbbox(renderer)
                              for image, ax in zip(sample_plot.images, sample_plot.pictures)})
                for name, box in parts.items():
                    if box.x0 < -0.5 or box.y0 < -0.5 or box.x1 > width + 0.5 or box.y1 > height + 0.5:
                        found.append(f"{name} cut off")
                names = list(parts)
                for i, a in enumerate(names):
                    for b in names[i + 1:]:
                        if parts[a].overlaps(parts[b]):
                            found.append(f"{a} overlaps {b}")
            figure.savefig(OUT / f"{sample.id}_w{width}.png")
        problems += len(found)
        note = f"   PROBLEM: {'; '.join(found)}" if found else ""
        print(f"{sample.id} width {width}: {width} x {height} px{note}")
print(f"{problems} problem(s); pictures in {OUT}")
