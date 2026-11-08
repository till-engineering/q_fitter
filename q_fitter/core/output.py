"""Writing the results: JSON (column-wise, for programs), Excel (for humans), PNG (figures).

    <output.dir>/
        ergebnis.xlsx       sheets: Proben, Uebersprungen, <tables of the fits>, Poren
        proben.json         one row per sample (+ columns of the fits)
        poren.json          one row per pore of all samples (+ columns of the fits)
        uebersprungen.json  skipped IDs with reason
        <table>.json        tables of the fits (e.g. m1_gesamt, m1_V_q)
        <figure>.png        figures of the fits (m1_samples/<ID>.png: Schliff pictures per sample)
        config_used.yaml
        .q_fitter_files.txt list of the files of this run: the next run removes exactly these first,
                            so no result of a fit that is no longer run stays behind
"""

import json
import logging
import math
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger("q_fitter")
EXCEL_MAX_ROWS = 1_048_000
MANIFEST = ".q_fitter_files.txt"


def clean(out_dir: Path) -> None:
    """Remove the files of the previous run (only those listed in its manifest)."""
    manifest = out_dir / MANIFEST
    if not manifest.is_file():
        return
    root = out_dir.resolve()
    folders = set()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        path = (out_dir / line).resolve()
        if line and path.is_relative_to(root) and path.is_file():
            try:
                path.unlink()
            except PermissionError:
                log.warning("%s is open in another program - not removed", line)
            if path.parent != root:
                folders.add(path.parent)
    for folder in folders:
        if folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()
    manifest.unlink()


def write(out_dir: Path, samples, skipped, results, field) -> None:
    per_sample = _sample_table(samples, field)
    pores = _pore_table(samples, results)
    for result in results:
        if result.per_sample is not None:
            per_sample = per_sample.merge(result.per_sample, on="ID", how="left")
    skipped_table = pd.DataFrame({"ID": [s.id for s in skipped], "reason": [s.reason for s in skipped]})

    written = ["config_used.yaml"]
    tables = {"proben": per_sample, "uebersprungen": skipped_table, "poren": pores}
    for result in results:
        tables.update(result.tables)
    for name, table in tables.items():
        write_json_table(out_dir / f"{name}.json", table)
        written.append(f"{name}.json")

    import matplotlib.pyplot as plt
    cleared = set()
    for result in results:
        for name, figure in result.figures.items():
            if callable(figure):        # drawn only now: one figure in memory at a time
                figure = figure()
            path = out_dir / f"{name}.png"
            if path.parent != out_dir and path.parent not in cleared:   # sub folder: remove pictures of older runs
                shutil.rmtree(path.parent, ignore_errors=True)
                cleared.add(path.parent)
            path.parent.mkdir(parents=True, exist_ok=True)
            figure.savefig(path, dpi=150)
            plt.close(figure)
            written.append(f"{name}.png")

    sheets = {"Proben": per_sample, "Uebersprungen": skipped_table}
    for result in results:
        sheets.update(result.tables)
    sheets["Poren"] = pores
    try:
        with pd.ExcelWriter(out_dir / "ergebnis.xlsx", engine="openpyxl") as writer:
            for name, table in sheets.items():
                if len(table) >= EXCEL_MAX_ROWS:       # Excel limit: such a table is only in its JSON file
                    log.warning("table %s too long for Excel (%d rows) - only in the JSON file", name, len(table))
                    continue
                _for_excel(table).to_excel(writer, sheet_name=name[:31], index=False)
        written.append("ergebnis.xlsx")
    except PermissionError:
        log.warning("ergebnis.xlsx is open in Excel - not written (the JSON files are)")
    (out_dir / MANIFEST).write_text("\n".join(written) + "\n", encoding="utf-8")


def write_json_table(path: Path, table: pd.DataFrame) -> None:
    data = {column: [_json_value(v) for v in table[column]] for column in table.columns}
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _sample_table(samples, field) -> pd.DataFrame:
    rows = []
    for sample in samples:
        pores, crack = sample.pores, sample.crack
        competitors = pores["kind"] == "pore"
        row = {"ID": sample.id, "images": len(sample.images), "pores": int(competitors.sum()),
               "excluded": int((competitors & pores["excluded"]).sum()),
               "outside_frame": int((competitors & pores["outside_frame"]).sum()),
               "crack_outside_frame": bool(crack["outside_frame"]),
               "A0_raw_um2": crack["A_raw_um2"], "A0_um2": crack["A_um2"], "xi0": crack["xi"], "zeta0": crack["zeta"],
               "g0_field": crack["g_field"], "g0": crack["g"], "stress_field": field.key,
               "notes": "; ".join(sample.notes)}
        row.update({f"excel_{k}": v for k, v in sample.excel.items() if k != "ID"})
        rows.append(row)
    return pd.DataFrame(rows, columns=None if rows else ["ID"])


def _pore_table(samples, results) -> pd.DataFrame:
    parts = []
    for sample in samples:
        table = sample.pores.copy()
        for result in results:
            extra = result.per_pore.get(sample.id)
            if extra is not None:
                table = pd.concat([table, extra.reset_index(drop=True)], axis=1)
        table.insert(0, "ID", sample.id)
        parts.append(table)
    if not parts:
        return pd.DataFrame()
    table = pd.concat(parts, ignore_index=True)
    table["labels"] = table["labels"].map(lambda labels: " ".join(map(str, labels)))
    return table


def _for_excel(table: pd.DataFrame) -> pd.DataFrame:
    """inf / nan -> empty cell (no bound = empty)."""
    return table.replace([np.inf, -np.inf], np.nan)


def _json_value(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not math.isfinite(value) else float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, tuple):
        return list(value)
    return value
