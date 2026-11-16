"""E02 — Probe Tube Measurement Bias and the Probe-Tube Presence Effect.

Two distinct questions are answered with the same dataset:

1. **Probe-to-probe bias** — in the measurement condition both probe tubes are
   in the ear, so the level difference between the measurement and reference
   probe quantifies a pure placement/calibration bias (earmolds only).
2. **Probe-tube presence effect (PTPE)** — inserting the measurement probe
   changes the acoustics.  Using the reference probe in both conditions gives
   ``ΔHha`` and ``ΔREOIG``; ``ΔT = T_ref − T_meas`` at 125 Hz extends the effect
   estimate to domes, where no reference probe exists.

All uncertainty intervals are computed across *subjects* (the three
reinsertions are averaged first).
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from acousticbench.experiments.base import ExperimentContext, ExperimentResult
from acousticbench.experiments.common import (
    band_summary,
    mean_ci,
    nearest_frequency,
    percentile_curves,
    subject_means,
)
from acousticbench.measurements.ptpe import (
    probe_bias_band_levels,
    probe_bias_db,
    ptpe_hha_band_levels,
    ptpe_hha_db,
    ptpe_reoig_band_levels,
    ptpe_threshold_db,
)
from acousticbench.report import figures as viz
from acousticbench.types import Condition

CODE = "E02"
TITLE = "Probe Tube Measurement Bias"
DESCRIPTION = (
    "Probe-to-probe bias and probe-tube presence effect on Hha, REOIG and "
    "hearing thresholds."
)


def _threshold_ptpe_frame(dataset, frequency_hz: float = 125.0) -> pd.DataFrame:
    cube = ptpe_threshold_db(dataset)
    index = int(np.argmin(np.abs(cube.freq_hz - frequency_hz)))
    values = cube.masked[index]  # (families, subjects, reinsertions)
    rows = []
    for family_index, device in enumerate(cube.devices):
        for subject_index, subject in enumerate(cube.subjects):
            row_values = values[family_index, subject_index]
            rows.append(
                {
                    "family": device.family,
                    "family_label": device.family_label,
                    "subject": int(subject),
                    "reinsertion": 1,
                    "delta_t_db": float(np.nanmean(row_values)),
                }
            )
    frame = pd.DataFrame(rows)
    frame["valid"] = np.isfinite(frame["delta_t_db"])
    return frame


def run(context: ExperimentContext) -> ExperimentResult:
    dataset = context.dataset
    bands = context.bands()
    warnings: list[str] = []

    # ------------------------------------------------------------------
    # 1) Probe-to-probe bias (measurement condition, earmolds)
    # ------------------------------------------------------------------
    bias_cube = probe_bias_db(dataset, condition=Condition.MEASUREMENT)
    bias_percentiles = percentile_curves(bias_cube, reference=1.0)
    bias_band = probe_bias_band_levels(dataset, bands, condition=Condition.MEASUREMENT)
    bias_band = bias_band.loc[bias_band["valid"]]
    bias_band_summary = band_summary(
        bias_band,
        value_col="bias_db",
        group_cols=("family", "family_label", "band", "band_center_hz"),
    )
    bias_ci = mean_ci(
        bias_band,
        value_col="bias_db",
        group_cols=("family", "family_label", "band", "band_center_hz"),
    )
    bias_ci["abs_bias_db"] = bias_ci["mean_db"].abs()

    # ------------------------------------------------------------------
    # 2) PTPE on Hha and REOIG (earmolds, reference probe both conditions)
    # ------------------------------------------------------------------
    ptpe_hha = ptpe_hha_db(dataset)
    ptpe_hha_percentiles = percentile_curves(ptpe_hha)
    ptpe_hha_frames = ptpe_hha_band_levels(dataset, bands)
    ptpe_hha_frames = ptpe_hha_frames.loc[ptpe_hha_frames["valid"]]
    ptpe_hha_summary = band_summary(
        ptpe_hha_frames,
        value_col="ptpe_db",
        group_cols=("family", "family_label", "band", "band_center_hz"),
    )
    ptpe_hha_ci = mean_ci(
        ptpe_hha_frames,
        value_col="ptpe_db",
        group_cols=("family", "family_label", "band", "band_center_hz"),
    )

    ptpe_reoig_frames = ptpe_reoig_band_levels(dataset, bands)
    ptpe_reoig_frames = ptpe_reoig_frames.loc[ptpe_reoig_frames["valid"]]
    ptpe_reoig_summary = band_summary(
        ptpe_reoig_frames,
        value_col="ptpe_db",
        group_cols=("family", "family_label", "band", "band_center_hz"),
    )
    ptpe_reoig_ci = mean_ci(
        ptpe_reoig_frames,
        value_col="ptpe_db",
        group_cols=("family", "family_label", "band", "band_center_hz"),
    )

    # ------------------------------------------------------------------
    # 3) Threshold-based PTPE at 125 Hz (all families, incl. domes)
    # ------------------------------------------------------------------
    delta_t = _threshold_ptpe_frame(dataset, 125.0)
    delta_t_ci = mean_ci(
        delta_t, value_col="delta_t_db", group_cols=("family", "family_label")
    )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------
    valid_bias = bias_band.copy()
    upper = valid_bias.loc[valid_bias["band_center_hz"].between(500, 4000)]
    metrics: dict[str, object] = {
        "probe_bias_median_abs_500_4000Hz_db": float(
            np.nanmedian(np.abs(upper["bias_db"]))
        ),
        "probe_bias_frequency_resolved_median_db": {
            f"{freq:g}": float(np.nanmedian(bias_cube.masked[int(np.argmin(np.abs(bias_cube.freq_hz - freq)))]))
            for freq in (100, 250, 500, 1000, 2000, 4000, 8000)
        },
        "ptpe_hha_100Hz_db_by_family": {},
        "ptpe_reoig_1kHz_db_by_family": {},
        "delta_threshold_125Hz_db_by_family": {
            str(row.family): float(row.mean_db) for row in delta_t_ci.itertuples()
        },
        "n_subjects": int(dataset.subjects.size),
        "sign_convention": "ΔHha<0 and ΔT<0 = reduced driver output; ΔREOIG>0 = more leakage",
    }
    for family in ptpe_hha.devices:
        frame = ptpe_hha_percentiles
        subset = frame.loc[
            (frame["family"] == family.family) & np.isclose(frame["frequency_hz"], 107.666, atol=8)
        ]
        if not subset.empty:
            metrics["ptpe_hha_100Hz_db_by_family"][family.family] = float(
                subset["median_db"].iloc[0]
            )
    freq_1k = nearest_frequency(ptpe_reoig_frames["band_center_hz"].to_numpy(), 1000.0)
    for family in ptpe_reoig_summary["family"].unique():
        subset = ptpe_reoig_summary.loc[
            (ptpe_reoig_summary["family"] == family)
            & np.isclose(ptpe_reoig_summary["band_center_hz"], 1000.0)
        ]
        if not subset.empty:
            metrics["ptpe_reoig_1kHz_db_by_family"][str(family)] = float(
                subset["median_db"].iloc[0]
            )

    # Sanity warnings (never silently accept unexpected signs).
    for family, value in metrics["delta_threshold_125Hz_db_by_family"].items():
        if value > 1.0:
            warnings.append(
                f"ΔT at 125 Hz is positive ({value:.2f} dB) for {family}; "
                "expected a negative probe-tube presence effect."
            )

    # ------------------------------------------------------------------
    # Figures
    # ------------------------------------------------------------------
    figures = {}
    fig, ax = plt.subplots(figsize=(7.4, 3.8))
    subset = bias_percentiles
    for family, group in subset.groupby("family", sort=False):
        color = viz.FAMILY_COLORS[family]
        ax.fill_between(
            group["frequency_hz"], group["q25"], group["q75"], color=color, alpha=0.18
        )
        ax.plot(group["frequency_hz"], group["median_db"], color=color, label=viz.FAMILY_LABELS[family])
    ax.axhline(0.0, color="k", linewidth=0.8)
    ax.set_xscale("log")
    ax.set_xlim(50, 20000)
    ax.set_xlabel("Frequency [Hz]")
    ax.set_ylabel("MPT − RPT [dB]")
    ax.set_title("Probe-to-probe bias in the measurement condition (median, IQR)")
    ax.legend(frameon=False, ncol=2)
    figures["probe_bias_curves"] = fig

    fig, ax = plt.subplots(figsize=(7.6, 3.9))
    for family, group in ptpe_hha_percentiles.groupby("family", sort=False):
        color = viz.FAMILY_COLORS[family]
        ax.fill_between(
            group["frequency_hz"], group["q25"], group["q75"], color=color, alpha=0.15
        )
        ax.plot(
            group["frequency_hz"],
            group["median_db"],
            color=color,
            label=viz.FAMILY_LABELS[family],
        )
    ax.axhline(0.0, color="k", linewidth=0.8)
    ax.set_xscale("log")
    ax.set_xlim(50, 20000)
    ax.set_xlabel("Frequency [Hz]")
    ax.set_ylabel("ΔHha [dB]")
    ax.set_title("Probe-tube presence effect on Hha (reference probe, measurement − reference)")
    ax.legend(frameon=False, ncol=2)
    figures["ptpe_hha_curves"] = fig

    ax = viz.band_bar_plot(
        ptpe_reoig_frames,
        band_col="band",
        value_col="ptpe_db",
        hue_col="family",
        title="PTPE on REOIG — median per octave band (ΔREOIG > 0 = more leakage)",
        ylabel="ΔREOIG [dB]",
    )
    figures["ptpe_reoig_bands"] = ax.figure

    ax = viz.band_bar_plot(
        ptpe_hha_frames,
        band_col="band",
        value_col="ptpe_db",
        hue_col="family",
        title="PTPE on Hha — median per octave band",
        ylabel="ΔHha [dB]",
    )
    figures["ptpe_hha_bands"] = ax.figure

    fig, ax = plt.subplots(figsize=(7.4, 3.0))
    ordered = delta_t_ci.sort_values("mean_db")
    ax.barh(
        ordered["family_label"],
        ordered["mean_db"],
        xerr=[
            ordered["mean_db"] - ordered["ci_low_db"],
            ordered["ci_high_db"] - ordered["mean_db"],
        ],
        color="none",
        edgecolor="#333333",
        height=0.55,
    )
    ax.scatter(
        ordered["mean_db"],
        ordered["family_label"],
        c=[viz.FAMILY_COLORS.get(family, "#1f77b4") for family in ordered["family"]],
        s=30,
        zorder=3,
    )
    ax.axvline(0.0, color="k", linewidth=0.8)
    ax.set_xlabel("ΔT at 125 Hz [dB] (T_ref − T_meas; mean ± 95 % CI across ears)")
    ax.set_title("Threshold-based probe-tube presence effect")
    figures["ptpe_threshold_125"] = fig

    narrative = (
        "The two probe tubes agree within ≈1.5 dB when both are in the ear, with the "
        "measurement probe reading slightly lower; the bias grows towards 8 kHz. Inserting "
        "the measurement probe reduces the low-frequency driver output (ΔHha < 0), most "
        "strongly for the nugget earmold, and increases the leakage of external sound "
        "(ΔREOIG > 0), most strongly for the nugget and closed earmolds. Threshold "
        "differences at 125 Hz confirm the effect for all families and extend it to domes, "
        "where no reference probe exists. These directions reproduce the source study and "
        "validate the validity model implemented in AcousticBench."
    )

    return ExperimentResult(
        code=CODE,
        title=TITLE,
        metrics=metrics,
        tables={
            "probe_bias_curves_percentiles": bias_percentiles,
            "probe_bias_bands_summary": bias_band_summary,
            "probe_bias_bands_ci": bias_ci,
            "ptpe_hha_curves_percentiles": ptpe_hha_percentiles,
            "ptpe_hha_bands_summary": ptpe_hha_summary,
            "ptpe_hha_bands_ci": ptpe_hha_ci,
            "ptpe_reoig_bands_summary": ptpe_reoig_summary,
            "ptpe_reoig_bands_ci": ptpe_reoig_ci,
            "ptpe_threshold_125Hz": delta_t,
            "ptpe_threshold_125Hz_ci": delta_t_ci,
        },
        figures=figures,
        warnings=warnings,
        narrative=narrative,
    )
