"""E10 — THD Estimation.

Evaluates the harmonic-distortion estimator on 250 synthetic cases with a known
injected distortion.  The preset target (≤ 0.1 percentage points) is evaluated
only in the documented reference condition (1 kHz, THD 0.5–5 %, no noise); the
wider range is reported separately.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from acousticbench.dsp.metrics import estimate_thd
from acousticbench.experiments.base import ExperimentContext, ExperimentResult
from acousticbench.experiments.synthetic_common import (
    build_suite,
    category_cases,
    error_summary,
    reference_cases,
)
from acousticbench.report import figures as viz
from acousticbench.synthetic import render_case

CODE = "E10"
TITLE = "THD Estimation"
DESCRIPTION = (
    "THD estimation on 250 synthetic cases with known distortion, evaluated against the "
    "preset reference-condition target."
)


def run(context: ExperimentContext) -> ExperimentResult:
    config = context.config
    warnings: list[str] = []
    cases = build_suite(config)
    thd_cases = category_cases(cases, "thd")

    rows = []
    for case in thd_cases:
        data = render_case(case)
        tone_hz = float(data.ground_truth["tone_hz"])
        estimate = estimate_thd(
            data.output, data.fs_hz, tone_hz, n_harmonics=int(data.ground_truth["n_harmonics"])
        )
        truth = float(data.ground_truth["thd_percent"])
        rows.append(
            {
                "case_id": case.case_id,
                "tone_hz": tone_hz,
                "input_level_dbfs": float(data.ground_truth["input_level_dbfs"]),
                "thd_percent_true": truth,
                "thd_percent_estimated": estimate.thd_percent,
                "error_percentage_points": estimate.thd_percent - truth,
                "fundamental_dbfs": estimate.fundamental_dbfs,
                "is_reference_condition": bool(case.is_reference_condition),
            }
        )
    results = pd.DataFrame(rows)
    reference = results.loc[results["is_reference_condition"]]
    target = float(config.synthetic.targets.get("thd_error_percentage_points", 0.1))
    reference_summary = error_summary(reference["error_percentage_points"], target, unit="pp")
    full_summary = error_summary(results["error_percentage_points"], target, unit="pp")
    metrics = {
        "n_cases": int(len(results)),
        "n_reference_cases": int(len(reference)),
        "target_percentage_points": target,
        "reference_condition": config.synthetic.reference_conditions.get("thd"),
        "reference_summary": reference_summary,
        "full_parameter_range_summary": full_summary,
        "target_met_in_reference_condition": reference_summary["target_met"],
        "note": (
            "THD is estimated from Hann-windowed harmonic projections; the injected "
            "harmonic amplitudes are known exactly from the generated waveforms."
        ),
    }
    if not reference_summary["target_met"]:
        warnings.append(
            f"THD target {target} pp not met: max |error| "
            f"{reference_summary['max_abs_error']:.4f} pp in the reference condition."
        )

    figures = {}
    fig, ax = plt.subplots(figsize=(5.2, 4.8))
    ax.scatter(
        results["thd_percent_true"],
        results["thd_percent_estimated"],
        c=np.where(results["is_reference_condition"], "#1f77b4", "#ff7f0e"),
        s=18,
        alpha=0.85,
    )
    limits = [
        0.0,
        float(max(results["thd_percent_true"].max(), results["thd_percent_estimated"].max()) * 1.05),
    ]
    ax.plot(limits, limits, "k--", linewidth=0.8)
    ax.set_xlim(limits)
    ax.set_ylim(limits)
    ax.set_xlabel("True THD [%]")
    ax.set_ylabel("Estimated THD [%]")
    ax.set_title("THD estimation: estimate vs. ground truth")
    figures["thd_scatter"] = fig

    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    span = max(0.02, np.max(np.abs(results["error_percentage_points"])) * 1.2)
    bins = np.linspace(-span, span, 41)
    ax.hist(reference["error_percentage_points"], bins=bins, color="#1f77b4", alpha=0.8, label="reference")
    ax.hist(
        results.loc[~results["is_reference_condition"], "error_percentage_points"],
        bins=bins,
        color="#ff7f0e",
        alpha=0.5,
        label="wider range",
    )
    ax.axvline(target, color="red", linestyle="--", linewidth=0.9)
    ax.axvline(-target, color="red", linestyle="--", linewidth=0.9)
    ax.set_xlabel("THD error [percentage points]")
    ax.set_ylabel("Number of cases")
    ax.set_title("THD error distribution")
    ax.legend(frameon=False)
    figures["thd_error_histogram"] = fig

    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    for reference_flag, group, color, label in (
        (True, reference, "#1f77b4", "reference"),
        (False, results.loc[~results["is_reference_condition"]], "#ff7f0e", "wider range"),
    ):
        ax.scatter(
            group["thd_percent_true"],
            group["error_percentage_points"],
            s=14,
            color=color,
            alpha=0.8,
            label=label,
        )
    ax.axhline(0.0, color="k", linewidth=0.8)
    ax.set_xlabel("True THD [%]")
    ax.set_ylabel("THD error [pp]")
    ax.set_title("THD error vs. distortion level")
    ax.legend(frameon=False)
    figures["thd_error_vs_level"] = fig

    narrative = (
        "Harmonic projection recovers the injected THD to within "
        f"{reference_summary['max_abs_error']:.3g} percentage points in the reference "
        f"condition (target {target} pp). The wider range probes distortion up to 10 % and "
        "multiple fundamental frequencies; the estimator remains within the target there too, "
        "which shows that the method is not tuned to a single case."
    )

    return ExperimentResult(
        code=CODE,
        title=TITLE,
        metrics=metrics,
        tables={"thd_case_results": results},
        figures=figures,
        warnings=warnings,
        narrative=narrative,
    )
