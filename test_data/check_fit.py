"""Check of the fit of q (q_fitter/fit.py): cracks are drawn from the pore model itself with a known
q_true (origin at a part with probability w g^q / Σ w g^q, placed at a point of the section with that
stress); the fit must find q_true again, and the 95 % interval must contain it in about 95 % of the
runs. Uses the pore results in input/pores (the real cracks are ignored).
    .venv\\Scripts\\python test_data\\check_fit.py [method]
"""
import dataclasses
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from q_fitter.data import Crack, load_all, load_config  # noqa: E402
from q_fitter.fit import Fitter  # noqa: E402

Q_TRUE = (1.0, 3.0, 6.0, 12.0)
CRACKS_PER_ID = (1, 3, 20)
RUNS = 40                           # runs per (q_true, cracks per ID) for the coverage of the interval

method = sys.argv[1] if len(sys.argv) > 1 else "area"
config = load_config()
config["fit"]["bootstrap"] = 400    # faster; enough for the check
samples = [s for s in load_all(config, report=lambda text: None) if any(image.ok for image in s.images)]
rng = np.random.default_rng(7)
ZETA = np.linspace(0, 1, 20001)


def draw_cracks(sample, q, n):
    """n crack origins of the sample drawn from the model with q (stress -> a point with that stress)."""
    images = [image for image in sample.images if image.ok]
    parts = [image.parts[image.method(method)] for image in images]
    values = [w * g ** q for _, w, g in parts]
    totals = np.array([v.sum() for v in values])
    cracks = []
    for k in range(n):
        s = rng.choice(len(images), p=totals / totals.sum())
        i = rng.choice(len(values[s]), p=values[s] / totals[s])
        g = parts[s][2][i]
        cracks.append(Crack(f"C{k + 1}", "synthetic", 0.5, _zeta_with(images[s].stress, g)))
    return cracks


def _zeta_with(stress, g) -> float:
    """zeta at xi = 0.5 where the field has exactly the stress g (grid, then bisection)."""
    profile = stress.evaluate(np.full(len(ZETA), 0.5), ZETA) - g
    j = int(np.argmin(np.abs(profile)))
    for a, b in ((j - 1, j), (j, j + 1)):
        if 0 <= a and b < len(ZETA) and profile[a] * profile[b] <= 0:
            lo, hi = ZETA[a], ZETA[b]
            f_lo = profile[a]
            for _ in range(60):
                mid = 0.5 * (lo + hi)
                f_mid = float(stress.evaluate(0.5, mid)) - g
                if f_lo * f_mid <= 0:
                    hi = mid
                else:
                    lo, f_lo = mid, f_mid
            return 0.5 * (lo + hi)
    return float(ZETA[j])


print(f"method {method}, {len(samples)} IDs, {RUNS} runs each")
print(f"{'q_true':>6} {'cracks/ID':>9} {'median q̂':>9} {'q̂ 10…90 %':>14} {'interval width':>14} {'covered':>8}"
      f" {'IDs spread covers':>18}")
for q_true in Q_TRUE:
    for n in CRACKS_PER_ID:
        estimates, widths, covered, spread = [], [], 0, 0
        for _ in range(RUNS):
            synthetic = [dataclasses.replace(s, cracks=draw_cracks(s, q_true, n)) for s in samples]
            fit = Fitter(synthetic, config).fit(method)
            estimates.append(fit.q_hat)
            widths.append(fit.high - fit.low)
            covered += bool((fit.low <= q_true or fit.low_side) and (q_true <= fit.high or fit.high_side))
            spread += fit.spread[0] <= q_true <= fit.spread[1]
        lo, med, hi = np.percentile(estimates, [10, 50, 90])
        print(f"{q_true:6g} {n:9d} {med:9.2f} {lo:6.2f} … {hi:5.2f} {np.median(widths):14.2f} {covered / RUNS:8.0%} {spread / RUNS:18.0%}")
