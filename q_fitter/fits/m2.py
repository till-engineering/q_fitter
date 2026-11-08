"""M2 - competition likelihood (zusammenfassung_porenmodell.md, M2).

Instead of "the crack origin MUST win" (M1): every pore j of a sample could have failed, with
probability proportional to its severity to the power k:

    P(crack origin | q, k) = (A0 g0^q)^k / sum_j (Aj gj^q)^k        (j: crack origin + all competitors)
    l(q, k) = sum over samples of ln P

k = sharpness of failure (k -> infinity: the most severe pore always fails = M1).
Estimate: (q, k) with the largest l on a grid; confidence interval for q from the profile likelihood
l_p(q) = max_k l(q, k):  2 [l_p(q_best) - l_p(q)] <= 3.84 (95 %).

Known weaknesses (PLAN.md): Schliff areas measured differently from A0 shift the estimate (M1 only
widens); only the pores of one section are in the denominator; if all samples agree (M1 interval not
empty), the best k lies at the upper end of the grid and M2 says no more than M1.
Competitors: Schliff pores not excluded; pores with g <= 0 have severity 0.
"""

import numpy as np
import pandas as pd

from q_fitter import Fit, FitResult, Prediction, Sample, register

CHI2_95 = 3.841         # chi^2, 1 degree of freedom, 95 % (interval of q alone)
CHI2_95_2 = 5.991       # chi^2, 2 degrees of freedom, 95 % (region of q and k together)
BLUE, BAND, INK, MUTED, GRID = "#2a78d6", "#cde2fb", "#0b0b0b", "#52514e", "#e4e3df"


@register("m2")
class M2(Fit):
    """M2: competition likelihood - best q and k, profile-likelihood interval for q."""

    params = {"q_start": "first q of the grid", "q_stop": "last q of the grid", "q_step": "step of the q grid",
              "k_min": "smallest k of the grid (k_min = k_max: k fixed)", "k_max": "largest k of the grid",
              "k_count": "number of k values, log-spaced between k_min and k_max"}

    def fit(self, samples: list[Sample]) -> FitResult:
        q = np.round(np.arange(self.q_start, self.q_stop + self.q_step / 2, self.q_step), 10)
        k = np.geomspace(self.k_min, self.k_max, int(self.k_count)) if self.k_max > self.k_min else np.array([float(self.k_min)])

        usable, notes = [], {}
        for sample in samples:
            ln_crack, ln_comp = _log_parts(sample)
            if not np.isfinite(ln_crack[1]):        # ln g0 = -inf: g0 <= 0
                notes[sample.id] = "crack origin without stress (g0 <= 0) - not used in M2"
            elif ln_comp.shape[1] == 0:
                notes[sample.id] = "no competitors - not used in M2"
            else:
                usable.append((sample.id, ln_crack, ln_comp))

        # l(q, k) summed over the samples. The grid of each sample is kept: the quality control
        # (validation) fits the same samples again and again in other combinations.
        cache = self.__dict__.setdefault("_ll_cache", {})
        ll = np.zeros((len(q), len(k)))
        for sample_id, ln_crack, ln_comp in usable:
            key = (sample_id, ln_crack.tobytes(), ln_comp.tobytes())
            if key not in cache:
                cache[key] = _sample_ll(q, k, ln_crack, ln_comp)
            ll += cache[key]

        if not usable:
            overall = pd.DataFrame([("status", "no usable samples", "")], columns=["quantity", "value", "note"])
            return FitResult(per_sample=_per_sample_table(samples, notes, {}), tables={"m2_overall": overall})

        i, j = np.unravel_index(np.argmax(ll), ll.shape)
        q_best, k_best = float(q[i]), float(k[j])
        profile = ll.max(axis=1)                  # l_p(q)
        k_at_q = k[ll.argmax(axis=1)]
        delta = profile.max() - profile
        inside = 2 * delta <= CHI2_95
        k_profile = ll.max(axis=0)
        k_inside = 2 * (k_profile.max() - k_profile) <= CHI2_95

        # per sample at the best (q, k): probability and rank of the crack origin
        best = {}
        for sample_id, ln_crack, ln_comp in usable:
            ln_s0 = ln_crack[0] + q_best * ln_crack[1]
            with np.errstate(invalid="ignore"):
                ln_s = ln_comp[0] + q_best * ln_comp[1]
            ln_s = np.where(np.isfinite(ln_s), ln_s, -np.inf)
            p = float(np.exp(k_best * ln_s0 - np.logaddexp(k_best * ln_s0, _lse(k_best * ln_s))))
            best[sample_id] = {"m2_p_crack": p, "m2_rank_crack": int(1 + (ln_s > ln_s0).sum()),
                               "m2_competitors": int(ln_comp.shape[1])}

        warnings = []
        if j == len(k) - 1 and len(k) > 1:
            warnings.append("best k at the upper end of the grid: the samples agree with a hard rule (M1) - "
                            "M2 adds nothing beyond the M1 interval; raise k_max to check")
        if j == 0 and len(k) > 1:
            warnings.append("best k at the lower end of the grid: failure looks almost random - lower k_min")
        if inside[0] or inside[-1]:
            warnings.append("q interval reaches the end of the q grid - widen q_start / q_stop")
        overall = pd.DataFrame([
            ("samples used", len(usable), f"of {len(samples)}"),
            ("q best", q_best, "maximum of the likelihood"),
            ("k best", k_best, "sharpness of failure (large = most severe pore nearly always fails)"),
            ("q 95% interval", _ranges(q[inside], q), "profile likelihood: 2 (l_max - l_p(q)) <= 3.84"),
            ("k 95% interval", _ranges(k[k_inside], k, fmt=".3g"), "profile likelihood over k"),
            ("log-likelihood max", float(ll[i, j]), ""),
            ("log-likelihood random", float(-sum(np.log(1 + c.shape[1]) for _, _, c in usable)),
             "k = 0: every pore equally likely to fail (for comparison)"),
            ("mean P(crack origin)", float(np.mean([b["m2_p_crack"] for b in best.values()])), "at q best, k best"),
            ("warnings", " | ".join(warnings), ""),
        ], columns=["quantity", "value", "note"]).astype({"value": object})
        profile_table = pd.DataFrame({"q": q, "loglik_profile": profile, "delta": delta, "k_best_at_q": k_at_q,
                                      "in_95": inside})
        figures = {"m2_profile": lambda: _plot_profile(profile_table, q_best, k_best),
                   "m2_likelihood": lambda: _plot_surface(q, k, ll, q_best, k_best)}
        return FitResult(per_sample=_per_sample_table(samples, notes, best),
                         tables={"m2_overall": overall, "m2_profile": profile_table}, figures=figures)

    def prediction(self, result: FitResult) -> Prediction | None:
        """point q = q best, range = 95 % interval of q, k = k best."""
        values = dict(zip(result.tables["m2_overall"]["quantity"], result.tables["m2_overall"]["value"]))
        if "q best" not in values:
            return None
        profile = result.tables["m2_profile"]
        return Prediction(q=float(values["q best"]), q_values=profile.loc[profile["in_95"], "q"].to_numpy(float),
                          k=float(values["k best"]))


def _log_parts(sample: Sample):
    """ln S as a function of q: ln S(q) = ln A + q ln g, returned as (crack (nq-independent parts), competitors)."""
    pores = sample.pores
    crack = sample.crack
    comp = pores[(pores["kind"] == "pore") & ~pores["excluded"]]
    with np.errstate(divide="ignore"):
        crack_parts = np.array([np.log(crack["A_um2"]), np.log(crack["g"]) if crack["g"] > 0 else -np.inf])
        g = comp["g"].to_numpy(float)
        comp_parts = np.vstack([np.log(comp["A_um2"].to_numpy(float)), np.where(g > 0, np.log(np.maximum(g, 1e-300)), -np.inf)])
    return crack_parts, comp_parts


def _sample_ll(q, k, crack_parts, comp_parts) -> np.ndarray:
    """ln P(crack origin) on the (q, k) grid for one sample."""
    with np.errstate(invalid="ignore"):
        ln_s0 = crack_parts[0] + q * crack_parts[1]                              # (nq,)
        ln_s = comp_parts[0][None, :] + q[:, None] * comp_parts[1][None, :]       # (nq, n)
    ln_s = np.where(np.isfinite(ln_s), ln_s, -np.inf)                           # g <= 0: severity 0
    out = np.empty((len(q), len(k)))
    for j, kj in enumerate(k):
        out[:, j] = kj * ln_s0 - np.logaddexp(kj * ln_s0, _lse(kj * ln_s, axis=-1))
    return out


def _lse(x, axis=-1):
    m = np.max(x, axis=axis, keepdims=True)
    m = np.where(np.isfinite(m), m, 0.0)
    return np.squeeze(m, axis=axis) + np.log(np.sum(np.exp(x - m), axis=axis))


def _per_sample_table(samples, notes, best) -> pd.DataFrame:
    rows = []
    for sample in samples:
        row = {"ID": sample.id, "m2_p_crack": np.nan, "m2_rank_crack": np.nan, "m2_competitors": np.nan,
               "m2_note": notes.get(sample.id, "")}
        row.update(best.get(sample.id, {}))
        rows.append(row)
    return pd.DataFrame(rows, columns=["ID", "m2_p_crack", "m2_rank_crack", "m2_competitors", "m2_note"])


def _ranges(values, grid, fmt="g") -> str:
    if not len(values):
        return ""
    index = np.searchsorted(grid, values)
    parts, start = [], 0
    for n in range(1, len(index) + 1):
        if n == len(index) or index[n] != index[n - 1] + 1:
            lo, hi = values[start], values[n - 1]
            parts.append(f"{lo:{fmt}}" if lo == hi else f"{lo:{fmt}}-{hi:{fmt}}")
            start = n
    return "; ".join(parts)


# ----------------------------------------------------------------------------------------------
# figures

def _style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelcolor=INK)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _plot_profile(table: pd.DataFrame, q_best: float, k_best: float):
    import matplotlib
    import matplotlib.ticker
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (top, bottom) = plt.subplots(2, 1, figsize=(9, 6), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    q, d = table["q"].to_numpy(), table["delta"].to_numpy()
    shown = np.minimum(d, 15)
    inside = table["in_95"].to_numpy()
    top.fill_between(q, 0, 15, where=inside, step="mid", color=BAND, zorder=0, label="95% interval of q")
    top.plot(q, shown, color=BLUE, linewidth=2)
    top.axhline(CHI2_95 / 2, color=MUTED, linestyle="--", linewidth=1, label="limit 1.92 (95%)")
    top.plot([q_best], [0], "o", color=INK, markersize=7, label=f"best q = {q_best:g} (k = {k_best:.3g})")
    top.set_ylim(15, -0.5)           # best at the top
    top.set_ylabel("l_max - l_p(q)")
    top.set_title("M2: profile likelihood of q (lower = more likely; cut at 15)", loc="left", fontsize=11, color=INK)
    top.legend(loc="lower right", frameon=False, fontsize=8)
    _style(top)
    bottom.step(q, table["k_best_at_q"], where="mid", color=BLUE, linewidth=2)
    bottom.set_yscale("log")
    bottom.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    bottom.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    bottom.set_ylabel("best k at q")
    bottom.set_xlabel("q")
    _style(bottom)
    fig.tight_layout()
    return fig


def _plot_surface(q, k, ll, q_best, k_best):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    delta = np.minimum(ll.max() - ll, 30)
    fig, ax = plt.subplots(figsize=(9, 5.5))
    if len(k) > 1:
        levels = np.linspace(0, 30, 31)
        filled = ax.contourf(q, k, delta.T, levels=levels, cmap="Blues_r")
        ax.contour(q, k, delta.T, levels=[CHI2_95_2 / 2], colors=[INK], linewidths=1.2)
        fig.colorbar(filled, ax=ax, label="l_max - l(q, k)  (cut at 30)")
        ax.set_yscale("log")
    else:
        ax.plot(q, delta[:, 0], color=BLUE, linewidth=2)
    ax.plot([q_best], [k_best], "o", color="white", markeredgecolor=INK, markersize=8, label="best (q, k)")
    ax.set_xlabel("q")
    ax.set_ylabel("k")
    ax.set_title("M2: likelihood over q and k (dark = more likely; black line = 95% region of q and k together)", loc="left",
                 fontsize=11, color=INK)
    ax.legend(loc="upper right", frameon=True, fontsize=8)
    fig.tight_layout()
    return fig
