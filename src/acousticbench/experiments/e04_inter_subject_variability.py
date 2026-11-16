"""E04 — Inter-subject Variability.

Quantifies how much Hha differs between the 14 ears (between-subject variance)
relative to the reinsertion noise (within-subject variance).  The one-way
random-effects decomposition separates the two components and reports
``ICC(1,1)``, the fraction of total variance attributable to the ear.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from acousticbench.experiments.base import ExperimentContext, ExperimentResult
from acousticbench.experiments.common import band_summary, nearest_frequency
from acousticbench.measurements.transfer import hha_db_spl
from acousticbench.measurements.variability import (
    inter_subject_variability,
    variability_by_device,
    variance_components,
)
from acousticbench.report import figures as viz
from acousticbench.types import Condition, Probe

CODE = "E04"
TITLE = "Inter-subject Variability"
DESCRIPTION = (
    "Between-subject spread of Hha and its decomposition into between-ear and "
    "reinsertion variance components."
)


def run(context: ExperimentContext) -> ExperimentResult:
    dataset = context.dataset
    bands = context.bands()
    warnings: list[str] = []

    hha = hha_db_spl(dataset, probe=Probe.MEASUREMENT, condition=Condition.MEASUREMENT)
    summary = inter_subject_variability(hha, bands, reference=1.0)
    wide_band = variability_by_device(hha, reference=1.0)
    levels = hha.level_array(reference=1.0)

    # Frequency-resolved between-subject SD.
    with np.errstate(invalid="ignore"):
        subject_mean = np.nanmean(levels, axis=3)
        sd_across_subjects = np.nanstd(subject_mean, axis=2, ddof=1)
    frequency_rows = []
    for device_index, device in enumerate(hha.devices):
        frequency_rows.append(
            pd.DataFrame(
                {
                    "frequency_hz": hha.freq_hz,
                    "device_code": device.code,
                    "family": device.family,
                    "family_label": device.family_label,
                    "sd_between_subject_db": sd_across_subjects[:, device_index],
                    "n_subjects": np.sum(np.isfinite(subject_mean[:, device_index, :]), axis=1),
                }
            )
        )
    frequency_sd = pd.concat(frequency_rows, ignore_index=True)
    frequency_sd = frequency_sd.loc[frequency_sd["frequency_hz"] >= 50.0]
    frequency_summary = (
        frequency_sd.groupby(["family", "frequency_hz"], as_index=False)
        .agg(
            median_sd_db=("sd_between_subject_db", "median"),
            q25_sd_db=("sd_between_subject_db", lambda values: np.nanpercentile(values, 25)),
            q75_sd_db=("sd_between_subject_db", lambda values: np.nanpercentile(values, 75)),
        )
        .reset_index(drop=True)
    )

    metrics: dict[str, object] = {
        "n_subjects": int(hha.subjects.size),
        "between_subject_sd_500_4000Hz_db_by_family": {
            str(row.family): float(row.sd_between_subject_db)
            for row in wide_band.itertuples()
        },
        "icc_1_1_500_4000Hz_by_family": {
            str(row.family): float(row.icc_1_1) for row in wide_band.itertuples()
        },
        "within_subject_sd_500_4000Hz_db_by_family": {
            str(row.family): float(np.sqrt(row.within_subject_variance_db2))
            for row in wide_band.itertuples()
        },
        "ratio_between_to_within_by_family": {
            str(row.family): float(
                np.sqrt(row.between_subject_variance_db2)
                / max(np.sqrt(row.within_subject_variance_db2), 1e-12)
            )
            for row in wide_band.itertuples()
        },
        "note": (
            "Between-subject SD uses subject-level means (reinsertions averaged); "
            "variance components are one-way random-effects estimates."
        ),
    }
    if metrics["between_subject_sd_500_4000Hz_db_by_family"]:
        worst = max(
            metrics["between_subject_sd_500_4000Hz_db_by_family"].items(),
            key=lambda item: item[1],
        )
        metrics["most_variable_family"] = {"family": worst[0], "sd_db": worst[1]}
        if worst[1] < 2.0:
            warnings.append(
                "Between-subject SD is unexpectedly small; check the analysis band."
            )

    figures = {}
    ax = viz.curves_plot(
        frequency_summary,
        x_col="frequency_hz",
        y_col="median_sd_db",
        hue_col="family",
        title="Between-subject SD of Hha",
        ylabel="SD across ears [dB]",
        x_limits=(50, 20000),
    )
    figures["between_subject_sd_spectrum"] = ax.figure

    ax = viz.band_bar_plot(
        summary,
        band_col="band",
        value_col="sd_between_subject_db",
        hue_col="family",
        title="Between-subject SD per octave band",
        ylabel="SD [dB]",
        y_reference=None,
    )
    figures["between_subject_sd_bands"] = ax.figure

    fig, ax = plt.subplots(figsize=(8.2, 3.6))
    families = wide_band["family"].tolist()
    between = np.sqrt(wide_band["between_subject_variance_db2"].to_numpy(dtype=float))
    within = np.sqrt(wide_band["within_subject_variance_db2"].to_numpy(dtype=float))
    x = np.arange(len(families))
    ax.bar(x, between, color="#1f77b4", label="between-ear SD")
    ax.bar(x, within, bottom=between, color="#ff7f0e", label="reinsertion SD")
    ax.set_xticks(x, [viz.FAMILY_LABELS.get(f, f) for f in families], rotation=20, ha="right")
    ax.set_ylabel("SD [dB]")
    ax.set_title("Variance decomposition of Hha (500–4000 Hz)")
    ax.legend(frameon=False)
    figures["variance_decomposition"] = fig

    ax = viz.heatmap_plot(
        summary,
        index_col="family",
        columns_col="band",
        value_col="sd_between_subject_db",
        title="Between-subject SD per octave band",
        xlabel="Octave band",
        colorbar_label="SD [dB]",
        cmap="magma",
        center=None,
    )
    figures["between_subject_heatmap"] = ax.figure

    narrative = (
        "Between-ear differences dominate the reinsertion noise for occluding couplings, "
        "especially at low frequencies where ear-canal volume and earpiece fit vary "
        "strongly. For open domes the between-ear spread is smaller at low frequencies "
        "but still substantial. This justifies treating the subject as the independent "
        "statistical unit and using paired designs wherever possible."
    )

    return ExperimentResult(
        code=CODE,
        title=TITLE,
        metrics=metrics,
        tables={
            "inter_subject_variability": summary,
            "inter_subject_variability_wide_band": wide_band,
            "between_subject_sd_by_frequency": frequency_sd,
            "between_subject_sd_frequency_summary": frequency_summary,
        },
        figures=figures,
        warnings=warnings,
        narrative=narrative,
    )
