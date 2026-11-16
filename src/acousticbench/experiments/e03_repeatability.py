"""E03 — Measurement Repeatability.

The three reinsertions of each earpiece are technical repeats with the probe
tubes left in place.  Their scatter is the noise floor of every downstream
effect estimate.  This experiment quantifies:

* within-subject reinsertion standard deviation (dB), frequency-resolved and
  per octave band,
* the repeatability coefficient ``1.96 · √2 · SD`` (95 % of reinsertion
  differences),
* the intraclass correlation ``ICC(2,1)`` between reinsertions.

Repeatability is computed on ``Hha`` (measurement probe, measurement
condition), so all seven coupling styles are represented.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from acousticbench.experiments.base import ExperimentContext, ExperimentResult
from acousticbench.experiments.common import nearest_frequency
from acousticbench.measurements.repeatability import (
    reinsertion_sd_by_frequency,
    repeatability_by_device,
    repeatability_summary,
)
from acousticbench.measurements.transfer import hha_db_spl
from acousticbench.report import figures as viz
from acousticbench.types import Condition, Probe

CODE = "E03"
TITLE = "Measurement Repeatability"
DESCRIPTION = (
    "Within-subject reinsertion variability of Hha, repeatability coefficient and ICC(2,1)."
)


def run(context: ExperimentContext) -> ExperimentResult:
    dataset = context.dataset
    bands = context.bands()
    params = context.params()
    warnings: list[str] = []

    hha = hha_db_spl(dataset, probe=Probe.MEASUREMENT, condition=Condition.MEASUREMENT)
    if "M_ha2edR" in params.get("probe", "") or params.get("probe") == "reference":
        hha = hha_db_spl(dataset, probe=Probe.REFERENCE, condition=Condition.MEASUREMENT)

    summary = repeatability_summary(hha, bands, reference=1.0)
    wide_band = repeatability_by_device(hha, reference=1.0)
    frequency_sd = reinsertion_sd_by_frequency(hha, reference=1.0)
    frequency_sd = frequency_sd.loc[frequency_sd["frequency_hz"] >= 50.0]

    # Median SD per family and frequency bin (one device per family here).
    frequency_summary = (
        frequency_sd.groupby(["family", "frequency_hz"], as_index=False)
        .agg(
            median_sd_db=("sd_db", "median"),
            q25_sd_db=("sd_db", lambda values: np.nanpercentile(values, 25)),
            q75_sd_db=("sd_db", lambda values: np.nanpercentile(values, 75)),
            n=("sd_db", "size"),
        )
        .reset_index(drop=True)
    )

    # Metrics.
    metrics: dict[str, object] = {
        "n_subjects": int(hha.subjects.size),
        "wide_band_hz": [500.0, 4000.0],
        "median_within_subject_sd_500_4000Hz_db_by_family": {
            str(row.family): float(row.sd_reinsertion_db_median)
            for row in wide_band.itertuples()
        },
        "repeatability_coefficient_500_4000Hz_db_by_family": {
            str(row.family): float(row.repeatability_coefficient_db)
            for row in wide_band.itertuples()
        },
        "icc_2_1_500_4000Hz_by_family": {
            str(row.family): float(row.icc_2_1) for row in wide_band.itertuples()
        },
        "overall_median_sd_500_4000Hz_db": float(np.nanmedian(wide_band["sd_reinsertion_db_median"])),
        "worst_band": {
            "band": str(summary.loc[summary["sd_reinsertion_db_median"].idxmax(), "band"]),
            "family": str(summary.loc[summary["sd_reinsertion_db_median"].idxmax(), "family"]),
            "sd_db": float(np.nanmax(summary["sd_reinsertion_db_median"])),
        },
        "note": (
            "SD is taken across the three reinsertions of the same subject; "
            "the probe tubes stayed in place between reinsertions."
        ),
    }
    if metrics["overall_median_sd_500_4000Hz_db"] > 3.0:
        warnings.append(
            "Median reinsertion SD exceeds 3 dB; effect estimates must be interpreted "
            "against this repeatability floor."
        )

    # Figures.
    figures = {}
    ax = viz.curves_plot(
        frequency_summary,
        x_col="frequency_hz",
        y_col="median_sd_db",
        hue_col="family",
        title="Within-subject reinsertion SD of Hha",
        ylabel="SD across reinsertions [dB]",
        x_limits=(50, 20000),
    )
    figures["reinsertion_sd_spectrum"] = ax.figure

    ax = viz.band_bar_plot(
        summary,
        band_col="band",
        value_col="sd_reinsertion_db_median",
        hue_col="family",
        title="Reinsertion SD per octave band (median across ears)",
        ylabel="SD [dB]",
        y_reference=None,
    )
    figures["reinsertion_sd_bands"] = ax.figure

    ax = viz.band_bar_plot(
        summary,
        band_col="band",
        value_col="icc_2_1",
        hue_col="family",
        title="ICC(2,1) between reinsertions per octave band",
        ylabel="ICC",
        y_reference=None,
    )
    ax.set_ylim(0.0, 1.0)
    figures["icc_bands"] = ax.figure

    # One concrete example: three reinsertions of one ear.
    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    device_index = 0
    subject_index = 0
    device = hha.devices[device_index]
    subject = int(hha.subjects[subject_index])
    levels = hha.level_array(reference=1.0)
    freq = hha.freq_hz
    keep = freq >= 50.0
    for reinsertion_index, reinsertion in enumerate(hha.reinsertions):
        ax.plot(
            freq[keep],
            levels[keep, device_index, subject_index, reinsertion_index],
            label=f"Reinsertion {int(reinsertion)}",
            linewidth=1.2,
        )
    ax.set_xscale("log")
    ax.set_xlim(50, 20000)
    ax.set_xlabel("Frequency [Hz]")
    ax.set_ylabel("Hha [dB SPL @ 11.2 mV]")
    ax.set_title(f"Reinsertion overlay — {device.label}, subject {subject}")
    ax.legend(frameon=False)
    figures["reinsertion_example"] = fig

    narrative = (
        "Reinsertion variability is a few dB in the mid frequencies and grows at the "
        "spectral extremes and for loosely coupled domes. The repeatability coefficient "
        "sets the smallest probe-tube presence effect that can be resolved for a single "
        "ear; the ICC indicates how much of the between-measurement variance is explained "
        "by the subject (high ICC = the ear dominates, low ICC = reinsertion noise dominates)."
    )

    return ExperimentResult(
        code=CODE,
        title=TITLE,
        metrics=metrics,
        tables={
            "repeatability_summary": summary,
            "repeatability_wide_band": wide_band,
            "reinsertion_sd_by_frequency": frequency_sd,
            "reinsertion_sd_frequency_summary": frequency_summary,
        },
        figures=figures,
        warnings=warnings,
        narrative=narrative,
    )
