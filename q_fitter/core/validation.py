"""Quality control: random train/test splits (config: validation; enabled: false = completely off).

For every split a share test_fraction of the samples is drawn at random (without the outcome):
    1. every fit of the config (M1, M2, ...) is run on the training samples only -> q (and k)
    2. with that q the severity S = A g^q of every pore of each test sample is computed:
         hit     = the crack origin is the most severe pore (rank 1)
         rank    = 1 + number of competitors more severe than the crack origin
         q_share = share of the fitted q range (M1: V minimal, M2: 95 % interval) in which it is rank 1
         p_crack = P(crack origin) = S0^k / sum S^k   (only fits with k, i.e. M2)
         chance  = 1 / (1 + competitors): hit rate of a blind guess
The splits are independent draws; the same split can occur twice. Tables val_*, figures val_*.png.
"""

import logging
import time

import numpy as np
import pandas as pd

from .data import Sample
from .methods import FitResult, Prediction

log = logging.getLogger("q_fitter")
KEYS = ("enabled", "test_fraction", "splits", "seed")


def validate(settings: dict, samples: list[Sample], fits, results) -> FitResult | None:
    if not settings["enabled"]:
        return None
    missing = [key for key in KEYS if key not in settings]
    if missing:
        raise ValueError(f"validation: missing settings {missing} (expected: {list(KEYS)})")
    n = len(samples)
    n_test = int(round(n * float(settings["test_fraction"])))
    if not 1 <= n_test <= n - 1:
        raise ValueError(f"validation: test_fraction {settings['test_fraction']} of {n} samples gives {n_test} "
                         f"test samples - need at least 1 test and 1 training sample")
    n_splits = int(settings["splits"])
    if n_splits < 1:
        raise ValueError("validation: splits must be at least 1")

    used = []                                     # (fit, prediction on all samples)
    for fit, result in zip(fits, results):
        full = fit.prediction(result)
        if full is None:
            log.warning("validation: fit %s gives no prediction - left out", fit.name)
        else:
            used.append((fit, full))
    if not used:
        log.warning("validation: no fit can predict - skipped")
        return None

    parts = [_log_parts(sample) for sample in samples]
    rng = np.random.default_rng(settings["seed"])
    membership, split_rows, pred_rows = [], [], []
    start, step = time.perf_counter(), max(1, n_splits // 10)
    for split in range(1, n_splits + 1):
        is_test = np.zeros(n, bool)
        is_test[rng.choice(n, n_test, replace=False)] = True
        for sample, test in zip(samples, is_test):
            membership.append({"split": split, "ID": sample.id, "role": "test" if test else "train",
                               "images": ", ".join(sample.images)})
        train = [sample for sample, test in zip(samples, is_test) if not test]
        for fit, _ in used:
            pred = fit.prediction(fit.fit(train))
            rows = [] if pred is None else [_predict(parts[i], pred) | {"ID": samples[i].id}
                                            for i in np.flatnonzero(is_test)]
            for row in rows:
                pred_rows.append({"split": split, "fit": fit.name} | row)
            split_rows.append(_split_row(split, fit.name, n - n_test, n_test, pred, rows))
        if split % step == 0 or split == n_splits:
            log.info("validation: %d / %d splits (%.0f s)", split, n_splits, time.perf_counter() - start)

    splits = pd.DataFrame(split_rows)
    predictions = pd.DataFrame(pred_rows, columns=["split", "fit", "ID", "hit", "rank", "competitors", "q_share",
                                                   "p_crack", "chance"])
    membership = pd.DataFrame(membership)
    per_sample = _per_sample(samples, predictions, membership, used)
    overall = _overall(splits, predictions, used, n_test)

    from . import validation_figures as figures
    names = [fit.name for fit, _ in used]
    full = {fit.name: pred for fit, pred in used}
    figs = {"val_q_stability": lambda: figures.plot_q_stability(splits, full, names),
            "val_hit_rate": lambda: figures.plot_hit_rate(splits, names, n_test),
            "val_per_sample": lambda: figures.plot_per_sample(per_sample, names),
            "val_split_matrix": lambda: figures.plot_split_matrix(membership, predictions, names)}
    wide = per_sample.pivot(index="ID", columns="fit", values=["test_count", "hit_rate"])
    wide.columns = [f"val_{fit}_{value}" for value, fit in wide.columns]
    return FitResult(per_sample=wide.reset_index(),
                     tables={"val_overall": overall, "val_splits": splits, "val_predictions": predictions,
                             "val_per_sample": per_sample, "val_membership": membership},
                     figures=figs)


def _log_parts(sample: Sample):
    """ln A and ln g of the crack origin and of the competitors (Schliff pores not excluded)."""
    pores = sample.pores
    crack = sample.crack
    comp = pores[(pores["kind"] == "pore") & ~pores["excluded"]]
    g = comp["g"].to_numpy(float)
    with np.errstate(divide="ignore"):
        return (float(np.log(crack["A_um2"])), float(np.log(crack["g"])) if crack["g"] > 0 else -np.inf,
                np.log(comp["A_um2"].to_numpy(float)), np.where(g > 0, np.log(np.maximum(g, 1e-300)), -np.inf))


def _ln_severity(ln_a, ln_g, q):
    with np.errstate(invalid="ignore"):
        s = ln_a + q * ln_g
    return np.where(np.isnan(s), -np.inf, s)        # g <= 0: severity 0 (also at q = 0)


def _predict(parts, pred: Prediction) -> dict:
    ln_a0, ln_g0, ln_a, ln_g = parts
    s0 = _ln_severity(ln_a0, ln_g0, pred.q)
    s = _ln_severity(ln_a, ln_g, pred.q)
    rank = int(1 + (s > s0).sum())
    q_share = np.nan
    if len(pred.q_values):
        qv = np.asarray(pred.q_values, float)
        s0_v = _ln_severity(ln_a0, ln_g0, qv)                              # (m,)
        s_v = _ln_severity(ln_a[None, :], ln_g[None, :], qv[:, None])      # (m, n)
        q_share = float(((s_v > s0_v[:, None]).sum(axis=1) == 0).mean())
    p = np.nan
    if pred.k is not None:
        if not len(s):
            p = 1.0
        elif not np.isfinite(s0):
            p = 0.0
        else:
            all_s = pred.k * np.append(s, s0)
            m = all_s.max()
            p = float(np.exp(pred.k * s0 - m - np.log(np.exp(all_s - m).sum())))
    return {"hit": rank == 1, "rank": rank, "competitors": len(s), "q_share": q_share, "p_crack": p,
            "chance": 1.0 / (1 + len(s))}


def _split_row(split, fit_name, n_train, n_test, pred: Prediction | None, rows) -> dict:
    row = {"split": split, "fit": fit_name, "n_train": n_train, "n_test": n_test}
    if pred is None:
        return row | {"q": np.nan, "q_low": np.nan, "q_high": np.nan, "k": np.nan, "hits": np.nan,
                      "hit_rate": np.nan, "chance_rate": np.nan, "mean_rank": np.nan, "mean_q_share": np.nan,
                      "mean_p_crack": np.nan, "note": "training gave no q"}
    t = pd.DataFrame(rows)
    qv = np.asarray(pred.q_values, float)
    row |= {"q": pred.q, "q_low": qv.min() if len(qv) else np.nan, "q_high": qv.max() if len(qv) else np.nan,
            "k": np.nan if pred.k is None else pred.k, "hits": int(t["hit"].sum()), "hit_rate": t["hit"].mean(),
            "chance_rate": t["chance"].mean(), "mean_rank": t["rank"].mean(), "mean_q_share": t["q_share"].mean(),
            "mean_p_crack": t["p_crack"].mean(), "note": ""}
    return row | pred.info


def _per_sample(samples, predictions, membership, used) -> pd.DataFrame:
    rows = []
    train_count = membership[membership["role"] == "train"].groupby("ID").size()
    for fit, _ in used:
        p = predictions[predictions["fit"] == fit.name]
        for sample in samples:
            t = p[p["ID"] == sample.id]
            rows.append({"ID": sample.id, "fit": fit.name, "train_count": int(train_count.get(sample.id, 0)),
                         "test_count": len(t), "hits": int(t["hit"].sum()),
                         "hit_rate": t["hit"].mean() if len(t) else np.nan,
                         "mean_rank": t["rank"].mean() if len(t) else np.nan,
                         "max_rank": t["rank"].max() if len(t) else np.nan,
                         "mean_q_share": t["q_share"].mean() if len(t) else np.nan,
                         "mean_p_crack": t["p_crack"].mean() if len(t) else np.nan,
                         "chance": 1.0 / (1 + len(_competitors(sample))),
                         "images": ", ".join(sample.images)})
    return pd.DataFrame(rows)


def _competitors(sample):
    pores = sample.pores
    return pores[(pores["kind"] == "pore") & ~pores["excluded"]]


def _overall(splits, predictions, used, n_test) -> pd.DataFrame:
    rows = []
    for fit, full in used:
        s = splits[splits["fit"] == fit.name]
        p = predictions[predictions["fit"] == fit.name]
        q = s["q"].dropna().to_numpy()
        full_lo, full_hi = (min(full.q_values), max(full.q_values)) if len(full.q_values) else (np.nan, np.nan)
        add = lambda quantity, value, note="": rows.append({"fit": fit.name, "quantity": quantity, "value": value,
                                                            "note": note})
        add("splits", len(s), f"{n_test} test samples each")
        add("splits without q", int(s["q"].isna().sum()), "training gave no q")
        add("q all samples", full.q, "point q of the normal run (all samples)")
        add("q range all samples", f"{full_lo:g}-{full_hi:g}" if np.isfinite(full_lo) else "",
            "M1: V minimal, M2: 95 % interval")
        if len(q):
            add("q median over splits", float(np.median(q)), "")
            add("q 5% / 95% over splits", f"{np.percentile(q, 5):.3g} / {np.percentile(q, 95):.3g}",
                "90 % of the splits give a q in this range")
            add("q std over splits", float(np.std(q)), "small = stable")
            add("q range of the splits contains q all samples",
                float(((s["q_low"] <= full.q) & (full.q <= s["q_high"])).mean()), "share of the splits")
        add("hit rate (all test predictions)", float(p["hit"].mean()) if len(p) else np.nan,
            "crack origin = most severe pore at the q of the training")
        add("chance rate", float(p["chance"].mean()) if len(p) else np.nan, "blind guess: 1 / (1 + competitors)")
        add("splits with hit rate > chance", float((s["hit_rate"] > s["chance_rate"]).mean()), "share of the splits")
        add("mean rank of the crack origin", float(p["rank"].mean()) if len(p) else np.nan, "1 = always the most severe")
        add("mean q_share", float(p["q_share"].mean()) if len(p) else np.nan,
            "share of the trained q range in which the crack origin wins")
        if p["p_crack"].notna().any():
            add("mean P(crack origin)", float(p["p_crack"].mean()), "predicted by the fit (M2)")
    return pd.DataFrame(rows, columns=["fit", "quantity", "value", "note"]).astype({"value": object})
