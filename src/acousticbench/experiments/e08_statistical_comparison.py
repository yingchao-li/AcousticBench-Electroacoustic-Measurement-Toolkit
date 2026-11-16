"""E08 — Statistical Comparison.

Subject-level paired inference with effect sizes and bootstrap confidence
intervals.  The three reinsertions are averaged within subject **before** any
test; the subject is the independent statistical unit.

Tests performed
---------------
1. ``Hha`` at 1 kHz: closed earmold vs. open dome (paired across 14 ears).
2. Probe-tube presence effect on ``Hha`` at the 125 Hz band: one-sample test
   against zero for each earmold family.
3. Probe-tube presence effect on ``REOIG`` at the 1 kHz band: one-sample test
   against zero for each earmold family.
4. Threshold-based PTPE ``ΔT`` at 125 Hz: one-sample test against zero for all
   seven families (extends the analysis to domes).
5. Systematic probe-to-probe bias at 1 kHz (measurement condition, earmolds).
6. Contrast: closed earmold vs. power dome threshold PTPE at 125 Hz.

All family-level tests are Holm-corrected together.  Each result reports the
mean difference, Student-t 95 % CI, percentile bootstrap 95 % CI, Cohen's
``d_z``, rank-biserial effect size and the Shapiro–Wilk normality p-value of
the paired differences.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from acousticbench.experiments.base import ExperimentContext, ExperimentResult
from acousticbench.experiments.common import nearest_frequency
from acousticbench.measurements.ptpe import (
    probe_bias_db,
    ptpe_hha_band_levels,
    ptpe_reoig_band_levels,
    ptpe_threshold_db,
)
from acousticbench.measurements.transfer import hha_db_spl
from acousticbench.report import figures as viz
from acousticbench.stats import (
    bootstrap_paired_ci,
    holm_bonferroni,
    normality_check,
    paired_t_test,
    wilcoxon_signed_rank,
)
from acousticbench.types import Condition, Probe

CODE = "E08"
TITLE = "Statistical Comparison"
DESCRIPTION = (
    "Subject-level paired tests with effect sizes, bootstrap 95 % CIs and Holm correction."
)


def _subject_values_at_frequency(
    cube,
    family: str,
    frequency_hz: float,
    *,
    reference: float = 1.0,
) -> np.ndarray:
    """Subject-level means at the nearest frequency bin for one family."""
    levels = cube.level_array(reference=reference)
    index = int(np.argmin(np.abs(cube.freq_hz - frequency_hz)))
    device_index = next(i for i, device in enumerate(cube.devices) if device.family == family)
    values = levels[index, device_index]  # subjects × reinsertions
    with np.errstate(invalid="ignore"):
        return np.nanmean(values, axis=1)


def _band_subject_values(frame: pd.DataFrame, band: str, family: str) -> np.ndarray:
    subset = frame.loc[(frame["band"] == band) & (frame["family"] == family) & frame["valid"]]
    if subset.empty:
        return np.array([])
    collapsed = subset.groupby("subject", as_index=True)["ptpe_db"].mean()
    return collapsed.to_numpy(dtype=float)


def _threshold_subject_values(dataset, family: str, frequency_hz: float = 125.0) -> np.ndarray:
    cube = ptpe_threshold_db(dataset)
    index = int(np.argmin(np.abs(cube.freq_hz - frequency_hz)))
    device_index = next(i for i, device in enumerate(cube.devices) if device.family == family)
    values = cube.masked[index, device_index]  # subjects × reinsertions
    with np.errstate(invalid="ignore"):
        return np.nanmean(values, axis=1)


def _threshold_condition_subject_values(dataset, family: str, condition: Condition) -> np.ndarray:
    cube = dataset.threshold(conditions=[condition])
    curves = cube
    index = int(np.argmin(np.abs(curves.freq_hz - 1000.0)))
    device_index = next(i for i, device in enumerate(curves.devices) if device.family == family)
    values = curves.masked[index, device_index]
    with np.errstate(invalid="ignore"):
        return np.nanmean(values, axis=1)


def _probe_bias_subject_values(dataset, frequency_hz: float = 1000.0) -> np.ndarray:
    cube = probe_bias_db(dataset, condition=Condition.MEASUREMENT)
    index = int(np.argmin(np.abs(cube.freq_hz - frequency_hz)))
    values = cube.masked[index]  # earmold devices × subjects × reinsertions
    with np.errstate(invalid="ignore"):
        per_device_subject = np.nanmean(values, axis=2)  # devices × subjects
        return np.nanmean(per_device_subject, axis=0)  # one value per subject


def run(context: ExperimentContext) -> ExperimentResult:
    dataset = context.dataset
    bands = context.bands()
    config = context.config
    seed = config.analysis.bootstrap.seed
    n_resamples = config.analysis.bootstrap.n_resamples
    confidence = config.analysis.bootstrap.confidence
    warnings: list[str] = []

    hha = hha_db_spl(dataset, probe=Probe.MEASUREMENT, condition=Condition.MEASUREMENT)
    closed = _subject_values_at_frequency(hha, "closed_earmold", 1000.0)
    open_dome = _subject_values_at_frequency(hha, "open_dome", 1000.0)

    hha_bands = ptpe_hha_band_levels(dataset, bands)
    reoig_bands = ptpe_reoig_band_levels(dataset, bands)
    earmold_families = ("closed_earmold", "vented_earmold", "nugget_earmold", "silicone_earmold")
    all_families = (
        "closed_earmold",
        "vented_earmold",
        "nugget_earmold",
        "silicone_earmold",
        "open_dome",
        "tulip_dome",
        "power_dome",
    )

    tests: list[dict[str, object]] = []
    subject_rows: list[dict[str, object]] = []

    def add_test(
        test_id: str,
        metric: str,
        family: str,
        comparison: str,
        a: np.ndarray,
        b: np.ndarray,
        *,
        correct: bool = True,
    ) -> np.ndarray:
        valid = np.isfinite(a) & np.isfinite(b)
        a_clean, b_clean = a[valid], b[valid]
        if a_clean.size < 3:
            warnings.append(f"Skipped {test_id}: only {a_clean.size} complete pairs.")
            return np.array([])
        ttest = paired_t_test(a_clean, b_clean, confidence=confidence)
        wilcoxon = wilcoxon_signed_rank(a_clean, b_clean)
        bootstrap = bootstrap_paired_ci(
            a_clean,
            b_clean,
            n_resamples=n_resamples,
            confidence=confidence,
            seed=seed,
            method=config.analysis.bootstrap.method,
        )
        normality = normality_check(a_clean - b_clean)
        tests.append(
            {
                "test_id": test_id,
                "metric": metric,
                "family": family,
                "comparison": comparison,
                "n": int(ttest.n),
                "mean_a": ttest.mean_a,
                "mean_b": ttest.mean_b,
                "mean_diff": ttest.mean_diff,
                "ci_low": ttest.ci_low,
                "ci_high": ttest.ci_high,
                "bootstrap_ci_low": bootstrap.ci_low,
                "bootstrap_ci_high": bootstrap.ci_high,
                "t": ttest.t,
                "df": ttest.df,
                "p_value": ttest.p_value,
                "p_wilcoxon": wilcoxon["p_value"],
                "cohen_dz": ttest.effect_size,
                "rank_biserial": wilcoxon["effect_size"],
                "shapiro_p": normality.get("p_value"),
                "holm_family": "primary" if correct else "contrast",
            }
        )
        for subject, value_a, value_b in zip(
            dataset.subjects[valid], a_clean, b_clean
        ):
            subject_rows.append(
                {
                    "test_id": test_id,
                    "metric": metric,
                    "family": family,
                    "subject": int(subject),
                    "a": float(value_a),
                    "b": float(value_b),
                    "difference": float(value_a - value_b),
                }
            )
        return a_clean - b_clean

    add_test(
        "hha_1kHz_closed_vs_open",
        "Hha@1kHz",
        "closed_vs_open",
        "closed earmold − open dome",
        closed,
        open_dome,
        correct=False,
    )
    for family in earmold_families:
        values = _band_subject_values(hha_bands, "125 Hz", family)
        add_test(
            f"ptpe_hha_125Hz_{family}",
            "ΔHha@125Hz",
            family,
            "PTPE vs 0",
            values,
            np.zeros_like(values),
        )
    for family in earmold_families:
        values = _band_subject_values(reoig_bands, "1000 Hz", family)
        add_test(
            f"ptpe_reoig_1kHz_{family}",
            "ΔREOIG@1kHz",
            family,
            "PTPE vs 0",
            values,
            np.zeros_like(values),
        )
    for family in all_families:
        values = _threshold_subject_values(dataset, family, 125.0)
        add_test(
            f"ptpe_threshold_125Hz_{family}",
            "ΔT@125Hz",
            family,
            "PTPE vs 0",
            values,
            np.zeros_like(values),
        )
    bias = _probe_bias_subject_values(dataset, 1000.0)
    add_test(
        "probe_bias_1kHz",
        "MPT−RPT@1kHz",
        "earmolds",
        "bias vs 0",
        bias,
        np.zeros_like(bias),
        correct=False,
    )
    delta_t_closed = _threshold_subject_values(dataset, "closed_earmold", 125.0)
    delta_t_power = _threshold_subject_values(dataset, "power_dome", 125.0)
    add_test(
        "ptpe_threshold_closed_vs_power",
        "ΔT@125Hz",
        "closed_vs_power",
        "closed earmold − power dome",
        delta_t_closed,
        delta_t_power,
        correct=False,
    )

    results = pd.DataFrame(tests)
    primary_mask = results["holm_family"] == "primary"
    results["p_holm"] = np.nan
    if primary_mask.any():
        results.loc[primary_mask, "p_holm"] = holm_bonferroni(
            results.loc[primary_mask, "p_value"].to_numpy(dtype=float)
        )
    results["significant_holm"] = results["p_holm"] < config.analysis.alpha
    subject_data = pd.DataFrame(subject_rows)

    metrics: dict[str, object] = {
        "n_tests": int(len(results)),
        "n_primary_family_tests": int(primary_mask.sum()),
        "alpha": config.analysis.alpha,
        "correction": "holm (within primary family tests)",
        "bootstrap": {
            "n_resamples": n_resamples,
            "confidence": confidence,
            "seed": seed,
            "method": config.analysis.bootstrap.method,
        },
        "significant_tests_holm": results.loc[results["significant_holm"], "test_id"].tolist(),
        "closed_vs_open_hha_1kHz_mean_difference_db": float(
            results.loc[results["test_id"] == "hha_1kHz_closed_vs_open", "mean_diff"].iloc[0]
        ),
        "closed_vs_open_hha_1kHz_p_value": float(
            results.loc[results["test_id"] == "hha_1kHz_closed_vs_open", "p_value"].iloc[0]
        ),
        "probe_bias_1kHz_mean_db": float(
            results.loc[results["test_id"] == "probe_bias_1kHz", "mean_diff"].iloc[0]
        ),
        "probe_bias_1kHz_p_value": float(
            results.loc[results["test_id"] == "probe_bias_1kHz", "p_value"].iloc[0]
        ),
        "note": (
            "Differences are a − b. Positive ΔREOIG means more leakage; negative ΔHha/ΔT "
            "mean reduced driver output."
        ),
    }
    if (results["n"] < 5).any():
        warnings.append("At least one test has fewer than 5 complete subject pairs.")
    if np.any(results["shapiro_p"].dropna() < 0.05):
        warnings.append(
            "Shapiro–Wilk indicates non-normal paired differences in at least one test; "
            "Wilcoxon p-values are reported alongside the t-tests."
        )

    figures = {}
    forest_frame = results.copy()
    forest_frame["label"] = forest_frame["metric"] + " · " + forest_frame["family"]
    forest_frame = forest_frame.sort_values(["metric", "mean_diff"])
    ax = viz.forest_plot(
        forest_frame,
        estimate_col="mean_diff",
        low_col="bootstrap_ci_low",
        high_col="bootstrap_ci_high",
        label_col="label",
        title="Paired effects with subject-level bootstrap 95 % CIs",
        xlabel="Mean paired difference [dB]",
        color_by="family",
    )
    figures["forest_effects"] = ax.figure

    fig, ax = plt.subplots(figsize=(5.4, 4.6))
    limit = [
        float(np.nanmin([np.nanmin(closed), np.nanmin(open_dome)])),
        float(np.nanmax([np.nanmax(closed), np.nanmax(open_dome)])),
    ]
    ax.scatter(closed, open_dome, s=26, color="#1f77b4")
    ax.plot(limit, limit, "k--", linewidth=0.8)
    ax.set_xlabel("Closed earmold Hha at 1 kHz [dB SPL]")
    ax.set_ylabel("Open dome Hha at 1 kHz [dB SPL]")
    ax.set_title("Paired comparison across 14 ears")
    figures["closed_vs_open_scatter"] = fig

    fig, ax = plt.subplots(figsize=(8.0, 3.6))
    labels = []
    data = []
    for test_id, group in subject_data.groupby("test_id", sort=False):
        if test_id.startswith(("ptpe_hha", "ptpe_threshold", "probe_bias")):
            labels.append(test_id.replace("ptpe_", "").replace("_Hz_", " "))
            data.append(group["difference"].to_numpy(dtype=float))
    if data:
        ax.boxplot(data, tick_labels=labels, showmeans=True, meanline=True)
        ax.axhline(0.0, color="k", linewidth=0.8)
        ax.set_ylabel("Paired difference [dB]")
        ax.set_title("Subject-level paired differences (primary family tests)")
        ax.tick_params(axis="x", labelrotation=25, labelsize=7)
    figures["paired_differences"] = fig

    narrative = (
        "All probe-tube presence effects are tested at the subject level with paired designs "
        "and interpreted against effect sizes and 95 % confidence intervals rather than "
        "p-values alone. Holm correction controls the family-wise error rate across the "
        "family-level tests. The closed-vs-open comparison quantifies the large acoustic "
        "difference between occluding and open couplings, while the probe-bias test shows "
        "whether the two probe microphones differ systematically."
    )

    return ExperimentResult(
        code=CODE,
        title=TITLE,
        metrics=metrics,
        tables={
            "paired_tests": results,
            "subject_level_data": subject_data,
        },
        figures=figures,
        warnings=warnings,
        narrative=narrative,
    )
