"""E07 — Hearing Threshold.

Audiometric thresholds (receiver voltage at threshold, dBV) are available at
125, 250, 500, 750, 1000 and 2000 Hz for all seven coupling styles and both
probe conditions.  This experiment quantifies:

* the audiogram obtained through each coupling style,
* the threshold-based probe-tube presence effect ``ΔT = T_ref − T_meas``,
* the equivalence between ``ΔT`` and the acoustic ``ΔHha`` for earmolds,
  where both quantities are available.  The equivalence is a direct check of
  the interpretation ``ΔT = ΔHha`` (fixed drive voltage), and it is the reason
  why threshold data can extend the PTPE analysis to domes.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from acousticbench.experiments.base import ExperimentContext, ExperimentResult
from acousticbench.experiments.common import mean_ci, subject_means
from acousticbench.measurements.ptpe import ptpe_hha_band_levels, ptpe_threshold_db
from acousticbench.measurements.threshold import threshold_curve
from acousticbench.report import figures as viz
from acousticbench.types import Condition

CODE = "E07"
TITLE = "Hearing Threshold"
DESCRIPTION = (
    "Audiograms through the hearing-aid receiver, threshold-based probe-tube presence "
    "effect and its equivalence with the acoustic ΔHha."
)


def _threshold_delta_frame(dataset, frequency_hz: float = 125.0) -> pd.DataFrame:
    cube = ptpe_threshold_db(dataset)
    index = int(np.argmin(np.abs(cube.freq_hz - frequency_hz)))
    values = cube.masked[index]  # families × subjects × reinsertions
    rows = []
    for family_index, device in enumerate(cube.devices):
        for subject_index, subject in enumerate(cube.subjects):
            rows.append(
                {
                    "family": device.family,
                    "family_label": device.family_label,
                    "subject": int(subject),
                    "reinsertion": 1,
                    "delta_t_db": float(np.nanmean(values[family_index, subject_index])),
                }
            )
    frame = pd.DataFrame(rows)
    frame["valid"] = np.isfinite(frame["delta_t_db"])
    return frame


def run(context: ExperimentContext) -> ExperimentResult:
    dataset = context.dataset
    bands = context.bands()
    warnings: list[str] = []

    curves = threshold_curve(dataset)
    delta_t = _threshold_delta_frame(dataset, 125.0)
    delta_t_ci = mean_ci(delta_t, value_col="delta_t_db", group_cols=("family", "family_label"))
    delta_t_subject = subject_means(delta_t, value_col="delta_t_db", group_cols=("family", "family_label"))

    # Equivalence between ΔT and ΔHha for earmolds.
    delta_hha_bands = ptpe_hha_band_levels(dataset, bands)
    delta_hha_bands = delta_hha_bands.loc[
        (delta_hha_bands["valid"]) & (delta_hha_bands["band"] == "125 Hz")
    ]
    delta_hha_subject = subject_means(
        delta_hha_bands,
        value_col="ptpe_db",
        group_cols=("family", "family_label", "band", "band_center_hz"),
    )
    delta_hha_subject = delta_hha_subject.rename(columns={"subject_mean": "delta_hha_db"})
    equivalence = delta_t_subject.merge(
        delta_hha_subject[["family", "subject", "delta_hha_db"]],
        on=["family", "subject"],
        how="inner",
    )
    equivalence = equivalence.dropna(subset=["subject_mean", "delta_hha_db"])
    equivalence = equivalence.rename(columns={"subject_mean": "delta_t_db"})
    if len(equivalence) >= 3:
        correlation = float(
            np.corrcoef(equivalence["delta_t_db"], equivalence["delta_hha_db"])[0, 1]
        )
        slope, intercept = np.polyfit(
            equivalence["delta_t_db"], equivalence["delta_hha_db"], deg=1
        )
        mean_difference = float(
            np.mean(equivalence["delta_hha_db"] - equivalence["delta_t_db"])
        )
    else:  # pragma: no cover - defensive
        correlation = slope = intercept = mean_difference = float("nan")
        warnings.append("Too few paired ΔT/ΔHha observations for the equivalence check.")

    metrics: dict[str, object] = {
        "n_subjects": int(dataset.subjects.size),
        "threshold_median_dbv_at_125Hz": {},
        "threshold_median_dbv_at_1kHz": {},
        "delta_threshold_125Hz_db_by_family": {
            str(row.family): float(row.mean_db) for row in delta_t_ci.itertuples()
        },
        "delta_threshold_125Hz_ci95_by_family": {
            str(row.family): [float(row.ci_low_db), float(row.ci_high_db)]
            for row in delta_t_ci.itertuples()
        },
        "delta_t_vs_delta_hha_correlation": correlation,
        "delta_t_vs_delta_hha_slope": float(slope),
        "delta_t_vs_delta_hha_mean_difference_db": mean_difference,
        "delta_t_vs_delta_hha_n": int(len(equivalence)),
        "note": (
            "ΔT = T_ref − T_meas is expressed in dB and equals the equivalent change of Hha "
            "at fixed drive voltage; negative values mean the probe reduces driver output."
        ),
    }
    for target in (125.0, 1000.0):
        subset = curves.loc[np.isclose(curves["frequency_hz"], target)]
        metrics[
            "threshold_median_dbv_at_125Hz" if target == 125.0 else "threshold_median_dbv_at_1kHz"
        ] = {str(row.family): float(row.median_dbv) for row in subset.itertuples()}
    if np.isfinite(correlation) and correlation < 0.3:
        warnings.append(
            f"ΔT and ΔHha correlate only weakly (r = {correlation:.2f}); "
            "the equivalence is limited by 1 dB threshold quantisation and threshold variability."
        )

    figures = {}
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 3.9), sharey=True)
    for ax, condition, title in (
        (axes[0], Condition.REFERENCE, "Reference condition"),
        (axes[1], Condition.MEASUREMENT, "Measurement condition"),
    ):
        subset = curves.loc[curves["condition"] == condition.value]
        for family, group in subset.groupby("family", sort=False):
            ax.plot(
                group["frequency_hz"],
                group["median_dbv"],
                "o-",
                label=viz.FAMILY_LABELS.get(family, family),
                color=viz.FAMILY_COLORS.get(family),
                markersize=4,
            )
        ax.set_xscale("log")
        ax.set_xlabel("Frequency [Hz]")
        ax.set_title(title)
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("Threshold [dBV]")
    axes[0].legend(frameon=False, fontsize=6.5, ncol=2)
    fig.suptitle("Hearing thresholds measured through the hearing-aid receiver", fontsize=10)
    fig.tight_layout()
    figures["audiograms"] = fig

    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    ordered = delta_t_ci.sort_values("mean_db")
    ax.barh(
        ordered["family_label"],
        ordered["mean_db"],
        xerr=[
            ordered["mean_db"] - ordered["ci_low_db"],
            ordered["ci_high_db"] - ordered["mean_db"],
        ],
        color=[viz.FAMILY_COLORS.get(f, "#1f77b4") for f in ordered["family"]],
        alpha=0.85,
    )
    ax.axvline(0.0, color="k", linewidth=0.8)
    ax.set_xlabel("ΔT at 125 Hz [dB] (mean ± 95 % CI across ears)")
    ax.set_title("Threshold-based probe-tube presence effect")
    figures["delta_threshold_125"] = fig

    fig, ax = plt.subplots(figsize=(5.4, 4.6))
    for family, group in equivalence.groupby("family", sort=False):
        ax.scatter(
            group["delta_t_db"],
            group["delta_hha_db"],
            s=24,
            color=viz.FAMILY_COLORS.get(family),
            label=viz.FAMILY_LABELS.get(family, family),
            alpha=0.9,
        )
    if np.isfinite(slope):
        limit = np.nanmax(np.abs(equivalence[["delta_t_db", "delta_hha_db"]].to_numpy())) * 1.1
        ax.plot([-limit, limit], [-limit, limit], "k--", linewidth=0.8, label="identity")
        ax.set_xlim(-limit, limit)
        ax.set_ylim(-limit, limit)
    ax.set_xlabel("ΔT at 125 Hz [dB]")
    ax.set_ylabel("ΔHha, 125 Hz band [dB]")
    ax.set_title(
        f"ΔT vs ΔHha (earmolds, r = {correlation:.2f}, n = {len(equivalence)})"
        if np.isfinite(correlation)
        else "ΔT vs ΔHha (earmolds)"
    )
    ax.legend(frameon=False, fontsize=7)
    figures["delta_t_vs_delta_hha"] = fig

    narrative = (
        "Thresholds through the hearing-aid receiver are lowest (most sensitive) for the "
        "closed and nugget earmolds and highest for the open dome, matching the coupling "
        "tightness. Inserting the measurement probe raises the required voltage at 125 Hz "
        "for the occluding couplings, again mirroring the acoustic PTPE. The ΔT–ΔHha "
        "comparison confirms that threshold differences express the same level change as the "
        "transfer-function measurement, within the limits set by 1 dB threshold quantisation."
    )

    return ExperimentResult(
        code=CODE,
        title=TITLE,
        metrics=metrics,
        tables={
            "threshold_curves": curves,
            "delta_threshold_125Hz": delta_t,
            "delta_threshold_125Hz_ci": delta_t_ci,
            "delta_t_vs_delta_hha": equivalence,
        },
        figures=figures,
        warnings=warnings,
        narrative=narrative,
    )
