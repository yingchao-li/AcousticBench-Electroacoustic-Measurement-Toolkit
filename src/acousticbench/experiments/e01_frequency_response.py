"""E01 — Frequency Response.

Characterises ``Hha`` (hearing-aid driver → eardrum pressure, in dB SPL at the
11.2 mV receiver drive) across all seven earpiece families, and quantifies the
inter-subject spread.  The clinical configuration is used: measurement probe
tube, measurement condition, where all seven earpieces have a valid eardrum
measurement.

Deliverables
------------
* median Hha curves per family and octave-band levels
* 10/25/50/75/90 % across-subject percentile curves
* band-level heat map and a summary table with the number of contributing ears
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from acousticbench.experiments.base import ExperimentContext, ExperimentResult
from acousticbench.experiments.common import (
    band_summary,
    nearest_frequency,
    percentile_curves,
)
from acousticbench.measurements.transfer import hha_band_levels, hha_db_spl
from acousticbench.report import figures as viz
from acousticbench.types import Condition, Probe

CODE = "E01"
TITLE = "Frequency Response"
DESCRIPTION = (
    "Hearing-aid driver response Hha at the eardrum across all earpiece families "
    "(measurement probe, measurement condition)."
)


def run(context: ExperimentContext) -> ExperimentResult:
    dataset = context.dataset
    bands = context.bands()
    params = context.params()
    warnings: list[str] = []

    hha = hha_db_spl(dataset, probe=Probe.MEASUREMENT, condition=Condition.MEASUREMENT)
    curves = hha.median_level_curve()
    curves = curves.loc[curves["frequency_hz"] >= 50.0]
    percentiles = percentile_curves(hha, reference=20e-6)

    band_levels = hha_band_levels(
        dataset, bands, probe=Probe.MEASUREMENT, condition=Condition.MEASUREMENT
    )
    bands_summary = band_summary(band_levels, value_col="level_db")
    bands_summary["family_label"] = bands_summary["family_label"].astype(str)

    # Metrics at key frequencies.
    metrics: dict[str, object] = {}
    for target in (1000.0, 2000.0, 4000.0):
        freq = nearest_frequency(curves["frequency_hz"].to_numpy(), target)
        subset = curves.loc[np.isclose(curves["frequency_hz"], freq)]
        metrics[f"hha_median_db_spl_at_{int(target)}Hz"] = {
            str(row.family): float(row.median_db) for row in subset.itertuples()
        }
    high_band = bands_summary.loc[bands_summary["band"] == "4000 Hz"]
    metrics["hha_median_db_spl_4kHz_band"] = {
        str(row.family): float(row.median_db) for row in high_band.itertuples()
    }
    metrics["n_subjects"] = int(hha.subjects.size)
    metrics["n_families"] = int(len(hha.devices))
    metrics["frequency_range_hz"] = [50.0, float(hha.freq_hz.max())]
    metrics["note"] = (
        "Levels are dB SPL at the 11.2 mV receiver drive. The clinical configuration "
        "(measurement probe, measurement condition) is used so that all seven families "
        "are comparable; dome conditions have no reference-probe data."
    )
    if np.any(~np.isfinite(curves["median_db"])):
        warnings.append("Some median curves contain NaN bins (no valid subject data).")

    figures = {}
    ax = viz.curves_plot(
        curves,
        x_col="frequency_hz",
        y_col="median_db",
        hue_col="family",
        title="Hha — median across 14 ears (measurement probe, measurement condition)",
        ylabel="Hha [dB SPL @ 11.2 mV]",
        x_limits=(50, 20000),
    )
    figures["hha_median_curves"] = ax.figure

    # Percentile fan chart for the most occluded and most open coupling.
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 3.8), sharey=True)
    for ax, family in zip(axes, ("closed_earmold", "open_dome")):
        subset = percentiles.loc[percentiles["family"] == family]
        color = viz.FAMILY_COLORS[family]
        ax.fill_between(
            subset["frequency_hz"], subset["q10"], subset["q90"], color=color, alpha=0.15, label="10–90 %"
        )
        ax.fill_between(
            subset["frequency_hz"], subset["q25"], subset["q75"], color=color, alpha=0.30, label="25–75 %"
        )
        ax.plot(subset["frequency_hz"], subset["median_db"], color=color, label="median")
        ax.set_xscale("log")
        ax.set_title(f"{viz.FAMILY_LABELS[family]}")
        ax.set_xlabel("Frequency [Hz]")
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("Hha [dB SPL @ 11.2 mV]")
    axes[0].legend(frameon=False, fontsize=7)
    fig.suptitle("Across-subject distribution of Hha", fontsize=10)
    fig.tight_layout()
    figures["hha_subject_distribution"] = fig

    ax = viz.heatmap_plot(
        bands_summary,
        index_col="family_label",
        columns_col="band",
        value_col="median_db",
        title="Hha octave-band levels — median across ears",
        xlabel="Octave band",
        colorbar_label="dB SPL @ 11.2 mV",
        cmap="viridis",
        center=None,
    )
    figures["hha_band_heatmap"] = ax.figure

    narrative = (
        "Hha is highest at mid frequencies (≈2 kHz) and rolls off both below 500 Hz and "
        "above 8 kHz. Closed and nugget earmolds show the highest low-frequency output, "
        "while open domes show the lowest, reflecting the acoustic leakage of the coupling. "
        "The across-subject fan chart demonstrates substantial inter-individual variability "
        "that must be respected by any statistical comparison (subject is the independent unit)."
    )

    return ExperimentResult(
        code=CODE,
        title=TITLE,
        metrics=metrics,
        tables={
            "hha_median_curves": curves,
            "hha_percentile_curves": percentiles,
            "hha_band_levels_summary": bands_summary,
            "hha_band_levels_raw": band_levels,
        },
        figures=figures,
        warnings=warnings,
        narrative=narrative,
    )
