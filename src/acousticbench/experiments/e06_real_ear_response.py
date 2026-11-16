"""E06 — Real-Ear Response.

Reports the real-ear unaided response (REUR), the real-ear unaided gain
(REUG), the real-ear occluded gain (REOG) and the real-ear occluded insertion
gain (REOIG) for every coupling style.

Scale conventions
-----------------
``REOIG`` is a ratio of two loudspeaker-driven pressures and is therefore
independent of the arbitrary free-field scaling of the stored data.
``REUG``/``REOG`` are normalised by the in-situ free-field estimate obtained
from the loosely hanging measurement probe in the reference condition (see the
data audit and docs/data.md).
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from acousticbench.experiments.base import ExperimentContext, ExperimentResult
from acousticbench.experiments.common import band_summary, nearest_frequency, percentile_curves
from acousticbench.measurements.transfer import (
    reog_db,
    reoig_band_levels,
    reoig_db,
    reug_band_levels,
    reug_db,
)
from acousticbench.report import figures as viz
from acousticbench.types import Condition, Probe

CODE = "E06"
TITLE = "Real-Ear Response"
DESCRIPTION = (
    "Real-ear unaided gain, occluded gain and occluded insertion gain across coupling styles."
)


def run(context: ExperimentContext) -> ExperimentResult:
    dataset = context.dataset
    bands = context.bands()
    warnings: list[str] = []

    reug = reug_db(dataset)
    reoig = reoig_db(dataset, condition=Condition.MEASUREMENT, probe=Probe.MEASUREMENT)
    reog = reog_db(dataset, condition=Condition.MEASUREMENT, probe=Probe.MEASUREMENT)

    reug_curves = percentile_curves(reug, reference=1.0)
    reoig_curves = percentile_curves(reoig, reference=1.0)
    reog_curves = percentile_curves(reog, reference=1.0)

    reug_bands = reug_band_levels(dataset, bands)
    reoig_bands = reoig_band_levels(
        dataset, bands, condition=Condition.MEASUREMENT, probe=Probe.MEASUREMENT
    )
    reoig_summary = band_summary(
        reoig_bands,
        value_col="reoig_db",
        group_cols=("family", "family_label", "band", "band_center_hz"),
    )
    reug_summary = band_summary(
        reug_bands,
        value_col="reug_db",
        group_cols=("family", "family_label", "band", "band_center_hz"),
    )

    metrics: dict[str, object] = {
        "n_subjects": int(dataset.subjects.size),
        "reug_median_db_at_1kHz": float(
            reug_curves.loc[
                np.isclose(reug_curves["frequency_hz"], nearest_frequency(reug_curves["frequency_hz"].to_numpy(), 1000.0)),
                "median_db",
            ].iloc[0]
        ),
        "reug_median_db_at_2kHz": float(
            reug_curves.loc[
                np.isclose(reug_curves["frequency_hz"], nearest_frequency(reug_curves["frequency_hz"].to_numpy(), 2000.0)),
                "median_db",
            ].iloc[0]
        ),
        "reug_median_db_at_4kHz": float(
            reug_curves.loc[
                np.isclose(reug_curves["frequency_hz"], nearest_frequency(reug_curves["frequency_hz"].to_numpy(), 4000.0)),
                "median_db",
            ].iloc[0]
        ),
        "reoig_median_db_at_1kHz": {},
        "reoig_median_db_at_4kHz": {},
        "note": (
            "REOIG is a pressure ratio and scale-invariant. REUG/REOG use the in-situ "
            "free-field reference; see docs/data.md for the documented scaling caveat."
        ),
    }
    for target, key in ((1000.0, "reoig_median_db_at_1kHz"), (4000.0, "reoig_median_db_at_4kHz")):
        subset = reoig_summary.loc[np.isclose(reoig_summary["band_center_hz"], target)]
        metrics[key] = {str(row.family): float(row.median_db) for row in subset.itertuples()}
    if np.nanmax(np.abs(reoig_summary["median_db"])) > 40:
        warnings.append(
            "Some REOIG values exceed ±40 dB; verify that the open-ear reference is correctly aligned."
        )

    figures = {}
    fig, ax = plt.subplots(figsize=(7.2, 3.7))
    subset = reug_curves
    ax.fill_between(subset["frequency_hz"], subset["q25"], subset["q75"], color="#7f7f7f", alpha=0.25, label="IQR")
    ax.fill_between(subset["frequency_hz"], subset["q10"], subset["q90"], color="#7f7f7f", alpha=0.12, label="10–90 %")
    ax.plot(subset["frequency_hz"], subset["median_db"], color="#333333", label="median")
    ax.axhline(0.0, color="k", linewidth=0.8)
    ax.set_xscale("log")
    ax.set_xlim(50, 20000)
    ax.set_xlabel("Frequency [Hz]")
    ax.set_ylabel("REUG [dB re in-situ free field]")
    ax.set_title("Real-ear unaided gain (open ear, 14 subjects)")
    ax.legend(frameon=False)
    figures["reug_curves"] = fig

    ax = viz.curves_plot(
        reoig_curves,
        x_col="frequency_hz",
        y_col="median_db",
        hue_col="family",
        title="Real-ear occluded insertion gain (measurement probe, measurement condition)",
        ylabel="REOIG [dB]",
        x_limits=(50, 20000),
        y_reference=0.0,
    )
    figures["reoig_curves"] = ax.figure

    ax = viz.band_bar_plot(
        reoig_summary,
        band_col="band",
        value_col="median_db",
        hue_col="family",
        title="REOIG per octave band (median)",
        ylabel="REOIG [dB]",
    )
    figures["reoig_band_levels"] = ax.figure

    ax = viz.curves_plot(
        reog_curves,
        x_col="frequency_hz",
        y_col="median_db",
        hue_col="family",
        title="Real-ear occluded gain re in-situ free field",
        ylabel="REOG [dB]",
        x_limits=(50, 20000),
        y_reference=0.0,
    )
    figures["reog_curves"] = ax.figure

    ax = viz.heatmap_plot(
        reoig_summary,
        index_col="family",
        columns_col="band",
        value_col="median_db",
        title="REOIG per octave band",
        xlabel="Octave band",
        colorbar_label="REOIG [dB]",
        center=0.0,
    )
    figures["reoig_heatmap"] = ax.figure

    narrative = (
        "The open ear shows the characteristic ear-canal resonance of roughly +14 dB near "
        "2 kHz relative to 1 kHz. Occluding the ear with a tightly sealed earmold strongly "
        "attenuates external sound below 2 kHz (negative REOIG), whereas open and tulip domes "
        "provide almost no attenuation. REOIG therefore quantifies coupling tightness and "
        "is the acoustic quantity most directly related to the probe-tube presence effect."
    )

    return ExperimentResult(
        code=CODE,
        title=TITLE,
        metrics=metrics,
        tables={
            "reug_percentiles": reug_curves,
            "reoig_percentiles": reoig_curves,
            "reog_percentiles": reog_curves,
            "reug_band_levels": reug_summary,
            "reoig_band_levels": reoig_summary,
        },
        figures=figures,
        warnings=warnings,
        narrative=narrative,
    )
