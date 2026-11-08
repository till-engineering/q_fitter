"""M1 - pairwise bounds (zusammenfassung_porenmodell.md, part B).

The crack origin (index 0) had the largest severity: A0 g0^q >= Ai gi^q for every competitor i.
With s = ln(g0 / gi) and a = ln(Ai / A0) that is  q s >= a, the limit is q* = a / s:

    s > 0, a > 0   crack origin nearer to the surface, competitor larger -> lower bound q >= q*
    s < 0, a < 0   crack origin further inside, competitor smaller        -> upper bound q <= q*
    s > 0, a <= 0  (or s = 0, a <= 0)                                     -> not informative
    s < 0, a >= 0  (or s = 0, a > 0)                                      -> contradiction (no q > 0 works)
    gi <= 0        competitor without stress (severity 0)                 -> not informative

Per sample q_u = largest lower bound (0 if none), q_o = smallest upper bound (inf if none).
All samples: intersection max q_u <= q <= min q_o. V(q) = number of samples whose crack origin does
not win at q (= q < q_u, q > q_o or a contradiction); V(q) = 0 is exactly the intersection.
"""

import numpy as np
import pandas as pd

from q_fitter import Fit, FitResult, Prediction, Sample, register

from . import m1_figures as figures


@register("m1")
class M1(Fit):
    """M1: pairwise bounds per sample, intersection over all samples and V(q)."""

    params = {"q_start": "first q of the grid for V(q)", "q_stop": "last q of the grid (also right end of the plot)",
              "q_step": "step of the grid",
              "sample_images": "pictures of the Schliff per sample: contradictions | all | none",
              "image_max_px": "long edge of those pictures in px (large panoramas are shrunk)"}

    def fit(self, samples: list[Sample]) -> FitResult:
        if self.sample_images not in ("contradictions", "all", "none"):
            raise ValueError(f"m1: sample_images must be contradictions, all or none, not {self.sample_images!r}")
        per_sample, per_pore = [], {}
        for sample in samples:
            row, pores = _bounds(sample)
            per_sample.append(row)
            per_pore[sample.id] = pores
        per_sample = pd.DataFrame(per_sample, columns=["ID", "m1_q_lower", "m1_q_upper", "m1_lower_bounds",
                                                       "m1_upper_bounds", "m1_contradictions", "m1_lower_by",
                                                       "m1_upper_by", "m1_status"])

        q = np.round(np.arange(self.q_start, self.q_stop + self.q_step / 2, self.q_step), 10)
        violated = np.zeros(len(q), int)
        for row in per_sample.itertuples():
            bad = (q < row.m1_q_lower) | (q > row.m1_q_upper) | (row.m1_contradictions > 0)
            violated += bad
        v_table = pd.DataFrame({"q": q, "V": violated})
        overall = _overall(per_sample, v_table)
        all_pores = _all_pores(samples, per_pore)
        contradictions = _contradiction_table(samples, per_sample, all_pores, overall)

        figs = {}
        if len(per_sample):      # callables: each figure is drawn and saved one after the other
            figs["m1_bounds"] = lambda: figures.plot_bounds(per_sample, overall, self.q_stop)
            figs["m1_V_q"] = lambda: figures.plot_v(v_table, len(per_sample))
            figs["m1_pore_map"] = lambda: figures.plot_pore_map(all_pores, overall)
            rows = per_sample.set_index("ID").to_dict("index")
            for sample in samples:
                row = rows[sample.id]
                if self.sample_images == "all" or (self.sample_images == "contradictions" and row["m1_status"] != "ok"):
                    figs[f"m1_samples/{sample.id}"] = (
                        lambda sample=sample, row=row: figures.plot_sample(
                            sample, all_pores[all_pores["ID"] == sample.id], row, self.image_max_px))
        return FitResult(per_sample=per_sample, per_pore=per_pore,
                         tables={"m1_overall": overall, "m1_V_q": v_table, "m1_contradictions": contradictions},
                         figures=figs)

    def prediction(self, result: FitResult) -> Prediction | None:
        """q range = grid points with V minimal (= the intersection if there is no contradiction);
        point q = the middle grid point of that range."""
        v = result.tables.get("m1_V_q")
        if v is None or not len(v) or not len(result.per_sample):
            return None
        v_min = int(v["V"].min())
        at_min = v.loc[v["V"] == v_min, "q"].to_numpy(float)
        return Prediction(q=float(at_min[len(at_min) // 2]), q_values=at_min, info={"V_min": v_min})


def _bounds(sample: Sample):
    pores = sample.pores
    crack = sample.crack
    a0, g0 = float(crack["A_um2"]), float(crack["g"])
    a_i, g_i = pores["A_um2"].to_numpy(float), pores["g"].to_numpy(float)
    competitor = ((pores["kind"] == "pore") & ~pores["excluded"]).to_numpy()

    with np.errstate(divide="ignore", invalid="ignore"):
        s = np.log(g0 / g_i) if g0 > 0 else np.full(len(pores), -np.inf)
        a = np.log(a_i / a0)
        q_star = a / s
    no_stress = competitor & (g_i <= 0)
    lower = competitor & ~no_stress & (s > 0) & (a > 0)
    upper = competitor & ~no_stress & (s < 0) & (a < 0)
    contradiction = competitor & ~no_stress & (((s < 0) & (a >= 0)) | ((s == 0) & (a > 0)))
    if g0 <= 0:
        lower[:] = upper[:] = False
        contradiction = competitor & (g_i > 0)

    bound = np.where(pores["kind"] == "crack", "crack origin",
             np.where(~competitor, "excluded",
             np.where(no_stress, "no stress",
             np.where(lower, "lower", np.where(upper, "upper",
             np.where(contradiction, "contradiction", "not informative"))))))
    q_star = np.where(lower | upper, q_star, np.nan)
    pore_cols = pd.DataFrame({"m1_s": np.where(competitor, s, np.nan), "m1_a": np.where(competitor, a, np.nan),
                              "m1_q_star": q_star, "m1_bound": bound})

    ids = pores["pore_id"].to_numpy()
    q_lower, lower_by = (float(q_star[lower].max()), ids[lower][np.argmax(q_star[lower])]) if lower.any() else (0.0, "")
    q_upper, upper_by = (float(q_star[upper].min()), ids[upper][np.argmin(q_star[upper])]) if upper.any() else (np.inf, "")
    if contradiction.any():
        status = "contradiction"
    elif q_lower > q_upper:
        status = "empty (lower > upper)"
    else:
        status = "ok"
    row = {"ID": sample.id, "m1_q_lower": q_lower, "m1_q_upper": q_upper, "m1_lower_bounds": int(lower.sum()),
           "m1_upper_bounds": int(upper.sum()), "m1_contradictions": int(contradiction.sum()),
           "m1_lower_by": lower_by, "m1_upper_by": upper_by, "m1_status": status}
    return row, pore_cols


def _overall(per_sample: pd.DataFrame, v_table: pd.DataFrame) -> pd.DataFrame:
    n = len(per_sample)
    ok = per_sample["m1_status"] == "ok"
    q_lower = float(per_sample["m1_q_lower"].max()) if n else np.nan
    q_upper = float(per_sample["m1_q_upper"].min()) if n else np.nan
    q_lower_ok = float(per_sample.loc[ok, "m1_q_lower"].max()) if ok.any() else np.nan
    q_upper_ok = float(per_sample.loc[ok, "m1_q_upper"].min()) if ok.any() else np.nan
    with_pores = int((per_sample["m1_contradictions"] > 0).sum())
    crossed = int((per_sample["m1_status"] == "empty (lower > upper)").sum())
    if not n:
        status = "no samples"
    elif with_pores or crossed:
        status = "empty - contradictions within samples"
    elif q_lower > q_upper:
        status = "empty - samples do not overlap"
    else:
        status = "ok"
    v_min = int(v_table["V"].min()) if len(v_table) else 0
    at_min = v_table.loc[v_table["V"] == v_min, "q"].to_numpy()
    rows = [
        ("samples", n, ""),
        ("samples with lower bound", int((per_sample["m1_lower_bounds"] > 0).sum()), ""),
        ("samples with upper bound", int((per_sample["m1_upper_bounds"] > 0).sum()), ""),
        ("samples with both bounds", int(((per_sample["m1_lower_bounds"] > 0) & (per_sample["m1_upper_bounds"] > 0)).sum()), ""),
        ("samples with contradicting pores", with_pores, "a pore larger AND further out than the crack origin: no q works"),
        ("samples with lower > upper", crossed, "the pores of one sample contradict each other"),
        ("q lower (max over samples)", q_lower, "intersection over ALL samples: q_lower <= q <= q_upper"),
        ("q upper (min over samples)", q_upper, "empty cell = no upper bound"),
        ("q lower (samples without contradiction)", q_lower_ok, "intersection over the samples with status ok"),
        ("q upper (samples without contradiction)", q_upper_ok, "lower > upper here = samples do not overlap"),
        ("contradicting pores (total)", int((per_sample["m1_contradictions"]).sum()), "details: sheet m1_contradictions"),
        ("status", status, "contradictions = hint that the model for A or g does not fit"),
        ("V min (on the grid)", v_min, "fewest samples whose crack origin does not win"),
        ("q at V min", _ranges(at_min, v_table["q"].to_numpy()), "q ranges of the grid with V = V min"),
    ]
    return pd.DataFrame(rows, columns=["quantity", "value", "note"]).astype({"value": object})


def _ranges(values: np.ndarray, grid: np.ndarray) -> str:
    """Grid values -> text of contiguous ranges, e.g. '4.2-7.85; 9-9.5'."""
    if not len(values):
        return ""
    index = np.searchsorted(grid, values)
    parts, start = [], 0
    for k in range(1, len(index) + 1):
        if k == len(index) or index[k] != index[k - 1] + 1:
            lo, hi = values[start], values[k - 1]
            parts.append(f"{lo:g}" if lo == hi else f"{lo:g}-{hi:g}")
            start = k
    return "; ".join(parts)




def _all_pores(samples, per_pore) -> pd.DataFrame:
    parts = [pd.concat([sample.pores.reset_index(drop=True), per_pore[sample.id]], axis=1).assign(ID=sample.id)
             for sample in samples]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["ID", "m1_bound"])


CONTRA_COLUMNS = ["ID", "type", "role", "pore_id", "image", "A0_um2", "A_um2", "A_ratio", "g0", "g", "g_ratio",
                  "q_star", "gap_q", "xi0", "zeta0", "xi", "zeta", "dist_um", "hint"]


def _contradiction_table(samples, per_sample, pores, overall) -> pd.DataFrame:
    """Every contradiction with the pores behind it:
        contradicting pore   larger AND under higher stress than the crack origin (A_ratio, g_ratio >= 1)
        lower > upper        the two pores of one sample that set the crossed bounds (gap_q = q_u - q_o)
        between samples      the two samples (without contradiction) whose bounds do not overlap
    hint: a contradicting pore close to the crack origin may be the remnant of the crack pore itself;
          a pore outside the sample frame gets the stress of the nearest edge (check frame / ROI)."""
    rows = []
    crack = pores[pores["kind"] == "crack"].set_index("ID")

    def pore_row(sample_id, pore, kind, role, gap=np.nan, hint=""):
        c = crack.loc[sample_id]
        if not (-0.01 <= pore["xi"] <= 1.01 and -0.01 <= pore["zeta"] <= 1.01):
            hint = "; ".join(filter(None, [hint, f"outside the sample frame (xi = {pore['xi']:.3g}, zeta = "
                                                 f"{pore['zeta']:.3g}) - stress taken at the nearest edge"]))
        return {"ID": sample_id, "type": kind, "role": role, "pore_id": pore["pore_id"], "image": pore["image"],
                "A0_um2": c["A_um2"], "A_um2": pore["A_um2"], "A_ratio": pore["A_um2"] / c["A_um2"],
                "g0": c["g"], "g": pore["g"], "g_ratio": pore["g"] / c["g"] if c["g"] > 0 else np.nan,
                "q_star": pore["m1_q_star"], "gap_q": gap, "xi0": c["xi"], "zeta0": c["zeta"],
                "xi": pore["xi"], "zeta": pore["zeta"], "dist_um": pore["dist_um"], "hint": hint}

    for _, pore in pores[pores["m1_bound"] == "contradiction"].iterrows():
        r0 = np.sqrt(crack.loc[pore["ID"], "A_um2"] / np.pi)
        hint = ("close to the crack origin - remnant of the crack pore? (exclusion.radius_um)"
                if pore["dist_um"] <= 2 * r0 else "")
        rows.append(pore_row(pore["ID"], pore, "contradicting pore", "pore wins at every q", hint=hint))

    by_id = pores.set_index(["ID", "pore_id"])
    for row in per_sample.itertuples():
        if row.m1_q_lower > row.m1_q_upper:
            gap = row.m1_q_lower - row.m1_q_upper
            rows.append(pore_row(row.ID, _get(by_id, row.ID, row.m1_lower_by),
                                 "lower > upper", "sets lower bound", gap))
            rows.append(pore_row(row.ID, _get(by_id, row.ID, row.m1_upper_by),
                                 "lower > upper", "sets upper bound", gap))

    values = dict(zip(overall["quantity"], overall["value"]))
    lo_ok, hi_ok = values["q lower (samples without contradiction)"], values["q upper (samples without contradiction)"]
    if np.isfinite(lo_ok) and lo_ok > hi_ok:
        ok = per_sample[per_sample["m1_status"] == "ok"]
        high = ok.loc[ok["m1_q_lower"].idxmax()]
        low = ok.loc[ok["m1_q_upper"].idxmin()]
        gap = lo_ok - hi_ok
        rows.append(pore_row(high.ID, _get(by_id, high.ID, high.m1_lower_by),
                             "between samples", "largest lower bound of all samples", gap))
        rows.append(pore_row(low.ID, _get(by_id, low.ID, low.m1_upper_by),
                             "between samples", "smallest upper bound of all samples", gap))
    return pd.DataFrame(rows, columns=CONTRA_COLUMNS)


def _get(by_id: pd.DataFrame, sample_id, pore_id) -> pd.Series:
    pore = by_id.loc[(sample_id, pore_id)].copy()
    pore["pore_id"] = pore_id
    return pore
