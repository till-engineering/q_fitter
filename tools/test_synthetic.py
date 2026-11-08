"""Test on synthetic data with a known q (and k): generate -> run -> compare with the truth.

    python tools/test_synthetic.py                 noise-free: the crack origin is always the most severe pore
    python tools/test_synthetic.py --k 3           noisy: failure with probability S^k / sum S^k (for M2)
    python tools/test_synthetic.py --q 8 --k 3 --seed 5

All other settings (pore models, stress model, fits, synthetic.source ...) come from config.yaml.
Only for this test: input.dir = the generated folder (daten_synth or daten_synth_k<k>),
exclusion.radius_um = 0 (the synthetic images have random scales). Results: output.dir (ergebnisse/).
"""

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import make_synthetic                                   # noqa: E402
from q_fitter.core.config import load_config            # noqa: E402
from q_fitter.core.pipeline import run                  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--q", type=float, help="q_true (default: synthetic.q_true of config.yaml)")
    parser.add_argument("--k", type=float, help="k_true; leave out = noise-free")
    parser.add_argument("--seed", type=int, help="random seed (default: synthetic.seed)")
    args = parser.parse_args()

    config = load_config()
    syn = config["synthetic"]
    if args.q is not None:
        syn["q_true"] = args.q
    syn["k_true"] = args.k
    if args.seed is not None:
        syn["seed"] = args.seed
    syn["target_dir"] = "daten_synth" if args.k is None else f"daten_synth_k{args.k:g}"
    config["exclusion"]["radius_um"] = 0.0
    config["logging"]["level"] = "WARNING"

    print(f"1/2 generating {syn['target_dir']}/  (q_true = {syn['q_true']:g}, k_true = {syn['k_true']}, seed {syn['seed']})")
    logging.disable(logging.WARNING)              # source images without frame are skipped silently
    with contextlib.redirect_stdout(io.StringIO()):
        make_synthetic.main(config)               # stress fields are taken from the normal input.dir
    logging.disable(logging.NOTSET)
    config["input"]["dir"] = syn["target_dir"]
    print("2/2 evaluating ...")
    out = run(config)

    print(f"\ntruth:  q = {syn['q_true']:g}" + (f",  k = {args.k:g}" if args.k is not None else ",  noise-free"))
    for name, keys in (("m1_overall", ["status", "q lower (max over samples)", "q upper (min over samples)",
                                       "samples with contradicting pores", "samples with lower > upper", "q at V min"]),
                       ("m2_overall", ["q best", "q 95% interval", "k best", "k 95% interval", "warnings"])):
        file = out / f"{name}.json"
        if not file.is_file():
            continue
        values = pd.DataFrame(json.loads(file.read_text(encoding="utf-8"))).set_index("quantity")["value"]
        print(f"\n{name[:2].upper()}:")
        for key in keys:
            value = values.get(key)
            if value not in (None, ""):
                print(f"  {key:36s} {value:.4g}" if isinstance(value, float) else f"  {key:36s} {value}")
    print(f"\nresults: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
