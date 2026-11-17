"""Check of the fit (FIT.md): curves made from the model with a known q must give that q back,
exactly as the model curve and approximately as its cubic fit (as made in Excel).

    .venv\\Scripts\\python test_data\\check_fit.py [method]
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from q_fitter.data import RUN, load_all, load_config  # noqa: E402
from q_fitter.fit import Curve, Fitter  # noqa: E402

method = sys.argv[1] if len(sys.argv) > 1 else RUN
config = load_config()
fitter = Fitter(load_all(config), config)
problems = 0
for q_true in (1.0, 3.0, 8.0, 20.0):
    exact = fitter.model(q_true, method)
    cubic = np.polyval(np.polyfit(fitter.grid, exact, 3), fitter.grid)
    fitter.curves = [Curve("exact", "", "", exact), Curve("cubic", "", "", cubic)]
    fitter._fits.clear()
    fit = fitter.fit(method)
    exact_q, cubic_q = fit.results[0].q, fit.results[1].q
    ok = abs(exact_q - q_true) < 1e-3
    problems += not ok
    print(f"q = {q_true:5.1f}: exact -> {exact_q:7.3f} ({'ok' if ok else 'WRONG'}),  "
          f"cubic -> {cubic_q:7.3f} (RMS {fit.results[1].rms * 100:.1f} %)")

# field reaches only 0.98: the curve (to 1) is compared conditional on [g_min, 0.98] -> same q
full = fitter
config["fit"]["g_max"] = 0.98                  # same effect as a field whose maximum is 0.98
short = Fitter(full.samples, config)
for q_true in (3.0, 8.0, 20.0):
    curve = np.interp(short.grid, full.grid, full.model(q_true, method))      # the curve up to 1, cut
    curve = (curve - curve[0]) / (curve[-1] - curve[0])
    short.curves = [Curve("cut", "", "", curve)]
    short._fits.clear()
    q_fit = short.fit(method).results[0].q
    ok = abs(q_fit - q_true) < 0.02 * q_true
    problems += not ok
    print(f"q = {q_true:5.1f}, compared up to g = {short.g_top}: -> {q_fit:7.3f} ({'ok' if ok else 'WRONG'})")
print(f"{problems} problem(s)")
