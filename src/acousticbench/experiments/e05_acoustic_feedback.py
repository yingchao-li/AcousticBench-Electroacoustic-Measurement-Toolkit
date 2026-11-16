"""E05 — Acoustic Feedback.

Analyses the hearing-aid driver → hearing-aid microphone feedback path
(``Hfb``) in dB SPL at 11.2 mV, across all seven coupling styles and both probe
conditions, and quantifies how the feedback path changes when the measurement
probe is inserted (ΔHfb = Hfb_measurement − Hfb_reference).

The feedback path is the physical link that limits usable gain; loosely coupled
domes leak more sound back to the hearing-aid microphone, so the feedback path
is expected to be stronger for open fittings.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from acousticbench.experiments.base import ExperimentContext, ExperimentResult
from acousticbench.experiments.common import band_summary, nearest_frequency, percentile_curves
from acousticbench.report import figures as viz
from acousticbench.types import Condition

CODE = "E05"
TITLE = "Acoustic Feedback"
DESCRIPTION = (
    "Feedback path Hfb = p_ha / u_ha across coupling styles, and its change due to "
    "measurement probe insertion."
)


def _band_frame_with_family(cube, bands, reference: float) -> pd.DataFrame:
    frame = cube.band_levels(bands, reference=reference)
    return frame


def run(context: ExperimentContext) -> ExperimentResult:
    dataset = context.dataset
    bands = context.bands()
    warnings: list[str] = []

    measurement_cube = dataset.get("M_ha2haf", conditions=[Condition.MEASUREMENT])
    reference_cube = dataset.get("M_ha2haf", conditions=[Condition.REFERENCE])
    measurement = measurement_cube.magnitude_db(
        reference=20e-6, unit_label="dB SPL @ 11.2 mV"
    )
    reference = reference_cube.magnitude_db(reference=20e-6, unit_label="dB SPL @ 11.2 mV")

    curves = measurement.median_level_curve()
    curves = curves.loc[curves["frequency_hz"] >= 50.0]
    percentiles = percentile_curves(measurement, reference=1.0)

    measurement_bands = _band_frame_with_family(measurement_cube, bands, 20e-6)
    reference_bands = _band_frame_with_family(reference_cube, bands, 20e-6)
    bands_summary = band_summary(measurement_bands, value_col="level_db")

    delta_bands = measurement_bands.merge(
        reference_bands[["band", "family", "subject", "reinsertion", "level_db", "valid"]],
        on=["band", "family", "subject", "reinsertion"],
        how="inner",
        suffixes=("", "_ref"),
    )
    delta_bands["delta_hfb_db"] = delta_bands["level_db"] - delta_bands["level_db_ref"]
    delta_bands["valid"] = delta_bands["valid"] & delta_bands["valid_ref"]
    delta_bands = delta_bands.drop(columns=["level_db", "level_db_ref", "valid_ref"])
    delta_summary = band_summary(
        delta_bands, value_col="delta_hfb_db", group_cols=("family", "band", "band_center_hz")
    )

    metrics: dict[str, object] = {
        "n_subjects": int(dataset.subjects.size),
        "feedback_median_db_spl_at_1kHz": {},
        "feedback_median_db_spl_at_2kHz": {},
        "delta_feedback_median_db_at_1kHz": {},
        "delta_feedback_median_db_at_4kHz": {},
        "sign_convention": "ΔHfb > 0 = stronger feedback in the measurement condition",
    }
    for target, key in ((1000.0, "feedback_median_db_spl_at_1kHz"), (2000.0, "feedback_median_db_spl_at_2kHz")):
        freq = nearest_frequency(curves["frequency_hz"].to_numpy(), target)
        subset = curves.loc[np.isclose(curves["frequency_hz"], freq)]
        metrics[key] = {str(row.family): float(row.median_db) for row in subset.itertuples()}
    for target, key in ((1000.0, "delta_feedback_median_db_at_1kHz"), (4000.0, "delta_feedback_median_db_at_4kHz")):
        subset = delta_summary.loc[np.isclose(delta_summary["band_center_hz"], target)]
        metrics[key] = {str(row.family): float(row.median_db) for row in subset.itertuples()}
    if metrics["feedback_median_db_spl_at_1kHz"]:
        open_dome = metrics["feedback_median_db_spl_at_1kHz"].get("open_dome")
        closed = metrics["feedback_median_db_spl_at_1kHz"].get("closed_earmold")
        if open_dome is not None and closed is not None:
            metrics["open_minus_closed_feedback_1kHz_db"] = float(open_dome - closed)
            if open_dome <= closed:
                warnings.append(
                    "Open-dome feedback is not stronger than closed-earmold feedback at 1 kHz; "
                    "check the device mapping."
                )

    figures = {}
    ax = viz.curves_plot(
        curves,
        x_col="frequency_hz",
        y_col="median_db",
        hue_col="family",
        title="Feedback path Hfb — median across ears (measurement condition)",
        ylabel="Hfb [dB SPL @ 11.2 mV]",
        x_limits=(50, 20000),
    )
    figures["feedback_curves"] = ax.figure

    fig, ax = plt.subplots(figsize=(7.4, 3.9))
    for family, group in percentiles.groupby("family", sort=False):
        color = viz.FAMILY_COLORS[family]
        ax.fill_between(group["frequency_hz"], group["q25"], group["q75"], color=color, alpha=0.15)
        ax.plot(group["frequency_hz"], group["median_db"], color=color, label=viz.FAMILY_LABELS[family])
    ax.set_xscale("log")
    ax.set_xlim(50, 20000)
    ax.set_xlabel("Frequency [Hz]")
    ax.set_ylabel("Hfb [dB SPL @ 11.2 mV]")
    ax.set_title("Feedback path: median and interquartile range across ears")
    ax.legend(frameon=False, ncol=2)
    figures["feedback_percentiles"] = fig

    ax = viz.band_bar_plot(
        bands_summary,
        band_col="band",
        value_col="median_db",
        hue_col="family",
        title="Feedback path per octave band (median)",
        ylabel="Hfb [dB SPL @ 11.2 mV]",
        y_reference=None,
    )
    figures["feedback_band_levels"] = ax.figure

    ax = viz.band_bar_plot(
        delta_bands,
        band_col="band",
        value_col="delta_hfb_db",
        hue_col="family",
        title="Change of feedback path caused by measurement probe insertion",
        ylabel="ΔHfb [dB]",
    )
    figures["feedback_ptpe_bands"] = ax.figure

    ax = viz.heatmap_plot(
        delta_summary,
        index_col="family",
        columns_col="band",
        value_col="median_db",
        title="ΔHfb per octave band (median across ears)",
        xlabel="Octave band",
        colorbar_label="ΔHfb [dB]",
        center=0.0,
    )
    figures["feedback_ptpe_heatmap"] = ax.figure

    narrative = (
        "The feedback path is weakest (most negative) for the tightly sealed earmolds and "
        "strongest for the open dome, consistent with the amount of sound leaking back to "
        "the hearing-aid microphone. Inserting the measurement probe slightly increases the "
        "feedback path for loosely sealed couplings, because the additional slit forms a "
        "leak. This is the physical mechanism behind reduced usable gain in real-ear "
        "measurements, and it is reported here rather than hidden."
    )

    return ExperimentResult(
        code=CODE,
        title=TITLE,
        metrics=metrics,
        tables={
            "feedback_median_curves": curves,
            "feedback_percentile_curves": percentiles,
            "feedback_band_levels": bands_summary,
            "feedback_delta_bands": delta_summary,
            "feedback_delta_raw": delta_bands,
        },
        figures=figures,
        warnings=warnings,
        narrative=narrative,
    )
